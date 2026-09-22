#!/usr/bin/env bash
#SBATCH -p gpu
#SBATCH -A kumargroup_gpu
#SBATCH -c 8
#SBATCH --mem 64G
#SBATCH --gres gpu:1
#SBATCH -t 2-00:00
#SBATCH -J htan-he-feat
#SBATCH -o /cluster/projects/kumargroup/sean/data/HTAN_SPATIAL_PROTEOMICS/processed/logs/feat-slurm-%A_%a.out
#SBATCH -e /cluster/projects/kumargroup/sean/data/HTAN_SPATIAL_PROTEOMICS/processed/logs/feat-slurm-%A_%a.err
#SBATCH --array=0-3
#SBATCH --export=NONE

# ==============================================================
#   UNI v2 patch feature extraction for the HTAN spatial-proteomics
#   H&E slides.
#
#   Reads the coordinates already written by submit_htan_he_patch.sh
#   and encodes each patch; segmentation and patching are NOT re-run.
#   The patching block in the config below must stay identical to the
#   coords job -- TRIDENT derives the coords directory name from it,
#   so a single changed value silently points at a directory that
#   does not exist and every slide is skipped.
#
#   Prerequisites:
#     1. The coords stage has finished (20x_256px_0px_overlap/patches/)
#     2. Run:    python scripts/prepare_htan_he_lists.py --stage feat \
#                    --dims-tsv "${DATA_DIR}/hande_codex_dims.tsv"
#     3. Submit: sbatch --array=0-3 scripts/submit_htan_he_feat.sh
# ==============================================================

set -euo pipefail
umask 002

source ~/miniforge3/bin/activate
conda activate methylcdm_h100

# ---- EDIT THESE ----
DATA_DIR="/cluster/projects/kumargroup/sean/data/HTAN_SPATIAL_PROTEOMICS"
OUT_DIR="/cluster/projects/kumargroup/sean/data/HTAN_SPATIAL_PROTEOMICS/processed"
ENCODER="uni_v2"
BATCH_SIZE="64"
# --------------------

# Must match submit_htan_he_patch.sh exactly; see note above.
MIN_TISSUE_PROPORTION="0.1"

PROCESS_LIST="${OUT_DIR}/process_lists_feat/chunk_${SLURM_ARRAY_TASK_ID}.csv"

# ---- Sanity checks ----
if [[ ! -d "${DATA_DIR}" ]]; then
    echo "[ERROR] Data directory not found: ${DATA_DIR}" >&2
    exit 1
fi

if [[ ! -f "${PROCESS_LIST}" ]]; then
    echo "[ERROR] Process list not found: ${PROCESS_LIST}" >&2
    echo "[ERROR] Run 'python scripts/prepare_htan_he_lists.py --stage feat' first." >&2
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
CONFIG_PATH="${OUT_DIR}/config_feat_chunk${SLURM_ARRAY_TASK_ID}.yaml"
cat > "${CONFIG_PATH}" << YAML
io:
    wsi_dir: ${DATA_DIR}
    job_dir: ${OUT_DIR}
    process_list: ${PROCESS_LIST}
    wsi_extension:
        - .tif
        - .tiff
        - .qptiff
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
    min_tissue_proportion: ${MIN_TISSUE_PROPORTION}

features:
    encoder: ${ENCODER}
    batch_size: ${BATCH_SIZE}

system:
    device: cuda
YAML

# ---- Job info ----
echo "[INFO] Array task   : ${SLURM_ARRAY_TASK_ID} / ${SLURM_ARRAY_JOB_ID}"
echo "[INFO] Chunk        : ${SLURM_ARRAY_TASK_ID} (${slide_count} slides)"
echo "[INFO] Process list : ${PROCESS_LIST}"
echo "[INFO] Encoder      : ${ENCODER}"
echo "[INFO] Node         : $(hostname)"
echo "[INFO] Start        : $(date)"
echo ""

echo "[INFO] === ${ENCODER} feature extraction ==="
wsi-trident-adapter run --task feat --config "${CONFIG_PATH}"

echo ""
echo "[INFO] Finished : $(date)"
echo "[INFO] Features : ${OUT_DIR}/20x_256px_0px_overlap/features_${ENCODER}/"
