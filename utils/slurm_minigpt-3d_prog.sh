#!/bin/bash

# Usage: sbatch slurm_minigpt-3d_prog.sh args/flags...

#SBATCH --account=3dllms
#SBATCH --job-name=mgpt3d
#SBATCH --partition=mb-l40s
#SBATCH --output=minigpt3d_%j.log
#SBATCH --error=minigpt3d_%j.log
#SBATCH --gres=gpu:1
#SBATCH --mem=16G
#SBATCH --time=01-23:59:59

if [ "$#" -ne 1 ]; then
    echo "Usage: sbatch run_minigpt3d.slurm <folder_name>"
    exit 1
fi

# Load the necessary modules - this may not work, the conda environment may have to be activated in the command line before you run this script
conda init
conda activate minigpt_3d

python ./minigpt-3d_prog.py $1