#!/bin/bash

#Usage: sbatch slurm_minigpt-3d_prog.sh args/flags...

#SBATCH --account=3dllms
#SBATCH --job-name=mgpt3d_inf
#SBATCH --partition=mb-a30
#SBATCH --output=minigpt3d_inf_%j.log
#SBATCH --error=minigpt3d_inf_%j.log
#SBATCH --gres=gpu:1
#SBATCH --mem=16G
#SBATCH --time=01-23:59:59

#This ensures conda activate works in non-interactive shells.
#running conda init every time won't work. Just make sure to source the correct conda.sh
source /project/3dllms/melgin/conda/etc/profile.d/conda.sh

#Activate the conda environment just in case you didn't already in the command line.
conda activate minigpt-3d

python ./minigpt-3d_prog.py "$@"