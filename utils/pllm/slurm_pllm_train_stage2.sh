#!/bin/bash
#SBATCH --account=3dllms
##SBATCH --partition=mb-h100
#SBATCH --partition=mb-l40s
##SBATCH --partition=mb-a30
#SBATCH --job-name=pllm_train_stage2
#SBATCH --output=pllm_train_stage2_%j.out
#SBATCH --error=pllm_train_stage2_%j.out
#SBATCH --gres=gpu:8
#SBATCH --mem=699G
#SBATCH --time=7-00:00:00

#This ensures "conda activate <env>" works in non-interactive shells.
#(running "conda init" every time won't work.)
if [ -n "$CONDA_INSTALL_PATH" ]; then
    CONDA_SH=$CONDA_INSTALL_PATH/etc/profile.d/conda.sh
    if [ ! -e "$CONDA_SH" ]; then
        echo "ERROR: $CONDA_SH does not exist."
        exit 1
    fi
    source "$CONDA_SH"
else
    CONDA_SH=/project/3dllms/melgin/conda/etc/profile.d/conda.sh
    echo "WARNING: CONDA_INSTALL_PATH is not set. Trying $CONDA_SH"
    if [ ! -e "$CONDA_SH" ]; then
        echo "ERROR: $CONDA_SH does not exist."
        exit 1
    fi
    source "$CONDA_SH"
fi

#Activate the conda environment just in case you didn't already in the command line.
conda activate pointllm

export PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:21
time scripts/PointLLM_train_stage2.sh