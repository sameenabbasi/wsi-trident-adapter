#!/bin/bash
#SBATCH -p gpu
#SBATCH -c 4
#SBATCH --mem 16G
#SBATCH --gres gpu:1
#SBATCH -A kumargroup_gpu
#SBATCH -t 1:00:00
#SBATCH -J WSI-Pipeline-Example
#SBATCH -o example/out/stdout.txt
#SBATCH -e example/out/stderr.txt

###########################################################################################################

# Fill in these

# Path to your config file, example: configs/config_template.yaml.

PATH_TO_CONFIG="example/config.yaml"

# Task you want to perform, available options: seg, patch, feat, all.
# seg: segmentation
# patch: patching (requires segmentation to be completed in the same job directory)
# feat: feature extraction (requires patching to be completed in the same job directory)
# all: everything

TASK="all"

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

# export WSI_TMP_DIR="/tmp/wsi_tmp_dir_$(date +%Y%m%d%H%M%S)"

# mkdir -p $WSI_TMP_DIR
# trap 'rm -rf -- "${WSI_TMP_DIR}"' EXIT 

###########################################################################################################

# Setup checkpoints and cache directory
# Do NOT change this unless you know what you are doing!!!

export HF_HOME="/cluster/projects/kumargroup/hayden/wsi_pipeline_model_weights/huggingface"
export TORCH_HOME="/cluster/projects/kumargroup/hayden/wsi_pipeline_model_weights/torch"
export TRIDENT_HOME="/cluster/projects/kumargroup/hayden/wsi_pipeline_model_weights/trident"
export LOCAL_CKPTS="/cluster/projects/kumargroup/hayden/wsi_pipeline_model_weights/local_ckpts"

###########################################################################################################

# Main Script

source .venv/bin/activate
export CUDA_VISIBLE_DEVICES=0

python3 wsi-pipeline/run.py \
    --config "${PATH_TO_CONFIG}" \
    --task "${TASK}"

###########################################################################################################
