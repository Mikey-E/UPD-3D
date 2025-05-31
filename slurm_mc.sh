#!/bin/bash
#This script is for making a job submission for the multiple-choice question generating file

#SBATCH --account=3dllms
#SBATCH --time=23:00:00
#SBATCH --partition=non-investor

python make_mc_text.py $1