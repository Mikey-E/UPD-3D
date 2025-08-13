#!/bin/bash
#SBATCH --account=3dllms
#SBATCH --partition=mb-a30
#SBATCH --job-name=mgpt3d_train_stage2_upd-only
#SBATCH --output=mgpt3d_train_stage2_upd-only_%j.out
#SBATCH --error=mgpt3d_train_stage2_upd-only_%j.out
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
conda activate minigpt-3d

export MASTER_ADDR=localhost
export MASTER_PORT=$(python -c "import socket; s=socket.socket(); s.bind(('',0)); print(s.getsockname()[1]); s.close()") #Determines a free port and assigns it
export WANDB_MODE=disabled #Otherwise it will give and error for trying to log to wandb
CUDA_VISIBLE_DEVICES=0 python train.py --cfg-path ./train_configs/MiniGPT_3D/mgpt3d_stage2_upd-only.yaml