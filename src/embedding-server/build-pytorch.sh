set -euo pipefail

export USE_ROCM=1
export USE_CUDA=0
export USE_SYSTEM_ROCM=1 

export ROCM_PATH="${ROCM_PATH:-/opt/rocm}"
export CMAKE_PREFIX_PATH="${CMAKE_PREFIX_PATH:-$ROCM_PATH}"
export HIP_PATH="${HIP_PATH:-$ROCM_PATH}"
export PATH="$ROCM_PATH/bin:${PATH}"
export LD_LIBRARY_PATH="$ROCM_PATH/lib:$ROCM_PATH/lib64:${LD_LIBRARY_PATH:-}"

# CMake expects a semicolon-separated list. Include both ROCm and Python site-packages.
PY_SITEPKG="$(python -c 'import site; print(site.getsitepackages()[0])' 2>/dev/null || true)"
export CMAKE_PREFIX_PATH="${CMAKE_PREFIX_PATH:-$ROCM_PATH${PY_SITEPKG:+;$PY_SITEPKG}}"
export PYTORCH_ROCM_ARCH="${PYTORCH_ROCM_ARCH:-}"

export MAX_JOBS="${MAX_JOBS:-4}"
export CMAKE_BUILD_PARALLEL_LEVEL="${CMAKE_BUILD_PARALLEL_LEVEL:-4}"

export BUILD_TEST=0
export USE_DISTRIBUTED=0
export USE_MPI=0
export USE_GLOO=0

# Pin these to avoid building arbitrary HEAD (torch/vision must match).
# Example:
#   export PYTORCH_REF="v2.5.1"
#   export TORCHVISION_REF="v0.20.1"
export PYTORCH_REF="${PYTORCH_REF:-}"
export TORCHVISION_REF="${TORCHVISION_REF:-}"

# If refs aren't provided, try to infer them from a sibling requirements.txt
# (common pattern: torch==2.9.1 -> v2.9.1, torchvision==0.24.1 -> v0.24.1).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQ_FILE="${SCRIPT_DIR}/requirements.txt"
if [ -z "$PYTORCH_REF" ] && [ -f "$REQ_FILE" ]; then
    TORCH_VER="$(grep -E '^torch==[0-9]+\.[0-9]+\.[0-9]+' "$REQ_FILE" | head -n 1 | cut -d= -f3 || true)"
    if [ -n "$TORCH_VER" ]; then
        PYTORCH_REF="v${TORCH_VER}"
        export PYTORCH_REF
    fi
fi
if [ -z "$TORCHVISION_REF" ] && [ -f "$REQ_FILE" ]; then
    TV_VER="$(grep -E '^torchvision==[0-9]+\.[0-9]+\.[0-9]+' "$REQ_FILE" | head -n 1 | cut -d= -f3 || true)"
    if [ -n "$TV_VER" ]; then
        TORCHVISION_REF="v${TV_VER}"
        export TORCHVISION_REF
    fi
fi

# Optional: build wheels inside a temp dir
CLONE_DIR="${CLONE_DIR:-/tmp/bwe-pytorch-build}"
WHEEL_DIR="${WHEEL_DIR:-$(pwd)/wheels}"
PIP_LOCAL_INSTALL_ARGS=(--no-index --find-links "$WHEEL_DIR" --no-deps --force-reinstall)


mkdir -p "$WHEEL_DIR"

if command -v rocminfo >/dev/null 2>&1; then
    echo "Detected ROCm GPU architectures:"
    ROCM_ARCH_LIST="$(rocminfo | grep -o 'gfx[0-9]\+' | sort -u | tr '\n' ' ' || true)"
    echo "  ${ROCM_ARCH_LIST:-<none>}"

    # Auto-select arch if not provided.
    # rocminfo sometimes includes both a family ("gfx11") and a specific target ("gfx1151").
    # For best correctness/perf, prefer the most specific (longest) gfx string.
    if [ -z "${PYTORCH_ROCM_ARCH}" ] && [ -n "${ROCM_ARCH_LIST}" ]; then
        # Prefer entries like gfx1151 (>= 6 chars: "gfx" + 4 digits), over generic like gfx11.
        SPECIFIC="$(printf "%s\n" ${ROCM_ARCH_LIST} | awk 'length($0) >= 7' | head -n 1 || true)"
        if [ -n "$SPECIFIC" ]; then
            PYTORCH_ROCM_ARCH="$SPECIFIC"
        else
            # Fallback: pick the longest entry (e.g. gfx1100 over gfx11), else first.
            PYTORCH_ROCM_ARCH="$(printf "%s\n" ${ROCM_ARCH_LIST} | awk '{ print length($0) ":" $0 }' | sort -nr | head -n 1 | cut -d: -f2-)"
        fi
        export PYTORCH_ROCM_ARCH
        echo "Auto-selected PYTORCH_ROCM_ARCH=$PYTORCH_ROCM_ARCH"
    fi
fi

mkdir -p "$CLONE_DIR"
cd "$CLONE_DIR"

