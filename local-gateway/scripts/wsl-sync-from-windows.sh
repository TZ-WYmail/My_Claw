#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 /mnt/<drive>/path/to/My_Claw [target_dir]" >&2
  exit 1
fi

SOURCE_DIR="$(realpath "$1")"
TARGET_DIR="${2:-$HOME/projects/My_Claw}"

mkdir -p "$(dirname "${TARGET_DIR}")"

if command -v rsync >/dev/null 2>&1; then
  rsync -a --delete \
    --exclude '.venv' \
    --exclude 'frontend/node_modules' \
    --exclude 'local-gateway/.venv' \
    --exclude 'local-gateway/frontend/node_modules' \
    "${SOURCE_DIR}/" "${TARGET_DIR}/"
else
  rm -rf "${TARGET_DIR}"
  mkdir -p "${TARGET_DIR}"
  cp -a "${SOURCE_DIR}/." "${TARGET_DIR}/"
fi

echo "Synced ${SOURCE_DIR} -> ${TARGET_DIR}"
