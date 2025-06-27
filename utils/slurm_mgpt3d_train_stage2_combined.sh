#!/bin/bash
#SBATCH --account=3dllms
#SBATCH --partition=mb-a30
#SBATCH --job-name=mgpt3d_train_stage2_combined
#SBATCH --output=mgpt3d_train_stage2_combined_%j.out
#SBATCH --error=mgpt3d_train_stage2_combined_%j.out
#SBATCH --gres=gpu:1
#SBATCH --mem=16G
#SBATCH --time=24:00:00

export MASTER_ADDR=localhost
export MASTER_PORT=$(python -c "import socket; s=socket.socket(); s.bind(('',0)); print(s.getsockname()[1]); s.close()") #Determines a free port and assigns it
export WANDB_MODE=disabled #Otherwise it will give and error for trying to log to wandb
CUDA_VISIBLE_DEVICES=0 python train.py --cfg-path ./train_configs/MiniGPT_3D/mgpt3d_stage2_combined.yaml