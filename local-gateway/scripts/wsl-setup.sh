#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CONDA_HOME="${WSL_CONDA_HOME:-$HOME/miniconda3}"
CONDA_SH="${CONDA_HOME}/etc/profile.d/conda.sh"
ENV_NAME="${WSL_CONDA_ENV:-claude}"

cd "${PROJECT_ROOT}"

if [[ ! -f "${CONDA_SH}" ]]; then
  echo "Conda not found at ${CONDA_SH}. Set WSL_CONDA_HOME or install Miniconda first." >&2
  exit 1
fi

source "${CONDA_SH}"

if conda env list | awk '{print $1}' | grep -qx "${ENV_NAME}"; then
  conda env update -n "${ENV_NAME}" -f environment.yml --prune
else
  conda env create -n "${ENV_NAME}" -f environment.yml
fi

conda activate "${ENV_NAME}"

echo "WSL conda environment ready: ${ENV_NAME}"

if command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1; then
  echo "Node detected: $(node --version)"
  echo "npm detected: $(npm --version)"
  if [[ -f frontend/package.json ]]; then
    (cd frontend && npm install)
  fi
else
  echo "Node.js not found in WSL. Backend is ready; frontend install skipped."
fi
