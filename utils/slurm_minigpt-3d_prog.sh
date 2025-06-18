#!/bin/bash

# Usage: sbatch minigpt-3d_prog.slurm args/flags...

#SBATCH --account=3dllms
#SBATCH --job-name=mgpt3d
#SBATCH --partition=mb-l40s
#SBATCH --output=mgpt3d_%j.out
#SBATCH --error=mgpt3d_%j.err
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