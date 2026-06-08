#!/usr/bin/env bash
#SBATCH -p gpu
#SBATCH -A kumargroup_gpu
#SBATCH -c 8
#SBATCH --mem 32G
#SBATCH --gres gpu:1
#SBATCH -t 2-00:00
#SBATCH -J cptac-uni-feat
#SBATCH -o /cluster/projects/kumargroup/CPTAC_data/trident_output/logs/slurm-%A_%a.out
#SBATCH -e /cluster/projects/kumargroup/CPTAC_data/trident_output/logs/slurm-%A_%a.err
#SBATCH --array=0-7
#SBATCH --export=NONE

# ==============================================================
#   UNI v2 feature extraction for 8 CPTAC cohorts (array job)
#   Cluster: hpc-for-health  |  Account: kumargroup_gpu
#
#   Submit:  sbatch submit_cptac_uni_feat.sh
#   Monitor: squeue -u $USER
# ==============================================================

set -euo pipefail
umask 002

# ==============================================================
#   USER-DEFINED INPUTS  —  EDIT BEFORE SUBMITTING
# ==============================================================

# Python environment
source ~/miniforge3/bin/activate
conda activate methylcdm_h100

# Base directory containing one subfolder per cohort
#   Expected layout:  WSI_BASE/<COHORT>/*.svs (flat — not nested in case dirs)
#   If your slides are in case subdirectories, see note at the bottom.
WSI_BASE="/cluster/projects/kumargroup/CPTAC_data/Histology_by_CT"

# Where outputs (patches, masks, features) will be written
OUT_BASE="/cluster/projects/kumargroup/CPTAC_data/trident_output"

# ==============================================================
#   END OF USER INPUTS
# ==============================================================

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

COHORT="${COHORTS[$SLURM_ARRAY_TASK_ID]}"
WSI_DIR="${WSI_BASE}/${COHORT}"
JOB_DIR="${OUT_BASE}/${COHORT}"

# ---- Sanity check ----
if ! command -v wsi-trident-adapter &> /dev/null; then
    echo "[ERROR] wsi-trident-adapter not found — activate your environment first." >&2
    exit 1
fi

if [[ ! -d "${WSI_DIR}" ]]; then
    echo "[ERROR] WSI directory not found: ${WSI_DIR}" >&2
    exit 1
fi

# ---- Asset paths (hpc-for-health profile) ----
WSI_ASSETS_ROOT="$(wsi-trident-adapter profile root)"
export TRIDENT_HOME="${WSI_ASSETS_ROOT}/weights/trident"
export TORCH_HOME="${WSI_ASSETS_ROOT}/weights/torch"
export HF_HOME="${WSI_ASSETS_ROOT}/weights/huggingface"

# ---- Create output and log dirs ----
mkdir -p "${JOB_DIR}"
mkdir -p "${OUT_BASE}/logs"

# ---- Write per-cohort config to a temp file ----
CONFIG_PATH="${JOB_DIR}/config.yaml"
cat > "${CONFIG_PATH}" << YAML
io:
    wsi_dir: ${WSI_DIR}
    job_dir: ${JOB_DIR}
    process_list: null
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
echo "[INFO] Cohort       : ${COHORT}"
echo "[INFO] WSI dir      : ${WSI_DIR}"
echo "[INFO] Job dir      : ${JOB_DIR}"
echo "[INFO] Config       : ${CONFIG_PATH}"
echo "[INFO] Node         : $(hostname)"
echo "[INFO] Start        : $(date)"
echo ""

# ---- Run full pipeline (seg -> patch -> feat) ----
wsi-trident-adapter run --task all --config "${CONFIG_PATH}"

echo ""
echo "[INFO] Finished : $(date)"

# ==============================================================
#   NOTE: If slides are nested in case subdirectories, e.g.:
#     CPTAC-AML/C3L-00001/C3L-00001.svs
#   the adapter only scans the top level of wsi_dir and will find
#   no slides. In that case, either:
#     (a) set WSI_DIR to the individual case dir and add a process_list, or
#     (b) create a flat symlink directory pointing to all slides.
# ==============================================================
