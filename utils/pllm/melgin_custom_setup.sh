# https://github.com/OpenRobotLab/PointLLM commit 55 (77bf64c)

# salloc an mb-l40s node with plenty of memory (48G+)

conda create -n pointllm python=3.10 -y

mkdir -p /project/3dllms/melgin/conda/envs/pointllm/etc/conda/activate.d

echo "module purge
module load gcc/11.4.0
module load cuda-toolkit/11.7.1" > /project/3dllms/melgin/conda/envs/pointllm/etc/conda/activate.d/lmod.sh

conda activate pointllm

conda install numpy=1.26 -y

pip install --upgrade pip

pip install torch==2.0.1+cu117 torchvision==0.15.2+cu117 \
  --extra-index-url https://download.pytorch.org/whl/cu117

pip install -e . --no-build-isolation

pip install ninja

pip install flash-attn==2.5.3 --no-build-isolation

python -m pip install opencv-python==4.10.0.84

python -m pip install objaverse