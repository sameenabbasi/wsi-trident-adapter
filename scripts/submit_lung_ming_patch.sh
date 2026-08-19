#!/usr/bin/env bash
#SBATCH -p gpu
#SBATCH -A kumargroup_gpu
#SBATCH -c 8
#SBATCH --mem 32G
#SBATCH --gres gpu:1
#SBATCH -t 1-00:00
#SBATCH -J lung-ming-patch
#SBATCH -o /cluster/projects/kumargroup/lung_ming/processed/logs/slurm-%A_%a.out
#SBATCH -e /cluster/projects/kumargroup/lung_ming/processed/logs/slurm-%A_%a.err
#SBATCH --array=0-7
#SBATCH --export=NONE

# ==============================================================
#   Tissue segmentation + patch coordinate extraction
#   for the lung-data-ming cohort (no feature extraction).
#
#   Stage 1 (seg)   : HEST tissue segmenter -> background removed
#   Stage 2 (patch) : 20x / 256px / 0 overlap coords written to h5
#
#   Prerequisites:
#     1. Check WSI_DIR / OUT_DIR below
#     2. Run:   bash prepare_lung_ming_lists.sh
#     3. Submit: sbatch submit_lung_ming_patch.sh
# ==============================================================

set -euo pipefail
umask 002

source ~/miniforge3/bin/activate
conda activate methylcdm_h100

# ---- EDIT THESE ----
WSI_DIR="/cluster/projects/kumargroup/lung-data-ming"
OUT_DIR="/cluster/projects/kumargroup/lung_ming/processed"
# --------------------

PROCESS_LIST="${OUT_DIR}/process_lists/chunk_${SLURM_ARRAY_TASK_ID}.csv"

# ---- Sanity checks ----
if [[ ! -d "${WSI_DIR}" ]]; then
    echo "[ERROR] WSI directory not found: ${WSI_DIR}" >&2
    exit 1
fi

if [[ ! -f "${PROCESS_LIST}" ]]; then
    echo "[ERROR] Process list not found: ${PROCESS_LIST}" >&2
    echo "[ERROR] Run prepare_lung_ming_lists.sh first." >&2
    exit 1
fi

slide_count=$(( $(wc -l < "${PROCESS_LIST}") - 1 ))
if [[ ${slide_count} -le 0 ]]; then
    echo "[INFO] No slides in chunk ${SLURM_ARRAY_TASK_ID}, exiting."
    exit 0
fi

mkdir -p "${OUT_DIR}/logs"

# ---- Asset paths (hpc-for-health profile) ----
ASSETS_ROOT="/cluster/projects/kumargroup/wsi-trident-adapter-assets"
export TRIDENT_HOME="${ASSETS_ROOT}/weights/trident"
export TORCH_HOME="${ASSETS_ROOT}/weights/torch"
export HF_HOME="${ASSETS_ROOT}/weights/huggingface"

# ---- Config ----
CONFIG_PATH="${OUT_DIR}/config_chunk${SLURM_ARRAY_TASK_ID}.yaml"
cat > "${CONFIG_PATH}" << YAML
io:
    wsi_dir: ${WSI_DIR}
    job_dir: ${OUT_DIR}
    process_list: ${PROCESS_LIST}
    wsi_extension:
        - .svs

segmentation:
    segmenter: hest
    seg_conf_thresh: 0.4
    remove_artifacts: false
    remove_holes: false

patching:
    magnification: 20
    patch_size: 256
    overlap: 0
    min_tissue_proportion: 0.1

features:
    encoder: uni_v2
    batch_size: 64

system:
    device: cuda
YAML

# ---- Job info ----
echo "[INFO] Array task   : ${SLURM_ARRAY_TASK_ID} / ${SLURM_ARRAY_JOB_ID}"
echo "[INFO] Chunk        : ${SLURM_ARRAY_TASK_ID} (${slide_count} slides)"
echo "[INFO] Process list : ${PROCESS_LIST}"
echo "[INFO] Node         : $(hostname)"
echo "[INFO] Start        : $(date)"
echo ""

# Two stages instead of --task all: 'all' would also run feature
# extraction, which this cohort does not need yet.
echo "[INFO] === Stage 1/2: segmentation ==="
wsi-trident-adapter run --task seg   --config "${CONFIG_PATH}"

echo "[INFO] === Stage 2/2: patch coordinates ==="
wsi-trident-adapter run --task patch --config "${CONFIG_PATH}"

echo ""
echo "[INFO] Finished : $(date)"
echo "[INFO] Coords   : ${OUT_DIR}/20x_256px_0px_overlap/patches/"
echo "[INFO] Masks    : ${OUT_DIR}/contours_geojson/ , ${OUT_DIR}/contours/"
