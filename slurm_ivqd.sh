#!/bin/bash
#This script is for making a job submission for the ivqd question generating file
#Example use: sbatch slurm_ivqd.sh args/flags...

#SBATCH --account=3dllms
#SBATCH --time=23:00:00
#SBATCH --partition=non-investor

# Ensure OPENAI_API_KEY is set; if missing, try sourcing export script
if [ -z "$OPENAI_API_KEY" ]; then
    if [ -f ./export_openai_api_key.sh ]; then
        echo "OPENAI_API_KEY not set; sourcing ./export_openai_api_key.sh"
        # shellcheck source=export_openai_api_key.sh
        . ./export_openai_api_key.sh
    elif [ -f "$HOME/export_openai_api_key.sh" ]; then
        echo "OPENAI_API_KEY not set; sourcing $HOME/export_openai_api_key.sh"
        # shellcheck source=$HOME/export_openai_api_key.sh
        . "$HOME/export_openai_api_key.sh"
    fi
fi
if [ -z "$OPENAI_API_KEY" ]; then
    echo "ERROR: OPENAI_API_KEY environment variable is not set."
    exit 1
fi

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
conda activate upd-3d

python make_ivqd_base_text.py $1