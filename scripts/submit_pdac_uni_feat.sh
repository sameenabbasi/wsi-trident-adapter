#!/usr/bin/env bash
#SBATCH -p gpu
#SBATCH -A kumargroup_gpu
#SBATCH -c 8
#SBATCH --mem 32G
#SBATCH --gres gpu:1
#SBATCH -t 2-00:00
#SBATCH -J pdac-uni-feat
#SBATCH -o /cluster/projects/kumargroup/hayden/processed/PDAC/logs/slurm-%A_%a.out
#SBATCH -e /cluster/projects/kumargroup/hayden/processed/PDAC/logs/slurm-%A_%a.err
#SBATCH --array=0-15
#SBATCH --export=NONE

# ==============================================================
#   UNI v2 feature extraction for PDAC slides — 2 datasets × 8 GPUs
#   Array index: dataset = task_id / 8,  chunk = task_id % 8
#
#   Prerequisites:
#     1. bash scripts/prepare_pdac_lists.sh
#     2. sbatch scripts/submit_pdac_uni_feat.sh
# ==============================================================

set -euo pipefail
umask 002

source ~/miniforge3/bin/activate
conda activate methylcdm_h100

OUT_BASE="/cluster/projects/kumargroup/hayden/processed/PDAC"
N_GPUS=8

DATASET_NAMES=(
    "HE_LCM"
    "TMA"
)

DATASET_DIRS=(
    "/cluster/projects/kumargroup/hayden/data/PDAC/HE LCM cases"
    "/cluster/projects/kumargroup/hayden/data/PDAC/TMA/Slides"
)

DATASET_IDX=$(( SLURM_ARRAY_TASK_ID / N_GPUS ))
CHUNK_IDX=$(( SLURM_ARRAY_TASK_ID % N_GPUS ))

NAME="${DATASET_NAMES[$DATASET_IDX]}"
WSI_DIR="${DATASET_DIRS[$DATASET_IDX]}"
OUT_DIR="${OUT_BASE}/${NAME}"
PROCESS_LIST="${OUT_DIR}/process_lists/chunk_${CHUNK_IDX}.csv"

if [[ ! -d "${WSI_DIR}" ]]; then
    echo "[ERROR] WSI directory not found: ${WSI_DIR}" >&2
    exit 1
fi

if [[ ! -f "${PROCESS_LIST}" ]]; then
    echo "[ERROR] Process list not found: ${PROCESS_LIST}" >&2
    echo "[ERROR] Run prepare_pdac_lists.sh first." >&2
    exit 1
fi

slide_count=$(( $(wc -l < "${PROCESS_LIST}") - 1 ))
if [[ ${slide_count} -le 0 ]]; then
    echo "[INFO] No slides in ${NAME} chunk ${CHUNK_IDX}, exiting."
    exit 0
fi

# ---- Asset paths ----
ASSETS_ROOT="/cluster/projects/kumargroup/wsi-trident-adapter-assets"
export TRIDENT_HOME="${ASSETS_ROOT}/weights/trident"
export TORCH_HOME="${ASSETS_ROOT}/weights/torch"
export HF_HOME="${ASSETS_ROOT}/weights/huggingface"

# ---- Config ----
CONFIG_PATH="${OUT_DIR}/config_chunk${CHUNK_IDX}.yaml"
cat > "${CONFIG_PATH}" << YAML
io:
    wsi_dir: "${WSI_DIR}"
    job_dir: ${OUT_DIR}
    process_list: ${PROCESS_LIST}
    wsi_extension:
        - .svs
        - .tif

segmentation:
    segmenter: hest
    seg_conf_thresh: 0.4
    remove_artifacts: false
    remove_holes: false

patching:
    magnification: 20
    patch_size: 256
    overlap: 0
    min_tissue_proportion: 0.0

features:
    encoder: uni_v2
    batch_size: 64

system:
    device: cuda
YAML

# ---- Job info ----
echo "[INFO] Array task   : ${SLURM_ARRAY_TASK_ID} / ${SLURM_ARRAY_JOB_ID}"
echo "[INFO] Dataset      : ${NAME}  (index ${DATASET_IDX})"
echo "[INFO] Chunk        : ${CHUNK_IDX} / $(( N_GPUS - 1 ))  (${slide_count} slides)"
echo "[INFO] WSI dir      : ${WSI_DIR}"
echo "[INFO] Process list : ${PROCESS_LIST}"
echo "[INFO] Node         : $(hostname)"
echo "[INFO] Start        : $(date)"
echo ""

wsi-trident-adapter run --task all --config "${CONFIG_PATH}"

echo ""
echo "[INFO] Finished : $(date)"
