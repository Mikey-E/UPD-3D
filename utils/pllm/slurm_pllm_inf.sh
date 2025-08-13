#!/bin/bash

#SBATCH --account=3dllms
#SBATCH --job-name=pllm_inf
#SBATCH --partition=mb-l40s,inv-ssheshap
#SBATCH --nodes=1
#SBATCH --nodelist=mbl40s-001,mbl40s-002,mbl40s-003,mbl40s-004,mbl40s-005,mbl40s-006,mbl40s-007,vl40s-005
#SBATCH --output=pllm_inf_%j.log
#SBATCH --error=pllm_inf_%j.log
#SBATCH --gres=gpu:1
#SBATCH --mem=48G
#SBATCH --time=7-00:00:00

#This ensures conda activate works in non-interactive shells.
#running conda init every time won't work. Just make sure to source the correct conda.sh
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

python ./pointllm/eval/pllm_inf.py "$@"