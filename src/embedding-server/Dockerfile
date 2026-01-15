FROM archlinux:base

WORKDIR /app

# Install Arch dependencies
RUN pacman -Sy --noconfirm archlinux-keyring \
    && pacman -Syu --noconfirm --needed \
      ca-certificates \
      curl \
      git \
      base-devel \
      cmake \
      ninja \
      pkgconf \
      libjpeg-turbo \
      libpng \
      zlib \
      rocm-hip-sdk

# Install Python from Arch Linux archive (explicit 3.12.x)
ARG ARCHIVE_BASE=https://archive.archlinux.org/packages
ARG PYTHON_PKG_NAME=python-3.12.7-1-x86_64.pkg.tar.zst

RUN curl -fsSL "$ARCHIVE_BASE/p/python/$PYTHON_PKG_NAME" -o /tmp/python.pkg.tar.zst \
    && pacman -U --noconfirm /tmp/python.pkg.tar.zst \
    && rm -f /tmp/python.pkg.tar.zst \
    && pacman -Scc --noconfirm

# Install pip for the pinned Python version
ARG PIP_VERSION=
ENV PIP_BREAK_SYSTEM_PACKAGES=1
RUN curl -fsSL https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py \
    && if [ -n "$PIP_VERSION" ]; then python /tmp/get-pip.py "pip==${PIP_VERSION}" --break-system-packages; else python /tmp/get-pip.py; fi \
    && rm -f /tmp/get-pip.py \
    && python -m pip --version

# Install Python dependencies
COPY requirements.txt ./requirements.txt

RUN python -m pip install -r requirements.txt

COPY wheels/ /app/wheels/

# Build Pytorch and Torchvision if wheels not present
ARG PYTORCH_REF="" \
    TORCHVISION_REF="" \
    WHEEL_DIR=/app/wheels \
    CLONE_DIR=/tmp/bwe-pytorch-build \
    ROCM_PATH=/opt/rocm \
    PYTORCH_ROCM_ARCH=gfx1151 \
    CMAKE_PREFIX_PATH=/opt/rocm

RUN chmod +x /app/build-pytorch.sh && /app/build-pytorch.sh

# Run application
COPY . .

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    API_NAME="bwe-embedding-server" \
    API_VERSION="0.1.0" \
    API_HOST="0.0.0.0" \
    API_PORT="8090" \
    MODEL_ID="nomic-ai/nomic-embed-multimodal-3b"

EXPOSE ${API_PORT}

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import os, httpx; httpx.get(f\"http://127.0.0.1:{os.getenv('API_PORT','8090')}/health\").raise_for_status()" || exit 1

CMD ["python", "-m", "main"]


