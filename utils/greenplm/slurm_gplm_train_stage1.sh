#!/bin/bash
#SBATCH --account=3dllms
##SBATCH --partition=mb-l40s
#SBATCH --partition=mb-a30
#SBATCH --job-name=gplm_train_stage1
#SBATCH --output=./slurm_logs/gplm_train_stage1_%j.out
#SBATCH --error=./slurm_logs/gplm_train_stage1_%j.out
#SBATCH --gres=gpu:1
#SBATCH --mem=64G
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
conda activate greenplm

export WANDB_MODE=disabled

# Experiment name → checkpoint dir suffix (stage_N_<EXP_NAME>).
# Usage: sbatch slurm_gplm_train_stage1.sh <experiment_name>
#    or: EXP_NAME=<experiment_name> sbatch ...
if [[ -n "${1:-}" ]]; then
    export EXP_NAME="$1"
fi
: "${EXP_NAME:?Pass experiment name as arg1 or set EXP_NAME}"
echo "EXP_NAME=${EXP_NAME}  (checkpoints → ./checkpoints/stage_1_${EXP_NAME})"

bash ./release/paper/scripts/train/1.sh