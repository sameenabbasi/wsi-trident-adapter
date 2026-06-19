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


# Build a set of WSI stems that have ANY lock file in the feat dir.
# Trident sometimes appends a series suffix (e.g. NLSI0000251-001.h5.lock)
# so we strip trailing -NNN before matching back to the WSI filename.
declare -A locked_stems
while IFS= read -r lockfile; do
    stem=$(basename "${lockfile}" .h5.lock)
    base_stem="${stem%-[0-9]*}"   # strip trailing -001 / -002 etc.
    locked_stems["${base_stem}"]=1
done < <(find "${FEAT_DIR}" -maxdepth 1 -name "*.h5.lock" 2>/dev/null)

mapfile -t remaining < <(
    for wsi in "${WSI_DIR}"/*.svs "${WSI_DIR}"/*.tif; do
        [[ -e "${wsi}" ]] || continue
        base=$(basename "${wsi}")
        stem="${base%.*}"
        h5="${FEAT_DIR}/${stem}.h5"
        # Include if: no exact-stem h5, OR lock exists (direct or series-suffixed)
        if [[ ! -f "${h5}" ]] || [[ -n "${locked_stems[${stem}]+x}" ]]; then
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
