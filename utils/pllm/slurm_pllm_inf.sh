#!/bin/bash

#Usage: sbatch slurm_pllm_inf.sh args/flags...

#SBATCH --account=3dllms
#SBATCH --job-name=pllm_inf
#SBATCH --partition=mb-l40s,inv-ssheshap
#SBATCH --nodes=1
#SBATCH --nodelist=mbl40s-001,mbl40s-002,mbl40s-003,mbl40s-004,mbl40s-005,mbl40s-006,mbl40s-007,vl40s-005
#SBATCH --output=./slurm_logs/pllm_inf_%j.log
#SBATCH --error=./slurm_logs/pllm_inf_%j.log
#SBATCH --gres=gpu:1
#SBATCH --mem=48G
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
conda activate pointllm

REPO_PATH="/project/3dllms/melgin/LLaVA-3D_for_UPD-3D"
export PYTHONPATH="$REPO_PATH":$PYTHONPATH

python ./pointllm/eval/pllm_inf.py "$@"