#!/bin/bash
#SBATCH -p gpu
#SBATCH -c 8
#SBATCH --mem 16G
#SBATCH --gres gpu:1
#SBATCH -A kumargroup_gpu
#SBATCH -t 3-00:00
#SBATCH -J extract_features
#SBATCH -o TODO
#SBATCH -e TODO
#SBATCH --mail-type=ALL
#SBATCH --mail-user=TODO

###########################################################################################################

# Fill in these

# Path to your config file, example: configs/config_template.yaml.
PATH_TO_CONFIG="TODO"

# Task you want to perform, available options: seg, patch, feat, all.
TASK="TODO"

###########################################################################################################

# You're all set.
# Feel free to take a look at what's below. But you do not need to change anything.

###########################################################################################################

# Setup temporary directory for WSI images. 
# Do NOT change this unless you know what you are doing!!!

# Files are typically stored on hard drives in slurm clusters, which could be slow if frequently accessed.
# Caching WSIs locally on the gpu cluster could speed up access.

# If you really have to change this, make extreme caution since this code will automatically clean anything
# inside the tmp directory

export WSI_TMP_DIR="/tmp/wsi_tmp_dir_$(date +%Y%m%d%H%M%S)"

init_wsi_tmp_dir() {
    mkdir -p $WSI_TMP_DIR
}

cleanup_wsi_tmp_dir() {
    trap 'rm -rf -- "${WSI_TMP_DIR}"' EXIT 
}

###########################################################################################################

# Setup PyTorch and Huggingface cache directory
# Do NOT change this unless you know what you are doing!!!

export HF_HOME="/cluster/projects/kumargroup/hayden/wsi_pipeline_model_weights/huggingface"
export TORCH_HOME="/cluster/projects/kumargroup/hayden/wsi_pipeline_model_weights/torch"

###########################################################################################################

# Main Script

init_wsi_tmp_dir

source .venv/bin/activate
export CUDA_VISIBLE_DEVICES=0

python3 src/run.py \
    --config "${PATH_TO_CONFIG}" \
    --task "${TASK}"

cleanup_wsi_tmp_dir

###########################################################################################################
