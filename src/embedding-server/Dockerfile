FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    API_NAME="bwe-embedding-server" \
    API_VERSION="0.1.0" \
    API_HOST="0.0.0.0" \
    API_PORT="8090" \
    MODEL_ID="nomic-ai/nomic-embed-multimodal-3b"

# Build/runtime deps:
# - git/curl: fetch model repos, clone pytorch/vision (if you build from source)
# - build-essential/cmake/ninja/pkg-config: native builds
# - libjpeg/libpng/zlib: torchvision image codecs
# Note: building ROCm-enabled torch from source still requires ROCm toolchain and headers
# to be present in the image (commonly via a ROCm base image or bind-mounted /opt/rocm).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
      ca-certificates \
      curl \
      git \
      gcc \
      g++ \
      make \
      cmake \
      ninja-build \
      pkg-config \
      python3-dev \
      libjpeg-dev \
      libpng-dev \
      zlib1g-dev \
      rocm-hip-sdk \
    && rm -rf /var/lib/apt/lists/*

    
COPY requirements.txt ./requirements.txt
RUN pip install -U setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Optional: build and cache ROCm torch/torchvision wheels into /app/wheels during image build.
# Usage:
#   docker build --build-arg PYTORCH_REF=v2.5.1 --build-arg TORCHVISION_REF=v0.20.1 .
ARG PYTORCH_REF=""
ARG TORCHVISION_REF=""
ENV PYTORCH_REF=${PYTORCH_REF} \
    TORCHVISION_REF=${TORCHVISION_REF} \
    WHEEL_DIR=/app/wheels \
    WORKDIR=/tmp/bwe-pytorch-build \
    ROCM_PATH=/opt/rocm \
    CMAKE_PREFIX_PATH=/opt/rocm

RUN chmod +x /app/build-pytorch.sh && /app/build-pytorch.sh

EXPOSE ${API_PORT}

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import os, httpx; httpx.get(f\"http://127.0.0.1:{os.getenv('API_PORT','8090')}/health\").raise_for_status()" || exit 1

CMD ["python", "-m", "main"]


