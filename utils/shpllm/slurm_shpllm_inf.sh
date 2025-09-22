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

#This ensures conda activate works in non-interactive shells.
#running conda init every time won't work. Just make sure to source the correct conda.sh
if [ -n "$CONDA_INSTALL_PATH" ]; then
    source $CONDA_INSTALL_PATH/etc/profile.d/conda.sh
else
    echo WARNING: CONDA_INSTALL_PATH is not set. Using default path.
    source /project/3dllms/melgin/conda/etc/profile.d/conda.sh
fi

#Activate the conda environment just in case you didn't already in the command line.
conda activate shapellm_h100

python ./shpllm_inf.py "$@"