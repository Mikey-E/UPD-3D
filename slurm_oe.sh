#!/bin/bash
#This script is for making a job submission for the open-ended question generating file

#SBATCH --account=3dllms
#SBATCH --time=23:00:00
#SBATCH --partition=non-investor

python make_oe_text.py $1