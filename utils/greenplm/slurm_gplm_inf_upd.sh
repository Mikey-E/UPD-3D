#!/bin/bash
#SBATCH --account=3dllms
#SBATCH --partition=mb-a30
#SBATCH --job-name=gplm_inf_upd
#SBATCH --output=gplm_inf_upd_%j.out
#SBATCH --error=gplm_inf_upd_%j.out
#SBATCH --gres=gpu:1
#SBATCH --mem=16G
#SBATCH --time=7-00:00:00

#This ensures conda activate works in non-interactive shells.
#running conda init every time won't work. Just make sure to source the correct conda.sh
if [ -n "$CONDA_INSTALL_PATH" ]; then
    source $CONDA_INSTALL_PATH/etc/profile.d/conda.sh
else
    echo WARNING: CONDA_INSTALL_PATH is not set. Using default path.
    source /project/3dllms/melgin/conda/etc/profile.d/conda.sh
fi

#Activate the conda environment just in case you didn't already in the command line.
conda activate greenplm

# Accept subfolder argument from command line
SUBFOLDER_ARG="$1"

bash gplm_inf_upd.sh "$SUBFOLDER_ARG"