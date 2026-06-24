#!/usr/bin/env bash
# ==============================================================
#   Prepare process-list chunks for PTRC_HGSOC feature extraction.
#
#   Run on the LOGIN NODE before submitting the array job:
#       bash prepare_ptrc_hgsoc_lists.sh
#
#   Splits all .svs files in WSI_DIR into N_GPUS chunks,
#   skipping slides that already have a completed .h5.
# ==============================================================

set -euo pipefail

# ---- EDIT THESE ----
WSI_DIR="/cluster/projects/kumargroup/PTRC_HGSOC/histology/raw"
OUT_DIR="/cluster/projects/kumargroup/PTRC_HGSOC/histology/processed"
N_GPUS=8
# --------------------

FEAT_SUBDIR="20x_256px_0px_overlap/features_uni_v2"
LIST_DIR="${OUT_DIR}/process_lists"
FEAT_DIR="${OUT_DIR}/${FEAT_SUBDIR}"

mkdir -p "${LIST_DIR}"

# Step 1: collect stems that have a .lock file anywhere under OUT_DIR.
declare -A needs_processing

n_locks=0
while IFS= read -r lockfile; do
    stem=$(basename "${lockfile}" .h5.lock)
    base_stem="${stem%-[0-9]*}"
    needs_processing["${base_stem}"]=1
    (( n_locks++ )) || true
done < <(find "${OUT_DIR}" -name "*.h5.lock")
echo "[INFO] Lock files found: ${n_locks}"

# Step 2: add slides with no h5 output at all.
n_missing=0
for wsi in "${WSI_DIR}"/*.svs "${WSI_DIR}"/*.tif; do
    [[ -e "${wsi}" ]] || continue
    stem=$(basename "${wsi%.*}")
    if ! compgen -G "${FEAT_DIR}/${stem}*.h5" > /dev/null 2>&1; then
        needs_processing["${stem}"]=1
        (( n_missing++ )) || true
    fi
done
echo "[INFO] Slides with no h5 output: ${n_missing}"

# Step 3: resolve stems back to WSI filenames.
mapfile -t remaining < <(
    for stem in "${!needs_processing[@]}"; do
        for ext in svs tif; do
            if [[ -f "${WSI_DIR}/${stem}.${ext}" ]]; then
                echo "${stem}.${ext}"
                break
            fi
        done
    done | sort
)

n=${#remaining[@]}
echo "[INFO] Total WSIs found without completed features: ${n}"

if [[ ${n} -eq 0 ]]; then
    echo "[INFO] Nothing to do."
    exit 0
fi

chunk_size=$(( (n + N_GPUS - 1) / N_GPUS ))

for i in $(seq 0 $(( N_GPUS - 1 ))); do
    csv="${LIST_DIR}/chunk_${i}.csv"
    echo "wsi" > "${csv}"
    start=$(( i * chunk_size ))
    for (( j = start; j < start + chunk_size && j < n; j++ )); do
        echo "${remaining[$j]}" >> "${csv}"
    done
    count=$(( $(wc -l < "${csv}") - 1 ))
    echo "  chunk ${i}: ${count} slides -> ${csv}"
done

echo ""
echo "[INFO] Done. Submit with: sbatch submit_ptrc_hgsoc_uni_feat.sh"
