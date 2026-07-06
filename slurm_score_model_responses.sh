#!/bin/bash
#This script is for making a job submission for scoring model responses
#Example use: sbatch slurm_score_model_responses.sh args/flags...

#SBATCH --account=3dllms
#SBATCH --partition=mb
#SBATCH --job-name=score_model_responses
#SBATCH --output=./slurm_logs/score_model_responses_%j.out
#SBATCH --error=./slurm_logs/score_model_responses_%j.out
#SBATCH --mem=16G
#SBATCH --time=7-00:00:00
#SBATCH --export=NIL

# Optional sleep duration in seconds (default: 0). Pass via --sleep to avoid env export.
SLEEP_SECONDS=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --sleep)
            SLEEP_SECONDS="$2"
            shift 2
            ;;
        *)
            break
            ;;
    esac
done

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

# Sleep before starting work (for staggering jobs)
if [ "$SLEEP_SECONDS" -gt 0 ]; then
    echo "Sleeping for $SLEEP_SECONDS seconds before starting..."
    sleep "$SLEEP_SECONDS"
    echo "Sleep completed. Starting work now."
fi

python score_model_responses.py "$@"