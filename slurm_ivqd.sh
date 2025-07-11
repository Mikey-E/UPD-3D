#!/bin/bash
#This script is for making a job submission for the ivqd question generating file
#Example use: sbatch slurm_ivqd.sh args/flags...

#SBATCH --account=3dllms
#SBATCH --time=23:00:00
#SBATCH --partition=non-investor

# Check if OPENAI_API_KEY is set
if [ -z "$OPENAI_API_KEY" ]; then
    echo "Error: OPENAI_API_KEY environment variable is not set."
    exit 1
fi

#This ensures conda activate works in non-interactive shells.
#running conda init every time won't work. Just make sure to source the correct conda.sh
source /project/3dllms/melgin/conda/etc/profile.d/conda.sh

# Activate the conda environment just in case it wasn't already done
conda activate upd-3d

python make_ivqd_base_text.py $1