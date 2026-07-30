FROM debian:13

LABEL maintainer="XXXXRT"
LABEL description="GPT-SoVITS API server on Debian 13"

ARG PYTHON_VERSION=3.12
ARG CUDA_VERSION=12.8
ARG TARGETPLATFORM=linux/amd64
ARG WORKFLOW=true

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/workspace/GPT-SoVITS \
    CUDA_VERSION=${CUDA_VERSION} \
    TARGETPLATFORM=${TARGETPLATFORM} \
    WORKFLOW=${WORKFLOW} \
    PATH=/root/conda/bin:${PATH}

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
      build-essential \
      ca-certificates \
      cmake \
      curl \
      ffmpeg \
      git \
      libgomp1 \
      libsndfile1 \
      make \
      unzip \
      wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace/GPT-SoVITS

COPY Docker/miniforge_install.sh Docker/miniforge_install.sh

RUN bash Docker/miniforge_install.sh

COPY extra-req.txt requirements.txt install.sh ./
COPY Docker/install_wrapper.sh Docker/install_wrapper.sh

RUN bash Docker/install_wrapper.sh

COPY . .

RUN rm -rf \
      GPT_SoVITS/pretrained_models \
      GPT_SoVITS/text/G2PWModel \
      tools/asr/models \
      tools/uvr5/uvr5_weights \
    && ln -s /workspace/models/pretrained_models GPT_SoVITS/pretrained_models \
    && ln -s /workspace/models/G2PWModel GPT_SoVITS/text/G2PWModel \
    && ln -s /workspace/models/asr_models tools/asr/models \
    && ln -s /workspace/models/uvr5_weights tools/uvr5/uvr5_weights

EXPOSE 9880

CMD ["python", "api_server.py", "--bind_addr", "0.0.0.0", "--port", "9880"]
