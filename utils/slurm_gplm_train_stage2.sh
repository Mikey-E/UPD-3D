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

export WANDB_MODE=disabled
bash ./release/paper/scripts/train/2.sh