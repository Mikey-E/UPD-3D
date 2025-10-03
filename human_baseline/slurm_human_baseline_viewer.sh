#!/bin/bash
#SBATCH --account=3dllms
#SBATCH --time=7-00:00:00
#SBATCH --partition=non-investor
#SBATCH --output=./slurm_logs/slurm_human_baseline_viewer_%j.log
#SBATCH --error=./slurm_logs/slurm_human_baseline_viewer_%j.log
#SBATCH --mem=400G
#SBATCH --mail-type=ALL
#SBATCH --mail-user=melgin@uwyo.edu

echo "=== SLURM Job Starting ==="
echo "Job ID: $SLURM_JOB_ID"
echo "Node: $SLURM_NODELIST"
echo "Working directory: $(pwd)"
echo "Date: $(date)"

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
echo "Activating conda environment..."
conda activate upd-3d

echo "Starting human baseline viewer with --share option..."
echo "Current working directory: $(pwd)"
echo "Python version: $(python --version)"
echo "Starting at: $(date)"

# Force Python to flush output immediately and show all output
# -u flag makes stdout and stderr unbuffered
# Also set PYTHONUNBUFFERED environment variable as backup
export PYTHONUNBUFFERED=1

echo "Running: python -u human_baseline/human_baseline_viewer.py --share"
python -u human_baseline/human_baseline_viewer.py --share 2>&1 | tee -a /dev/stderr

exit_code=$?
echo "Script finished at: $(date)"
echo "Exit code: $exit_code"

if [ $exit_code -ne 0 ]; then
    echo "ERROR: Script exited with non-zero code $exit_code"
fi