#!/usr/bin/env bash
#SBATCH -p gpu
#SBATCH -A kumargroup
#SBATCH --gres=gpu:1
#SBATCH -c 8
#SBATCH --mem 48G
#SBATCH -t 1-00:00
#SBATCH -J train-vessel-unet
#SBATCH -o /cluster/projects/kumargroup/ch_fibrosis_analysis/trident/unet_runs/logs/slurm-%j.out
#SBATCH -e /cluster/projects/kumargroup/ch_fibrosis_analysis/trident/unet_runs/logs/slurm-%j.err
#SBATCH --export=NONE

# ==============================================================
#   UNet blood-vessel segmentation — patient-level k-fold CV
#   Cluster: hpc-for-health  |  Account: kumargroup
# ==============================================================

set -euo pipefail
umask 002

# ==============================================================
#   EDIT BEFORE SUBMITTING
# ==============================================================

REPO_DIR="/cluster/home/t140585uhn/wsi-trident-sean"
CONDA_ENV="methylcdm"

# Regex for extracting patient ID from slide directory name.
# Default: everything before the first underscore, e.g. "P001_slide1" -> "P001"
# Adjust to match your naming convention, e.g.:
#   r'^(TCGA-\w{2}-\w{4})' for TCGA slides
PATIENT_REGEX="^([^_]+)_"

# ==============================================================
#   END OF USER INPUTS
# ==============================================================

DATA_DIR="/cluster/projects/kumargroup/ch_fibrosis_analysis/trident"
OUT_DIR="${DATA_DIR}/unet_runs"

source ~/miniforge3/bin/activate
conda activate "${CONDA_ENV}"

mkdir -p "${OUT_DIR}/logs"

echo "[INFO] Job ID       : ${SLURM_JOB_ID}"
echo "[INFO] Node         : $(hostname)"
echo "[INFO] CPUs         : ${SLURM_CPUS_PER_TASK}"
echo "[INFO] GPUs         : ${SLURM_GPUS_ON_NODE:-1}"
echo "[INFO] Data dir     : ${DATA_DIR}"
echo "[INFO] Output dir   : ${OUT_DIR}"
echo "[INFO] Start        : $(date)"
echo ""

python "${REPO_DIR}/scripts/train_vessel_unet.py" \
    --data_dir      "${DATA_DIR}" \
    --out_dir       "${OUT_DIR}" \
    --patient_regex "${PATIENT_REGEX}" \
    --folds         5 \
    --epochs        50 \
    --batch_size    16 \
    --image_size    256 \
    --lr            1e-4 \
    --weight_decay  1e-5 \
    --encoder       resnet34 \
    --num_workers   "${SLURM_CPUS_PER_TASK}" \
    --patience      15 \
    --amp

echo ""
echo "[INFO] Finished : $(date)"
