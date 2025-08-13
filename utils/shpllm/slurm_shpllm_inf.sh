#!/bin/bash

#Usage: sbatch slurm_shpllm_inf.sh args/flags...

#SBATCH --account=3dllms
#SBATCH --job-name=shpllm_inf
#SBATCH --partition=mb-h100
#SBATCH --nodes=1
#SBATCH --output=./slurm_logs/shpllm_inf_%j.log
#SBATCH --error=./slurm_logs/shpllm_inf_%j.log
#SBATCH --gres=gpu:1
#SBATCH --mem=96G
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
# Now the activation should work
conda activate shapellm_h100

python ./shpllm_inf.py "$@"