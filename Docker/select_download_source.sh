#!/bin/bash

set -euo pipefail

SOURCE_MODE="${1:-auto}"

probe_latency() {
    local host="$1"
    local started elapsed

    started="$(date +%s%3N)"
    if timeout 4 bash -c "exec 3<>/dev/tcp/${host}/443" 2>/dev/null; then
        elapsed=$(( $(date +%s%3N) - started ))
        echo "$elapsed"
    else
        echo "999999"
    fi
}

select_fastest() {
    local best_host=""
    local best_latency=999999
    local host latency

    for host in "$@"; do
        latency="$(probe_latency "$host")"
        echo "Download source probe: ${host} ${latency}ms" >&2
        if ((latency < best_latency)); then
            best_host="$host"
            best_latency="$latency"
        fi
    done

    if [[ -z "$best_host" ]]; then
        echo "No download source is reachable." >&2
        return 1
    fi

    echo "$best_host"
}

case "$SOURCE_MODE" in
auto)
    apt_host="$(select_fastest deb.debian.org mirrors.ustc.edu.cn mirrors.tuna.tsinghua.edu.cn)"
    conda_host="$(select_fastest conda.anaconda.org mirrors.tuna.tsinghua.edu.cn)"
    pypi_host="$(select_fastest pypi.org pypi.tuna.tsinghua.edu.cn)"
    model_host="$(select_fastest huggingface.co hf-mirror.com www.modelscope.cn)"
    ;;
official)
    apt_host="deb.debian.org"
    conda_host="conda.anaconda.org"
    pypi_host="pypi.org"
    model_host="huggingface.co"
    ;;
ustc)
    apt_host="mirrors.ustc.edu.cn"
    conda_host="conda.anaconda.org"
    pypi_host="pypi.org"
    model_host="hf-mirror.com"
    ;;
tuna)
    apt_host="mirrors.tuna.tsinghua.edu.cn"
    conda_host="mirrors.tuna.tsinghua.edu.cn"
    pypi_host="pypi.tuna.tsinghua.edu.cn"
    model_host="hf-mirror.com"
    ;;
*)
    echo "Unknown DOWNLOAD_SOURCE: ${SOURCE_MODE}" >&2
    echo "Choose from: auto, official, ustc, tuna" >&2
    exit 1
    ;;
esac

case "$apt_host" in
mirrors.ustc.edu.cn) apt_mirror="http://mirrors.ustc.edu.cn" ;;
mirrors.tuna.tsinghua.edu.cn) apt_mirror="http://mirrors.tuna.tsinghua.edu.cn" ;;
*) apt_mirror="http://deb.debian.org" ;;
esac

case "$conda_host" in
mirrors.tuna.tsinghua.edu.cn) conda_mirror="https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud" ;;
*) conda_mirror="" ;;
esac

case "$pypi_host" in
pypi.tuna.tsinghua.edu.cn) pip_index_url="https://pypi.tuna.tsinghua.edu.cn/simple" ;;
*) pip_index_url="https://pypi.org/simple" ;;
esac

case "$model_host" in
hf-mirror.com) model_source="HF-Mirror" ;;
www.modelscope.cn) model_source="ModelScope" ;;
*) model_source="HF" ;;
esac

echo "APT_MIRROR=${apt_mirror}"
echo "CONDA_MIRROR=${conda_mirror}"
echo "PIP_INDEX_URL=${pip_index_url}"
echo "MODEL_SOURCE=${model_source}"