echo "Build configuration:"
echo "  ROCM_PATH=$ROCM_PATH"
echo "  HIP_PATH=$HIP_PATH"
echo "  USE_SYSTEM_ROCM=$USE_SYSTEM_ROCM"
echo "  PYTORCH_ROCM_ARCH=${PYTORCH_ROCM_ARCH:-<unset>}"
echo "  PYTORCH_REF=${PYTORCH_REF:-<unset>}"
echo "  TORCHVISION_REF=${TORCHVISION_REF:-<unset>}"
echo "  CLONE_DIR=$CLONE_DIR"
echo "  WHEEL_DIR=$WHEEL_DIR"
echo "  CMAKE_PREFIX_PATH=$CMAKE_PREFIX_PATH"

if [ -z "${PYTORCH_ROCM_ARCH}" ]; then
    echo "ERROR: PYTORCH_ROCM_ARCH is not set and could not be auto-detected. Set it explicitly (e.g. gfx1151)." >&2
    exit 1
fi

echo "---- Uninstalling Previous Pytorch..."
python -m pip uninstall -y torch torchvision torchaudio

if ! ls "$WHEEL_DIR"/torch-*.whl >/dev/null 2>&1; then
    if [ ! -d "$ROCM_PATH" ]; then
        echo "ERROR: ROCM_PATH=$ROCM_PATH does not exist. Install ROCm (and headers/toolchain) before building." >&2
        exit 1
    fi

    if [ ! -x "$ROCM_PATH/bin/hipcc" ]; then
        echo "ERROR: $ROCM_PATH/bin/hipcc not found/executable. You need the ROCm HIP SDK/toolchain installed." >&2
        echo "       (On many distros this is the 'rocm-hip-sdk' / 'hipcc' package.)" >&2
        exit 1
    fi

    echo "Using hipcc: $ROCM_PATH/bin/hipcc"
    "$ROCM_PATH/bin/hipcc" --version || true

    if [ ! -d "pytorch" ]; then
        echo "---- Cloning Pytorch Source..."
        rm -rf pytorch
        git clone --recursive https://github.com/pytorch/pytorch
    fi

    cd pytorch

    # Ensure we have a full checkout (avoid sparse/partial surprises)
    git sparse-checkout disable >/dev/null 2>&1 || true

    if [ -n "$PYTORCH_REF" ]; then
        echo "---- Checking out Pytorch version $PYTORCH_REF..."
        git fetch --tags --force
        git checkout "$PYTORCH_REF"
    fi
    git submodule sync --recursive
    git submodule update --init --recursive

    # If this directory has been reused across refs, stale build dirs can cause confusing CMake errors.
    rm -rf build

    # build hip files
    echo "---- Building HIP files..."
    python tools/amd_build/build_amd.py

    echo "---- Building Pytorch Wheel..."

    python setup.py bdist_wheel
    mv dist/torch-*.whl "$WHEEL_DIR"/
else
    echo "---- PyTorch wheel already exists in $WHEEL_DIR"
fi

echo "---- Installing Pytorch Wheel..."
python -m pip install "${PIP_LOCAL_INSTALL_ARGS[@]}" "$WHEEL_DIR"/torch-*.whl

#echo "---- Verifying torch is ROCm-enabled (torch.version.hip must be set)..."
#python - <<'PY'
#import torch
#print("torch", torch.__version__)
#print("torch.version.hip", torch.version.hip)
#print("torch.version.cuda", torch.version.cuda)
#print("torch.cuda.is_available()", torch.cuda.is_available())
#if torch.version.hip is None:
#    raise SystemExit("ERROR: Installed torch is CPU-only (torch.version.hip is None). ROCm was not compiled in.")
#PY


cd "$CLONE_DIR"
if ! ls "$WHEEL_DIR"/torchvision-*.whl >/dev/null 2>&1; then
    if [ ! -d "$ROCM_PATH" ]; then
        echo "ERROR: ROCM_PATH=$ROCM_PATH does not exist. Install ROCm (and headers/toolchain) before building." >&2
        exit 1
    fi

    if [ ! -x "$ROCM_PATH/bin/hipcc" ]; then
        echo "ERROR: $ROCM_PATH/bin/hipcc not found/executable. You need the ROCm HIP SDK/toolchain installed." >&2
        echo "       (On many distros this is the 'rocm-hip-sdk' / 'hipcc' package.)" >&2
        exit 1
    fi

    echo "Using hipcc: $ROCM_PATH/bin/hipcc"
    "$ROCM_PATH/bin/hipcc" --version || true

    if [ ! -d "vision" ]; then
      echo "---- Building Torchvision wheel"
      git clone --recursive https://github.com/pytorch/vision.git
    fi

    cd vision

    git sparse-checkout disable >/dev/null 2>&1 || true

    if [ -n "$TORCHVISION_REF" ]; then
        echo "---- Checking out Torchvision version $TORCHVISION_REF..."
        git fetch --tags --force
        git checkout "$TORCHVISION_REF"
    fi
    git submodule sync --recursive
    git submodule update --init --recursive

    rm -rf build

    echo "---- Building Torchvision Wheel..."
    python setup.py bdist_wheel
    mv dist/torchvision-*.whl "$WHEEL_DIR"/
else
    echo "---- Torchvision wheel already exists in $WHEEL_DIR"
fi

echo "---- Installing Torchvision Wheel (no deps, local only)..."
python -m pip install "${PIP_LOCAL_INSTALL_ARGS[@]}" "$WHEEL_DIR"/torchvision-*.whl


echo "---- Done. Wheels in: $WHEEL_DIR"