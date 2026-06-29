#!/usr/bin/env bash
# ==============================================================
#   Prepare process-list chunks for TCGA-OV feature extraction.
#
#   Run on the LOGIN NODE before submitting the array job:
#       bash prepare_tcga_ov_lists.sh
#
#   Reads slide filenames from SLIDE_LIST, checks which already
#   have a completed .h5, and splits the remainder into N_GPUS chunks.
# ==============================================================

set -euo pipefail

# ---- EDIT THESE ----
SLIDE_LIST="/cluster/projects/kumargroup/sean/data/new_proteomics/TCGA-OV/slides_for_feature_extraction.txt"
WSI_DIR="/cluster/projects/kumargroup/hayden/data/TCGA/TCGA-OV/slides/raw"
OUT_DIR="/cluster/projects/kumargroup/sean/data/TCGA_features/new_TCGA_OV"
N_GPUS=8
# --------------------

FEAT_SUBDIR="20x_256px_0px_overlap/features_uni_v2"
LIST_DIR="${OUT_DIR}/process_lists"
FEAT_DIR="${OUT_DIR}/${FEAT_SUBDIR}"

mkdir -p "${LIST_DIR}"

if [[ ! -f "${SLIDE_LIST}" ]]; then
    echo "[ERROR] Slide list not found: ${SLIDE_LIST}" >&2
    exit 1
fi

# Step 1: collect stems that have a .lock file (incomplete prior run).
declare -A needs_processing

n_locks=0
while IFS= read -r lockfile; do
    stem=$(basename "${lockfile}" .h5.lock)
    base_stem="${stem%-[0-9]*}"
    needs_processing["${base_stem}"]=1
    (( n_locks++ )) || true
done < <(find "${OUT_DIR}" -name "*.h5.lock" 2>/dev/null)
echo "[INFO] Lock files found: ${n_locks}"

# Step 2: add slides from SLIDE_LIST that have no completed .h5 output.
n_missing=0
while IFS= read -r filename || [[ -n "${filename}" ]]; do
    [[ -z "${filename}" ]] && continue
    stem="${filename%.*}"
    if ! compgen -G "${FEAT_DIR}/${stem}*.h5" > /dev/null 2>&1; then
        needs_processing["${stem}"]=1
        (( n_missing++ )) || true
    fi
done < "${SLIDE_LIST}"
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
echo "[INFO] Total WSIs to process: ${n}"

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
echo "[INFO] Done. Submit with: sbatch submit_tcga_ov_uni_feat.sh"
