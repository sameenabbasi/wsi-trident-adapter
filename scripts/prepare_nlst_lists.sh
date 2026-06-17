#!/usr/bin/env bash
# ==============================================================
#   Prepare process-list chunks for NLST feature extraction.
#
#   Run on the LOGIN NODE before submitting the array job:
#       bash prepare_nlst_lists.sh
#
#   Splits all .svs files in WSI_DIR into N_GPUS chunks,
#   skipping slides that already have a completed .h5.
# ==============================================================

set -euo pipefail

# ---- EDIT THESE ----
WSI_DIR="/cluster/projects/kumargroup/nlst/raw"
OUT_DIR="/cluster/projects/kumargroup/nlst/processed"
N_GPUS=8
# --------------------

FEAT_SUBDIR="20x_256px_0px_overlap/features_uni_v2"
LIST_DIR="${OUT_DIR}/process_lists"
FEAT_DIR="${OUT_DIR}/${FEAT_SUBDIR}"

mkdir -p "${LIST_DIR}"

mapfile -t remaining < <(
    for wsi in "${WSI_DIR}"/*.svs; do
        [[ -e "${wsi}" ]] || continue
        base=$(basename "${wsi}")
        stem="${base%.*}"
        h5="${FEAT_DIR}/${stem}.h5"
        lock="${h5}.lock"
        if [[ ! -f "${h5}" ]] || [[ -f "${lock}" ]]; then
            echo "${base}"
        fi
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
echo "[INFO] Done. Submit with: sbatch submit_nlst_uni_feat.sh"
