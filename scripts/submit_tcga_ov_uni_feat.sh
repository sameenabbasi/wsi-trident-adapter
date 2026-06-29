#!/usr/bin/env bash
#SBATCH -p gpu
#SBATCH -A kumargroup_gpu
#SBATCH -c 8
#SBATCH --mem 32G
#SBATCH --gres gpu:1
#SBATCH -t 2-00:00
#SBATCH -J tcga-ov-uni-feat
#SBATCH -o /cluster/projects/kumargroup/sean/data/TCGA_features/new_TCGA_OV/logs/slurm-%A_%a.out
#SBATCH -e /cluster/projects/kumargroup/sean/data/TCGA_features/new_TCGA_OV/logs/slurm-%A_%a.err
#SBATCH --array=0-7
#SBATCH --export=NONE

# ==============================================================
#   UNI v2 patching + feature extraction for TCGA-OV slides
#   8 parallel GPU workers, each processing one chunk of slides
#
#   Prerequisites:
#     1. Slide list is at:
#        /cluster/projects/kumargroup/sean/data/new_proteomics/TCGA-OV/slides_for_feature_extraction.txt
#     2. Run:    bash prepare_tcga_ov_lists.sh
#     3. Submit: sbatch submit_tcga_ov_uni_feat.sh
# ==============================================================

set -euo pipefail
umask 002

source ~/miniforge3/bin/activate
conda activate methylcdm_h100

# ---- EDIT THIS ----
WSI_DIR="/cluster/projects/kumargroup/hayden/data/TCGA/TCGA-OV/slides/raw"
# -------------------

OUT_DIR="/cluster/projects/kumargroup/sean/data/TCGA_features/new_TCGA_OV"
PROCESS_LIST="${OUT_DIR}/process_lists/chunk_${SLURM_ARRAY_TASK_ID}.csv"

# ---- Sanity checks ----
if [[ ! -d "${WSI_DIR}" ]]; then
    echo "[ERROR] WSI directory not found: ${WSI_DIR}" >&2
    exit 1
fi

if [[ ! -f "${PROCESS_LIST}" ]]; then
    echo "[ERROR] Process list not found: ${PROCESS_LIST}" >&2
    echo "[ERROR] Run prepare_tcga_ov_lists.sh first." >&2
    exit 1
fi

slide_count=$(( $(wc -l < "${PROCESS_LIST}") - 1 ))
if [[ ${slide_count} -le 0 ]]; then
    echo "[INFO] No slides in chunk ${SLURM_ARRAY_TASK_ID}, exiting."
    exit 0
fi

# ---- Asset paths ----
ASSETS_ROOT="/cluster/projects/kumargroup/wsi-trident-adapter-assets"
export TRIDENT_HOME="${ASSETS_ROOT}/weights/trident"
export TORCH_HOME="${ASSETS_ROOT}/weights/torch"
export HF_HOME="${ASSETS_ROOT}/weights/huggingface"

# ---- Create log dir ----
mkdir -p "${OUT_DIR}/logs"

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
    min_tissue_proportion: 0.0

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

wsi-trident-adapter run --task all --config "${CONFIG_PATH}"

echo ""
echo "[INFO] Finished : $(date)"
