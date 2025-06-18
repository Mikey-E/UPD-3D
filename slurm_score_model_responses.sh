#!/bin/bash
#This script is for making a job submission for scoring model responses

#SBATCH --account=3dllms
#SBATCH --time=23:00:00
#SBATCH --partition=non-investor

python score_model_responses.py $1