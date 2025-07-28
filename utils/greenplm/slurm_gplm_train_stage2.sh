#!/bin/bash
#SBATCH --account=3dllms
##SBATCH --partition=mb-l40s
#SBATCH --partition=mb-a30
#SBATCH --job-name=gplm_train_stage2
#SBATCH --output=gplm_train_stage2_%j.out
#SBATCH --error=gplm_train_stage2_%j.out
#SBATCH --gres=gpu:1
#SBATCH --mem=64G
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
conda activate greenplm

export WANDB_MODE=disabled
bash ./release/paper/scripts/train/2.sh