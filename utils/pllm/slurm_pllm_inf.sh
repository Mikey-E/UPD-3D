#!/bin/bash

#SBATCH --account=3dllms
#SBATCH --job-name=pllm_inf
#SBATCH --partition=mb-l40s,inv-ssheshap
#SBATCH --nodes=1
#SBATCH --nodelist=mbl40s-001,mbl40s-002,mbl40s-003,mbl40s-004,mbl40s-005,mbl40s-006,mbl40s-007,vl40s-005
#SBATCH --output=./slurm_logs/pllm_inf_%j.log
#SBATCH --error=./slurm_logs/pllm_inf_%j.log
#SBATCH --gres=gpu:1
#SBATCH --mem=48G
#SBATCH --time=7-00:00:00

# Fail fast and keep a clean environment
set -euo pipefail

# Ensure we run from the repo root, robustly resolving symlinks
SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(dirname "$SCRIPT_PATH")"

# Ensure Python can import the top-level package regardless of cwd quirks
export PYTHONPATH="$SCRIPT_DIR:${PYTHONPATH:-}"

echo "[pllm_inf] Working dir: $(pwd)" >&2
echo "[pllm_inf] PYTHONPATH: $PYTHONPATH" >&2
ls -la "$SCRIPT_DIR/pointllm" >/dev/null 2>&1 || echo "[pllm_inf][WARN] pointllm/ not found under $SCRIPT_DIR" >&2

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
conda activate pointllm

cd /project/3dllms/melgin/PointLLM_ft-comb/

# Run as a module so Python resolves the top-level package `pointllm`
python pointllm/eval/pllm_inf.py "$@"
# python -m pointllm.eval.pllm_inf "$@"