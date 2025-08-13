#!/bin/bash
#SBATCH --account=3dllms
#SBATCH --partition=mb-a30
#SBATCH --job-name=gplm_inf_upd
#SBATCH --output=gplm_inf_upd_%j.out
#SBATCH --error=gplm_inf_upd_%j.out
#SBATCH --gres=gpu:1
#SBATCH --mem=16G
#SBATCH --time=7-00:00:00

#This ensures "conda activate <env>" works in non-interactive shells.
#(running "conda init" every time won't work.)
if [ -n "$CONDA_INSTALL_PATH" ]; then
    CONDA_SH=$CONDA_INSTALL_PATH/etc/profile.d/conda.sh
    if [ ! -e "$CONDA_SH" ]; then
        echo "ERROR: $CONDA_SH does not exist."
        exit 1
    fi
    source "$CONDA_SH"
else
    CONDA_SH=/project/3dllms/melgin/conda/etc/profile.d/conda.sh
    echo "WARNING: CONDA_INSTALL_PATH is not set. Trying $CONDA_SH"
    if [ ! -e "$CONDA_SH" ]; then
        echo "ERROR: $CONDA_SH does not exist."
        exit 1
    fi
    source "$CONDA_SH"
fi
# Now the activation should work
conda activate greenplm

# Accept subfolder argument from command line
SUBFOLDER_ARG="$1"

bash gplm_inf_upd.sh "$SUBFOLDER_ARG"