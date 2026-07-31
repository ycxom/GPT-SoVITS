#!/bin/bash

set -euo pipefail

if [ -f /etc/download-source.env ]; then
    source /etc/download-source.env
fi

target_dir="/workspace/models/G2PWModel"
config_file="${target_dir}/config.py"

if [ -f "$config_file" ]; then
    echo "G2PWModel is already installed."
    exit 0
fi

case "${MODEL_SOURCE:-HF}" in
HF)
    model_url="https://huggingface.co/XXXXRT/GPT-SoVITS-Pretrained/resolve/main/G2PWModel.zip"
    ;;
HF-Mirror)
    model_url="https://hf-mirror.com/XXXXRT/GPT-SoVITS-Pretrained/resolve/main/G2PWModel.zip"
    ;;
ModelScope)
    model_url="https://www.modelscope.cn/models/XXXXRT/GPT-SoVITS-Pretrained/resolve/master/G2PWModel.zip"
    ;;
*)
    echo "Unsupported model source: ${MODEL_SOURCE}" >&2
    exit 1
    ;;
esac

archive="$(mktemp --suffix=.zip)"
trap 'rm -f "$archive"' EXIT

echo "Downloading G2PWModel from ${MODEL_SOURCE:-HF}..."
wget -nv --tries=25 --wait=5 --read-timeout=40 -O "$archive" "$model_url"
unzip -tq "$archive"
mkdir -p /workspace/models
unzip -q -o "$archive" -d /workspace/models

if [ ! -f "$config_file" ]; then
    echo "G2PWModel installation is incomplete: ${config_file} is missing." >&2
    exit 1
fi

echo "G2PWModel installed successfully."
