#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"

cd "$SCRIPT_DIR" || exit 1

cd .. || exit 1

set -e

if [ -f /etc/download-source.env ]; then
    source /etc/download-source.env
    export PIP_INDEX_URL
fi

source "$HOME/conda/etc/profile.d/conda.sh"

mkdir -p GPT_SoVITS

mkdir -p GPT_SoVITS/text

mkdir -p \
    /workspace/models/pretrained_models \
    /workspace/models/G2PWModel \
    /workspace/models/asr_models \
    /workspace/models/uvr5_weights

ln -s /workspace/models/pretrained_models /workspace/GPT-SoVITS/GPT_SoVITS/pretrained_models

ln -s /workspace/models/G2PWModel /workspace/GPT-SoVITS/GPT_SoVITS/text/G2PWModel

TERM=dumb bash install.sh --device "CU${CUDA_VERSION//./}" --source "${MODEL_SOURCE:-HF}"

pip cache purge

pip show torch

rm -rf /tmp/* /var/tmp/*

rm -rf "$HOME/conda/pkgs"

mkdir -p "$HOME/conda/pkgs"

rm -rf /root/.conda /root/.cache
