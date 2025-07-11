#!/bin/bash
#SBATCH --account=3dllms
#SBATCH --partition=mb-a30
#SBATCH --job-name=mgpt3d_train_stage3_combined
#SBATCH --output=mgpt3d_train_stage3_combined_%j.out
#SBATCH --error=mgpt3d_train_stage3_combined_%j.out
#SBATCH --gres=gpu:1
#SBATCH --mem=16G
#SBATCH --time=24:00:00

#This ensures conda activate works in non-interactive shells.
#running conda init every time won't work. Just make sure to source the correct conda.sh
source /project/3dllms/melgin/conda/etc/profile.d/conda.sh

#Activate the conda environment just in case you didn't already in the command line.
conda activate minigpt-3d

export MASTER_ADDR=localhost
export MASTER_PORT=$(python -c "import socket; s=socket.socket(); s.bind(('',0)); print(s.getsockname()[1]); s.close()") #Determines a free port and assigns it
export WANDB_MODE=disabled #Otherwise it will give and error for trying to log to wandb
CUDA_VISIBLE_DEVICES=0 python train.py --cfg-path ./train_configs/MiniGPT_3D/mgpt3d_stage3_combined.yaml