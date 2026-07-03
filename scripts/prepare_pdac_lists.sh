#!/usr/bin/env bash
# ==============================================================
#   Prepare process-list chunks for PDAC feature extraction.
#
#   Run on the LOGIN NODE before submitting the array job:
#       bash scripts/prepare_pdac_lists.sh
#
#   Covers two source directories:
#     0 — HE LCM cases
#     1 — TMA/Slides
#
#   Each is split into N_GPUS chunks, skipping slides that
#   already have a completed .h5 (no .lock alongside).
# ==============================================================

set -euo pipefail

OUT_BASE="/cluster/projects/kumargroup/hayden/processed/PDAC"
N_GPUS=8
FEAT_SUBDIR="20x_256px_0px_overlap/features_uni_v2"

DATASET_NAMES=(
    "HE_LCM"
    "TMA"
)

DATASET_DIRS=(
    "/cluster/projects/kumargroup/hayden/data/PDAC/HE LCM cases"
    "/cluster/projects/kumargroup/hayden/data/PDAC/TMA/Slides"
)

total_remaining=0

for idx in "${!DATASET_NAMES[@]}"; do
    NAME="${DATASET_NAMES[$idx]}"
    WSI_DIR="${DATASET_DIRS[$idx]}"
    OUT_DIR="${OUT_BASE}/${NAME}"
    FEAT_DIR="${OUT_DIR}/${FEAT_SUBDIR}"
    LIST_DIR="${OUT_DIR}/process_lists"

    if [[ ! -d "${WSI_DIR}" ]]; then
        echo "[WARN]  ${NAME}: WSI dir not found, skipping"
        continue
    fi

    echo "[INFO]  Processing dataset: ${NAME}"
    echo "[INFO]  WSI dir: ${WSI_DIR}"

    # Collect stems with lock files
    declare -A needs_processing
    n_locks=0
    while IFS= read -r lockfile; do
        stem=$(basename "${lockfile}" .h5.lock)
        base_stem="${stem%-[0-9]*}"
        needs_processing["${base_stem}"]=1
        (( n_locks++ )) || true
    done < <(find "${OUT_DIR}" -name "*.h5.lock" 2>/dev/null || true)
    echo "         Lock files found: ${n_locks}"

    # Collect slides with no h5 output at all
    n_missing=0
    while IFS= read -r wsi; do
        [[ -e "${wsi}" ]] || continue
        stem=$(basename "${wsi%.*}")
        if ! compgen -G "${FEAT_DIR}/${stem}*.h5" > /dev/null 2>&1; then
            needs_processing["${stem}"]=1
            (( n_missing++ )) || true
        fi
    done < <(find "${WSI_DIR}" -maxdepth 1 \( -name "*.svs" -o -name "*.tif" \) 2>/dev/null)
    echo "         Slides with no h5: ${n_missing}"

    # Resolve stems back to WSI filenames
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
    echo "         Total remaining  : ${n}"
    total_remaining=$(( total_remaining + n ))

    if [[ ${n} -eq 0 ]]; then
        for i in $(seq 0 $(( N_GPUS - 1 ))); do
            echo "wsi" > "${LIST_DIR}/chunk_${i}.csv"
        done
        unset needs_processing
        continue
    fi

    chunk_size=$(( (n + N_GPUS - 1) / N_GPUS ))
    for i in $(seq 0 $(( N_GPUS - 1 ))); do
        csv="${LIST_DIR}/chunk_${i}.csv"
        printf 'wsi\n' > "${csv}"
        start=$(( i * chunk_size ))
        for (( j = start; j < start + chunk_size && j < n; j++ )); do
            printf '%s\n' "${remaining[$j]}" >> "${csv}"
        done
        count=$(( $(wc -l < "${csv}") - 1 ))
        echo "         chunk ${i}: ${count} slides -> ${csv}"
    done

    unset needs_processing
    echo ""
done

echo "[INFO]  Total slides to process: ${total_remaining}"
echo "[INFO]  Done. Submit with: sbatch scripts/submit_pdac_uni_feat.sh"
