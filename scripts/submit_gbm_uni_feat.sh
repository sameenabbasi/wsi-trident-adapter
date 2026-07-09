#!/usr/bin/env bash
#SBATCH -p gpu
#SBATCH -A kumargroup_gpu
#SBATCH -c 8
#SBATCH --mem 32G
#SBATCH --gres gpu:1
#SBATCH -t 2-00:00
#SBATCH -J gbm-uni-feat
#SBATCH -o /cluster/projects/kumargroup/sean/data/GBM/logs/slurm-%A.out
#SBATCH -e /cluster/projects/kumargroup/sean/data/GBM/logs/slurm-%A.err
#SBATCH --export=NONE

# ==============================================================
#   UNI v2 feature extraction for the GBM H&E slides (single GPU)
#   Cluster: hpc-for-health  |  Account: kumargroup_gpu
#
#   Processes only the H&E images in the source directory:
#     - HE__*.ome.tif      (individual per-case slides)
#     - WSI_HE__*.qptiff   (multi-case composite scans)
#   CODEX__* and WSI_CODEX__* (multiplex fluorescence) are skipped.
#
#   Submit:  sbatch scripts/submit_gbm_uni_feat.sh
#   Monitor: squeue -u $USER
# ==============================================================

set -euo pipefail
umask 002

source ~/miniforge3/bin/activate
conda activate methylcdm_h100

# ==============================================================
#   USER-DEFINED INPUTS
# ==============================================================

# Directory containing the source slides (flat — slides sit directly here)
WSI_DIR="/cluster/projects/kumargroup/codex/gbm/raw"

# Where the TRIDENT output tree (segmentation/patches/features) is written
OUT_DIR="/cluster/projects/kumargroup/sean/data/GBM"

# ==============================================================
#   END OF USER INPUTS
# ==============================================================

if [[ ! -d "${WSI_DIR}" ]]; then
    echo "[ERROR] WSI directory not found: ${WSI_DIR}" >&2
    exit 1
fi

# ---- Asset paths (hpc-for-health profile) ----
ASSETS_ROOT="/cluster/projects/kumargroup/wsi-trident-adapter-assets"
export TRIDENT_HOME="${ASSETS_ROOT}/weights/trident"
export TORCH_HOME="${ASSETS_ROOT}/weights/torch"
export HF_HOME="${ASSETS_ROOT}/weights/huggingface"

# ---- Create output and log dirs ----
mkdir -p "${OUT_DIR}"
mkdir -p "${OUT_DIR}/logs"

# ---- Write process list ----
# H&E files only: basenames starting with "HE__" or "WSI_HE__".
# This includes the per-case .ome.tif slides and the composite .qptiff
# scans, and excludes CODEX__* / WSI_CODEX__* by construction.
PROCESS_LIST="${OUT_DIR}/process_list.csv"
printf 'wsi\n' > "${PROCESS_LIST}"
while IFS= read -r wsi; do
    printf '%s\n' "$(basename "${wsi}")" >> "${PROCESS_LIST}"
done < <(
    find "${WSI_DIR}" -maxdepth 1 -type f \
        \( -name 'HE__*.tif' -o -name 'HE__*.tiff' -o -name 'WSI_HE__*.qptiff' \) \
        2>/dev/null | sort
)

slide_count=$(( $(wc -l < "${PROCESS_LIST}") - 1 ))
if [[ ${slide_count} -le 0 ]]; then
    echo "[ERROR] No H&E slides found in ${WSI_DIR}" >&2
    exit 1
fi

# ---- Write config ----
CONFIG_PATH="${OUT_DIR}/config.yaml"
cat > "${CONFIG_PATH}" << YAML
io:
    wsi_dir: "${WSI_DIR}"
    job_dir: ${OUT_DIR}
    process_list: ${PROCESS_LIST}
    wsi_extension:
        - .tif
        - .tiff
        - .qptiff

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
echo "[INFO] Job          : ${SLURM_JOB_ID}"
echo "[INFO] WSI dir      : ${WSI_DIR}"
echo "[INFO] Out dir      : ${OUT_DIR}"
echo "[INFO] Process list : ${PROCESS_LIST} (${slide_count} H&E slides)"
echo "[INFO] Config       : ${CONFIG_PATH}"
echo "[INFO] Node         : $(hostname)"
echo "[INFO] Start        : $(date)"
echo ""

# ---- Run full pipeline (seg -> patch -> feat) ----
wsi-trident-adapter run --task all --config "${CONFIG_PATH}"

echo ""
echo "[INFO] Finished : $(date)"
