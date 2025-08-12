#!/bin/bash
#SBATCH --account=3dllms
#SBATCH --partition=mb-h100
#SBATCH --job-name=shpllm_pretrain_h100
#SBATCH --output=shpllm_pretrain_%j.out
#SBATCH --error=shpllm_pretrain_%j.out
#SBATCH --gres=gpu:1
#SBATCH --mem=96G
#SBATCH --time=7-00:00:00

##SBATCH --exclusive

#This ensures conda activate works in non-interactive shells.
#running conda init every time won't work. Just make sure to source the correct conda.sh
source /project/3dllms/melgin/conda/etc/profile.d/conda.sh

#Activate the conda environment just in case you didn't already in the command line.
conda activate shapellm_h100

#export PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:21 #most lenient

sh scripts/pretrain.sh