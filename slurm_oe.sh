#!/bin/bash
#This script is for making a job submission for the open-ended question generating file

#SBATCH --account=3dllms
#SBATCH --time=23:00:00
#SBATCH --partition=non-investor

# Check if OPENAI_API_KEY is set
if [ -z "$OPENAI_API_KEY" ]; then
    echo "Error: OPENAI_API_KEY environment variable is not set."
    exit 1
fi

python make_oe_text.py $1