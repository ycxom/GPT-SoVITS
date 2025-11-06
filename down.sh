run_wget_quiet() {
    if wget --tries=25 --wait=5 --read-timeout=40 -q --show-progress "$@" 2>&1; then
        tput cuu1 && tput el
    else
        echo -e "${ERROR} Wget failed"
        exit 1
    fi
}

# Find python
if command -v python3 &>/dev/null; then
    PYTHON_CMD=python3
elif command -v python &>/dev/null; then
    PYTHON_CMD=python
else
    echo "Error: Neither python3 nor python found. Please install python." >&2
    exit 1
fi

PRETRINED_URL="https://www.modelscope.cn/models/XXXXRT/GPT-SoVITS-Pretrained/resolve/master/pretrained_models.zip"
G2PW_URL="https://www.modelscope.cn/models/XXXXRT/GPT-SoVITS-Pretrained/resolve/master/G2PWModel.zip"
UVR5_URL="https://www.modelscope.cn/models/XXXXRT/GPT-SoVITS-Pretrained/resolve/master/uvr5_weights.zip"
NLTK_URL="https://www.modelscope.cn/models/XXXXRT/GPT-SoVITS-Pretrained/resolve/master/nltk_data.zip"
PYOPENJTALK_URL="https://www.modelscope.cn/models/XXXXRT/GPT-SoVITS-Pretrained/resolve/master/open_jtalk_dic_utf_8-1.11.tar.gz"

run_wget_quiet "$PRETRINED_URL"
unzip -q -o pretrained_models.zip -d GPT_SoVITS
rm -rf pretrained_models.zip

run_wget_quiet "$G2PW_URL"
unzip -q -o G2PWModel.zip -d GPT_SoVITS/text
rm -rf G2PWModel.zip

run_wget_quiet "$UVR5_URL"
unzip -q -o uvr5_weights.zip -d tools/uvr5
rm -rf uvr5_weights.zip

pip install torch torchaudio --index-url "https://download.pytorch.org/whl/cu128"

pip install -r extra-req.txt --no-deps

pip install -r requirements.txt

PY_PREFIX=$($PYTHON_CMD -c "import sys; print(sys.prefix)")
PYOPENJTALK_PREFIX=$($PYTHON_CMD -c "import os, pyopenjtalk; print(os.path.dirname(pyopenjtalk.__file__))")

run_wget_quiet "$NLTK_URL" -O nltk_data.zip
unzip -q -o nltk_data.zip -d "$PY_PREFIX"
rm -rf nltk_data.zip

run_wget_quiet "$PYOPENJTALK_URL" -O open_jtalk_dic_utf_8-1.11.tar.gz
tar -xzf open_jtalk_dic_utf_8-1.11.tar.gz -C "$PYOPENJTALK_PREFIX"
rm -rf open_jtalk_dic_utf_8-1.11.tar.gz
