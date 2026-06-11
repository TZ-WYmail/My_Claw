#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CONDA_HOME="${WSL_CONDA_HOME:-$HOME/miniconda3}"
CONDA_SH="${CONDA_HOME}/etc/profile.d/conda.sh"
ENV_NAME="${WSL_CONDA_ENV:-claude}"

cd "${PROJECT_ROOT}"

if [[ ! -f "${CONDA_SH}" ]]; then
  echo "Conda not found at ${CONDA_SH}. Run ./scripts/wsl-setup.sh after installing Miniconda." >&2
  exit 1
fi

source "${CONDA_SH}"
conda activate "${ENV_NAME}"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

python main.py
