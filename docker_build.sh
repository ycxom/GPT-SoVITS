#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
cd "$SCRIPT_DIR"

PYTHON_VERSION=3.12
CUDA_VERSION=""
DOWNLOAD_SOURCE=auto

print_help() {
    echo "Usage: bash docker_build.sh [OPTIONS]"
    echo ""
    echo "Builds the Debian 13 API image using the best supported CUDA runtime."
    echo "The CUDA version is detected from the local NVIDIA driver by default."
    echo ""
    echo "Options:"
    echo "  --cuda 12.6|12.8|13.0  Override automatic CUDA detection"
    echo "  --python 3.12           Override the recommended Python version"
    echo "  --source MODE           Download source: auto, official, ustc, tuna"
    echo "  -h, --help              Show this help message and exit"
}

select_cuda_runtime() {
    local driver_cuda="$1"
    local major minor

    IFS=. read -r major minor <<<"$driver_cuda"
    minor="${minor:-0}"

    if ((major >= 13)); then
        echo "13.0"
    elif ((major == 12 && minor >= 8)); then
        echo "12.8"
    elif ((major == 12 && minor >= 6)); then
        echo "12.6"
    else
        echo "Unsupported NVIDIA driver CUDA compatibility: ${driver_cuda}" >&2
        echo "CUDA 12.6 or newer is required." >&2
        return 1
    fi
}

detect_cuda_runtime() {
    local driver_cuda

    if ! command -v nvidia-smi &>/dev/null; then
        echo "nvidia-smi was not found. Install an NVIDIA driver or pass --cuda." >&2
        return 1
    fi

    driver_cuda="$(
        nvidia-smi 2>/dev/null |
            sed -n 's/.*CUDA Version: \([0-9][0-9]*\.[0-9][0-9]*\).*/\1/p' |
            head -n 1
    )"

    if [[ -z "$driver_cuda" ]]; then
        echo "Unable to detect CUDA compatibility from nvidia-smi." >&2
        return 1
    fi

    select_cuda_runtime "$driver_cuda"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
    --cuda)
        CUDA_VERSION="${2:-}"
        shift 2
        ;;
    --python)
        PYTHON_VERSION="${2:-}"
        shift 2
        ;;
    --source)
        DOWNLOAD_SOURCE="${2:-}"
        shift 2
        ;;
    -h | --help)
        print_help
        exit 0
        ;;
    *)
        echo "Unknown argument: $1" >&2
        print_help
        exit 1
        ;;
    esac
done

if [[ -z "$CUDA_VERSION" ]]; then
    CUDA_VERSION="$(detect_cuda_runtime)"
fi

case "$CUDA_VERSION" in
12.6 | 12.8 | 13.0) ;;
*)
    echo "Unsupported CUDA runtime: $CUDA_VERSION" >&2
    echo "Choose from: 12.6, 12.8, 13.0" >&2
    exit 1
    ;;
esac

case "$DOWNLOAD_SOURCE" in
auto | official | ustc | tuna) ;;
*)
    echo "Unsupported download source: $DOWNLOAD_SOURCE" >&2
    echo "Choose from: auto, official, ustc, tuna" >&2
    exit 1
    ;;
esac

case "$(uname -m)" in
x86_64 | amd64) TARGET_PLATFORM="linux/amd64" ;;
aarch64 | arm64) TARGET_PLATFORM="linux/arm64" ;;
*)
    echo "Unsupported architecture: $(uname -m)" >&2
    exit 1
    ;;
esac

echo "Building with Python ${PYTHON_VERSION}, CUDA ${CUDA_VERSION}, platform ${TARGET_PLATFORM}, source ${DOWNLOAD_SOURCE}"

SOURCE_REVISION="$(date -u +%Y%m%d%H%M%S)"

docker build \
    --build-arg "CUDA_VERSION=${CUDA_VERSION}" \
    --build-arg "PYTHON_VERSION=${PYTHON_VERSION}" \
    --build-arg "TARGETPLATFORM=${TARGET_PLATFORM}" \
    --build-arg "WORKFLOW=true" \
    --build-arg "DOWNLOAD_SOURCE=${DOWNLOAD_SOURCE}" \
    --build-arg "SOURCE_REVISION=${SOURCE_REVISION}" \
    --tag "gpt-sovits-api:local" \
    .
