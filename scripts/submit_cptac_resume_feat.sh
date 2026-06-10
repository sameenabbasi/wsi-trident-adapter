#!/usr/bin/env bash
#SBATCH -p gpu
#SBATCH -A kumargroup_gpu
#SBATCH -c 8
#SBATCH --mem 32G
#SBATCH --gres gpu:1
#SBATCH -t 2-00:00
#SBATCH -J cptac-resume-feat
#SBATCH -o /cluster/projects/kumargroup/CPTAC_data/trident_output/logs/slurm-%A_%a.out
#SBATCH -e /cluster/projects/kumargroup/CPTAC_data/trident_output/logs/slurm-%A_%a.err
#SBATCH --array=0-63
#SBATCH --export=NONE

# ==============================================================
#   Resume UNI v2 feature extraction — 8 cohorts × 8 GPUs each
#   Array index: cohort = task_id / 8,  chunk = task_id % 8
#
#   Prerequisites:
#     1. Cancel the old job:   scancel <JOBID>
#     2. Build resume lists:   bash prepare_resume_lists.sh
#     3. Submit this job:      sbatch submit_cptac_resume_feat.sh
# ==============================================================

set -euo pipefail
umask 002

source ~/miniforge3/bin/activate
conda activate methylcdm_h100

WSI_BASE="/cluster/projects/kumargroup/CPTAC_data/Histology_by_CT"
OUT_BASE="/cluster/projects/kumargroup/CPTAC_data/trident_output"
N_CHUNKS=8

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

COHORT_IDX=$(( SLURM_ARRAY_TASK_ID / N_CHUNKS ))
CHUNK_IDX=$(( SLURM_ARRAY_TASK_ID % N_CHUNKS ))

COHORT="${COHORTS[$COHORT_IDX]}"
WSI_DIR="${WSI_BASE}/${COHORT}"
JOB_DIR="${OUT_BASE}/${COHORT}"
PROCESS_LIST="${JOB_DIR}/resume_lists/chunk_${CHUNK_IDX}.csv"

# ---- Sanity checks ----
if [[ ! -d "${WSI_DIR}" ]]; then
    echo "[ERROR] WSI directory not found: ${WSI_DIR}" >&2
    exit 1
fi

if [[ ! -f "${PROCESS_LIST}" ]]; then
    echo "[ERROR] Process list not found: ${PROCESS_LIST}" >&2
    echo "[ERROR] Run prepare_resume_lists.sh first." >&2
    exit 1
fi

# If the prepare script wrote an empty sentinel (header only), nothing to do
slide_count=$(( $(wc -l < "${PROCESS_LIST}") - 1 ))
if [[ ${slide_count} -le 0 ]]; then
    echo "[INFO]  No remaining slides for ${COHORT} chunk ${CHUNK_IDX}, exiting."
    exit 0
fi

# ---- Asset paths (hpc-for-health profile) ----
ASSETS_ROOT="/cluster/projects/kumargroup/wsi-trident-adapter-assets"
export TRIDENT_HOME="${ASSETS_ROOT}/weights/trident"
export TORCH_HOME="${ASSETS_ROOT}/weights/torch"
export HF_HOME="${ASSETS_ROOT}/weights/huggingface"

mkdir -p "${JOB_DIR}" "${OUT_BASE}/logs"

# ---- Per-chunk config ----
CONFIG_PATH="${JOB_DIR}/resume_config_chunk${CHUNK_IDX}.yaml"
cat > "${CONFIG_PATH}" << YAML
io:
    wsi_dir: ${WSI_DIR}
    job_dir: ${JOB_DIR}
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
echo "[INFO] Cohort       : ${COHORT}  (index ${COHORT_IDX})"
echo "[INFO] Chunk        : ${CHUNK_IDX} / $(( N_CHUNKS - 1 ))  (${slide_count} slides)"
echo "[INFO] Process list : ${PROCESS_LIST}"
echo "[INFO] Node         : $(hostname)"
echo "[INFO] Start        : $(date)"
echo ""

wsi-trident-adapter run --task feat --config "${CONFIG_PATH}"

echo ""
echo "[INFO] Finished : $(date)"
