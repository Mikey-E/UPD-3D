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

python score_model_responses.py "$@"