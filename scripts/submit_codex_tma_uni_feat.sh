#!/usr/bin/env bash
#SBATCH -p gpu
#SBATCH -A kumargroup_gpu
#SBATCH -c 8
#SBATCH --mem 32G
#SBATCH --gres gpu:1
#SBATCH -t 1-00:00
#SBATCH -J codex-tma-uni-feat
#SBATCH -o /cluster/projects/kumargroup/sean/data/CODEX_TMA/logs/slurm-%A_%a.out
#SBATCH -e /cluster/projects/kumargroup/sean/data/CODEX_TMA/logs/slurm-%A_%a.err
#SBATCH --array=0-3
#SBATCH --export=NONE

# ==============================================================
#   UNI v2 feature extraction for the CODEX processed H&E TMAs
#   Cluster: hpc-for-health  |  Account: kumargroup_gpu
#
#   Source layout: SRC_ROOT contains 4 TMA folders, each holding
#   dearrayed cores named reg###_X01_Y01_Z##.tif. Each core is
#   treated as its own slide; the pipeline segments -> patches
#   (256 px @ 20x) -> extracts UNI v2 features per patch.
#
#   Runs as a SLURM job array: one array task per TMA folder, each
#   on its own GPU into its own output tree. The slide lister does
#   not recurse into subfolders and reg### numbers may repeat across
#   folders, so folders must be processed independently.
#
#   Submit:  sbatch scripts/submit_codex_tma_uni_feat.sh
#   Monitor: squeue -u $USER
# ==============================================================

set -euo pipefail
umask 002

source ~/miniforge3/bin/activate
conda activate methylcdm_h100

# ==============================================================
#   USER-DEFINED INPUTS
# ==============================================================

# Root directory containing the four TMA folders (flat .tif cores each)
SRC_ROOT="/cluster/projects/kumargroup/codex/processed_hande"

# TMA folders to process (one array task each; keep --array in sync)
TMAS=(
    CRC_TMA_A
    CRC_TMA_B
    Multi-tumor_TMA
    Tonsil
)

# Where the TRIDENT output trees are written (one subdir per TMA)
OUT_ROOT="/cluster/projects/kumargroup/sean/data/CODEX_TMA"

# Microns-per-pixel for the cores (Keyence-based CODEX @ 20x/0.75).
# The generic ImageWSI loader does NOT parse embedded pixel size, so
# mpp is supplied explicitly via the process-list 'mpp' column below.
MPP="0.37744"

# Minimum tissue proportion per patch (patches below this are dropped)
MIN_TISSUE_PROPORTION="0.5"

# ==============================================================
#   END OF USER INPUTS
# ==============================================================

if [[ ! -d "${SRC_ROOT}" ]]; then
    echo "[ERROR] Source root not found: ${SRC_ROOT}" >&2
    exit 1
fi

# ---- Select this array task's TMA folder ----
if [[ -z "${SLURM_ARRAY_TASK_ID:-}" ]]; then
    echo "[ERROR] SLURM_ARRAY_TASK_ID unset; submit with 'sbatch' (job array)." >&2
    exit 1
fi
if (( SLURM_ARRAY_TASK_ID >= ${#TMAS[@]} )); then
    echo "[ERROR] Array index ${SLURM_ARRAY_TASK_ID} out of range for ${#TMAS[@]} TMAs." >&2
    exit 1
fi
tma="${TMAS[${SLURM_ARRAY_TASK_ID}]}"

WSI_DIR="${SRC_ROOT}/${tma}"
OUT_DIR="${OUT_ROOT}/${tma}"

# ---- Asset paths (hpc-for-health profile) ----
ASSETS_ROOT="/cluster/projects/kumargroup/wsi-trident-adapter-assets"
export TRIDENT_HOME="${ASSETS_ROOT}/weights/trident"
export TORCH_HOME="${ASSETS_ROOT}/weights/torch"
export HF_HOME="${ASSETS_ROOT}/weights/huggingface"

mkdir -p "${OUT_ROOT}/logs"

echo "[INFO] Job       : ${SLURM_ARRAY_JOB_ID:-?}_${SLURM_ARRAY_TASK_ID}"
echo "[INFO] TMA       : ${tma}"
echo "[INFO] WSI dir   : ${WSI_DIR}"
echo "[INFO] Out dir   : ${OUT_DIR}"
echo "[INFO] MPP       : ${MPP}"
echo "[INFO] Node      : $(hostname)"
echo "[INFO] Start     : $(date)"
echo ""

if [[ ! -d "${WSI_DIR}" ]]; then
    echo "[ERROR] Folder not found: ${WSI_DIR}" >&2
    exit 1
fi

mkdir -p "${OUT_DIR}/logs"

# ---- Write process list (wsi + mpp) ----
PROCESS_LIST="${OUT_DIR}/process_list.csv"
printf 'wsi,mpp\n' > "${PROCESS_LIST}"
while IFS= read -r wsi; do
    printf '%s,%s\n' "$(basename "${wsi}")" "${MPP}" >> "${PROCESS_LIST}"
done < <(
    find "${WSI_DIR}" -maxdepth 1 -type f \
        \( -name '*.tif' -o -name '*.tiff' \) \
        -not -name '._*' 2>/dev/null | sort
)

slide_count=$(( $(wc -l < "${PROCESS_LIST}") - 1 ))
if [[ ${slide_count} -le 0 ]]; then
    echo "[ERROR] No .tif cores found in ${WSI_DIR}" >&2
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
    encoder: uni_v2
    batch_size: 64

system:
    device: cuda
YAML

echo "[INFO] Cores     : ${slide_count}"
echo "[INFO] Config    : ${CONFIG_PATH}"
echo ""

# ---- Run full pipeline (seg -> patch -> feat) ----
wsi-trident-adapter run --task all --config "${CONFIG_PATH}"

echo ""
echo "[INFO] Done ${tma} : $(date)"
