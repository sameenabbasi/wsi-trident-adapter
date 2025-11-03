#!/usr/bin/env bash
set -euo pipefail

profile="hpc-for-health"

REQ_FILE="$(dirname "$0")/requirements.txt"
if [ -f "$REQ_FILE" ]; then
    pip install -r "$REQ_FILE" --no-cache-dir
else
    echo "[install.sh] requirements.txt not found at $REQ_FILE" >&2
    exit 1
fi

python -m trident_adapter.scripts.copy_ckpts "$profile"

# TODO Will be removed