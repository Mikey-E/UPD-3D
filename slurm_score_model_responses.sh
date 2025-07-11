#!/bin/bash
#This script is for making a job submission for scoring model responses
#Example use: sbatch slurm_score_model_responses.sh args/flags...

#SBATCH --account=3dllms
#SBATCH --partition=non-investor
#SBATCH --job-name=score_model_responses
#SBATCH --output=score_model_responses_%j.out
#SBATCH --error=score_model_responses_%j.out
#SBATCH --mem=16G
#SBATCH --time=7-00:00:00

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

python score_model_responses.py "$@"