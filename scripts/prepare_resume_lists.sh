#!/usr/bin/env bash
# ==============================================================
#   Prepare resume process-lists for feature extraction.
#
#   Run this on the LOGIN NODE before submitting the array job:
#       bash prepare_resume_lists.sh
#
#   For each cohort it:
#     1. Finds all WSIs in WSI_BASE/<COHORT>/
#     2. Identifies slides WITHOUT a completed .h5 (i.e. missing or
#        still has a .lock file alongside it)
#     3. Splits remaining slides into N_CHUNKS chunks
#     4. Writes CSVs to OUT_BASE/<COHORT>/resume_lists/chunk_0.csv ...
#
#   After this script finishes, submit the array job:
#       sbatch submit_cptac_resume_feat.sh
# ==============================================================

set -euo pipefail

WSI_BASE="/cluster/projects/kumargroup/CPTAC_data/Histology_by_CT"
OUT_BASE="/cluster/projects/kumargroup/CPTAC_data/trident_output"
FEAT_SUBDIR="20x_256px_0px_overlap/features_uni_v2"
N_CHUNKS=4

COHORTS=(
    CPTAC-AML
    CPTAC-BRCA
    CPTAC-COAD
    CPTAC-LUAD
    CPTAC-OV
    CPTAC-PDA
    CPTAC-STAD
    CPTAC-non-CCRCC
)

total_remaining=0

for COHORT in "${COHORTS[@]}"; do
    WSI_DIR="${WSI_BASE}/${COHORT}"
    FEAT_DIR="${OUT_BASE}/${COHORT}/${FEAT_SUBDIR}"
    LIST_DIR="${OUT_BASE}/${COHORT}/resume_lists"

    if [[ ! -d "${WSI_DIR}" ]]; then
        echo "[WARN]  ${COHORT}: WSI dir not found, skipping"
        continue
    fi

    mkdir -p "${LIST_DIR}"

    # Collect slides that still need features
    mapfile -t remaining < <(
        for wsi in "${WSI_DIR}"/*.svs "${WSI_DIR}"/*.tif; do
            [[ -e "${wsi}" ]] || continue
            base=$(basename "${wsi}")
            stem="${base%.*}"
            h5="${FEAT_DIR}/${stem}.h5"
            lock="${h5}.lock"
            # Needs processing if: no .h5, or .h5 exists but .lock is still there
            if [[ ! -f "${h5}" ]] || [[ -f "${lock}" ]]; then
                echo "${base}"
            fi
        done | sort
    )

    n=${#remaining[@]}
    echo "[INFO]  ${COHORT}: ${n} slides remaining"
    total_remaining=$(( total_remaining + n ))

    if [[ ${n} -eq 0 ]]; then
        # Write empty sentinel so the array job can detect and exit cleanly
        for i in $(seq 0 $(( N_CHUNKS - 1 ))); do
            echo "wsi" > "${LIST_DIR}/chunk_${i}.csv"
        done
        continue
    fi

    # Split into N_CHUNKS roughly equal CSVs
    chunk_size=$(( (n + N_CHUNKS - 1) / N_CHUNKS ))
    for i in $(seq 0 $(( N_CHUNKS - 1 ))); do
        csv="${LIST_DIR}/chunk_${i}.csv"
        echo "wsi" > "${csv}"
        start=$(( i * chunk_size ))
        for (( j = start; j < start + chunk_size && j < n; j++ )); do
            echo "${remaining[$j]}" >> "${csv}"
        done
        count=$(( $(wc -l < "${csv}") - 1 ))
        echo "         chunk ${i}: ${count} slides -> ${csv}"
    done
done

echo ""
echo "[INFO]  Total slides to resume: ${total_remaining}"
echo "[INFO]  Done. Submit with: sbatch submit_cptac_resume_feat.sh"
