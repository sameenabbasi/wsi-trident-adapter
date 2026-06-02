#!/usr/bin/env bash
#SBATCH -p himem
#SBATCH -A kumargroup
#SBATCH -c 16
#SBATCH --mem 64G
#SBATCH -t 1-00:00
#SBATCH -J extract-patches-masks
#SBATCH -o /cluster/projects/kumargroup/ch_fibrosis_analysis/trident/logs/slurm-%j.out
#SBATCH -e /cluster/projects/kumargroup/ch_fibrosis_analysis/trident/logs/slurm-%j.err
#SBATCH --export=NONE

# ==============================================================
#   Patch + binary mask extraction from WSIs + GeoJSON annotations
#   Cluster: hpc-for-health  |  Account: kumargroup
# ==============================================================

set -euo pipefail
umask 002

# ==============================================================
#   EDIT BEFORE SUBMITTING
# ==============================================================

# Path to your GeoJSON annotation files (one per slide, matched by stem)
ANNOT_DIR="<PATH_TO_GEOJSON_DIR>"

# Path to this repo on the cluster
REPO_DIR="<PATH_TO_WSI_TRIDENT_ADAPTER_REPO>"

# Python environment (virtualenv or conda — keep one, remove the other)
source "${REPO_DIR}/.venv/bin/activate"
# conda activate your-env

# ==============================================================
#   END OF USER INPUTS
# ==============================================================

# ---- Guard for unedited placeholders ----
if [[ "$ANNOT_DIR" == "<PATH_TO_GEOJSON_DIR>" || "$REPO_DIR" == "<PATH_TO_WSI_TRIDENT_ADAPTER_REPO>" ]]; then
    echo "[ERROR] Edit ANNOT_DIR and REPO_DIR before submitting." >&2
    exit 1
fi

# ---- Fixed paths ----
WSI_DIR="/cluster/projects/kumargroup/ch-fibrosis"
OUT_DIR="/cluster/projects/kumargroup/ch_fibrosis_analysis/trident"

# ---- Asset / weight paths (hpc-for-health profile) ----
ASSETS_ROOT="/cluster/projects/kumargroup/wsi-trident-adapter-assets"
export TRIDENT_HOME="${ASSETS_ROOT}/weights/trident"
export TORCH_HOME="${ASSETS_ROOT}/weights/torch"
export HF_HOME="${ASSETS_ROOT}/weights/huggingface"

# ---- Create log and output dirs ----
mkdir -p "${OUT_DIR}/logs"
mkdir -p "${OUT_DIR}/patches"
mkdir -p "${OUT_DIR}/masks"

# ---- Job info ----
echo "[INFO] Job ID       : ${SLURM_JOB_ID}"
echo "[INFO] Node         : $(hostname)"
echo "[INFO] CPUs         : ${SLURM_CPUS_PER_TASK}"
echo "[INFO] WSI dir      : ${WSI_DIR}"
echo "[INFO] Annotation   : ${ANNOT_DIR}"
echo "[INFO] Output dir   : ${OUT_DIR}"
echo "[INFO] Start        : $(date)"
echo ""

# ---- Run extraction ----
python "${REPO_DIR}/scripts/extract_annotated_patches.py" \
    --wsi_dir        "${WSI_DIR}" \
    --annot_dir      "${ANNOT_DIR}" \
    --out_dir        "${OUT_DIR}" \
    --magnification  20 \
    --patch_size     256 \
    --overlap        0 \
    --num_workers    "${SLURM_CPUS_PER_TASK}"

echo ""
echo "[INFO] Finished : $(date)"
