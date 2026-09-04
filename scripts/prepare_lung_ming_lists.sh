#!/usr/bin/env bash
# ==============================================================
#   Prepare process-list chunks for lung-data-ming patching.
#
#   Run on the LOGIN NODE before submitting an array job:
#       bash prepare_lung_ming_lists.sh [coords|feat]
#
#   Splits all .svs files in WSI_DIR into N_WORKERS chunks, skipping
#   slides already finished for the requested stage:
#     coords (default) — skip slides with a coords .h5   (seg + patch job)
#     feat             — skip slides with a features .h5 (feature job)
#
#   The two stages write to different chunk files, so preparing one
#   does not clobber the other.
#
#   NOTE: slide filenames in this cohort contain spaces
#   (e.g. "PHLC 189 UHNCEA-435.svs"). Everything below is
#   whitespace-safe; do not "simplify" the loops with word
#   splitting or unquoted globs.
# ==============================================================

set -euo pipefail

# ---- EDIT THESE ----
WSI_DIR="/cluster/projects/kumargroup/lung-data-ming"
OUT_DIR="/cluster/projects/kumargroup/lung_ming/processed"
N_WORKERS=8
# --------------------

ENCODER="uni_v2"
STAGE="${1:-coords}"

case "${STAGE}" in
    coords)
        DONE_DIR="${OUT_DIR}/20x_256px_0px_overlap/patches"
        LIST_DIR="${OUT_DIR}/process_lists"
        SUBMIT_SCRIPT="submit_lung_ming_patch.sh"
        ;;
    feat)
        DONE_DIR="${OUT_DIR}/20x_256px_0px_overlap/features_${ENCODER}"
        LIST_DIR="${OUT_DIR}/process_lists_feat"
        SUBMIT_SCRIPT="submit_lung_ming_feat.sh"
        ;;
    *)
        echo "[ERROR] Unknown stage '${STAGE}'. Use 'coords' or 'feat'." >&2
        exit 1
        ;;
esac

echo "[INFO] Stage: ${STAGE}"

mkdir -p "${LIST_DIR}"

if [[ ! -d "${WSI_DIR}" ]]; then
    echo "[ERROR] WSI directory not found: ${WSI_DIR}" >&2
    exit 1
fi

# Step 1: slides whose coords h5 is missing, empty, or still locked.
remaining=()
n_total=0
n_done=0
n_no_coords=0
COORDS_DIR="${OUT_DIR}/20x_256px_0px_overlap/patches"

while IFS= read -r -d '' wsi; do
    (( n_total++ )) || true
    fname=$(basename "${wsi}")
    stem="${fname%.*}"
    if [[ "${STAGE}" == "coords" ]]; then
        h5="${DONE_DIR}/${stem}_patches.h5"
    else
        h5="${DONE_DIR}/${stem}.h5"
    fi

    if [[ -s "${h5}" && ! -e "${h5}.lock" ]]; then
        (( n_done++ )) || true
        continue
    fi

    # Features are computed from existing coordinates; a slide that never
    # produced a coords h5 has nothing to encode.
    if [[ "${STAGE}" == "feat" ]]; then
        coords_h5="${COORDS_DIR}/${stem}_patches.h5"
        if [[ ! -s "${coords_h5}" || -e "${coords_h5}.lock" ]]; then
            (( n_no_coords++ )) || true
            continue
        fi
    fi

    remaining+=("${fname}")
done < <(find "${WSI_DIR}" -maxdepth 1 -type f -name '*.svs' -print0 | sort -z)

echo "[INFO] Slides found            : ${n_total}"
echo "[INFO] Already complete         : ${n_done}"
if [[ "${STAGE}" == "feat" && ${n_no_coords} -gt 0 ]]; then
    echo "[WARN] Skipped (no coords h5)   : ${n_no_coords}"
    echo "[WARN]   Re-run the coords stage for these first."
fi

n=${#remaining[@]}
echo "[INFO] Slides still to process : ${n}"

if [[ ${n} -eq 0 ]]; then
    echo "[INFO] Nothing to do."
    exit 0
fi

# Step 2: split into chunks. Filenames may contain spaces but never
# commas, so a bare single-column CSV stays valid.
chunk_size=$(( (n + N_WORKERS - 1) / N_WORKERS ))

for i in $(seq 0 $(( N_WORKERS - 1 ))); do
    csv="${LIST_DIR}/chunk_${i}.csv"
    echo "wsi" > "${csv}"
    start=$(( i * chunk_size ))
    for (( j = start; j < start + chunk_size && j < n; j++ )); do
        printf '%s\n' "${remaining[$j]}" >> "${csv}"
    done
    count=$(( $(wc -l < "${csv}") - 1 ))
    echo "  chunk ${i}: ${count} slides -> ${csv}"
done

# Guard: a comma in any filename would corrupt the CSV.
if grep -q ',' "${LIST_DIR}"/chunk_*.csv; then
    echo "[ERROR] A slide filename contains a comma; CSV manifest is invalid." >&2
    exit 1
fi

echo ""
echo "[INFO] Done. Submit with: sbatch --array=0-$(( N_WORKERS - 1 )) ${SUBMIT_SCRIPT}"
