#!/bin/bash
#SBATCH -p gpu
#SBATCH -c 8
#SBATCH --mem 32G
#SBATCH --gres gpu:1
#SBATCH -A kumargroup_gpu
#SBATCH -t 1-00:00
#SBATCH -J example
#SBATCH -o out/stdout.txt
#SBATCH -e out/stderr.txt

# ===== Environment setup =====
export HF_HOME="/cluster/projects/kumargroup/hayden/wsi_pipeline_model_weights/huggingface"
export TORCH_HOME="/cluster/projects/kumargroup/hayden/wsi_pipeline_model_weights/torch"
export TRIDENT_HOME="/cluster/projects/kumargroup/hayden/wsi_pipeline_model_weights/trident"
# ==============================

wsi-trident-adapter extract --config "example/config.yaml"