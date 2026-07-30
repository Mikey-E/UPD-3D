# https://github.com/TangYuan96/GreenPLM commit 6 (a1912a3) on GitHub, commit 3 (9c06848) on huggingface

# salloc an a30 or l40s. h100 will give an sm_90 error. I tried very hard for a full day to get a build that would work for h100s. Using torch 2.0.1+cu118 allowed a build that worked for some inference commands, but not training. In any case, at this time (2025_08_17) we have all the results we need from GreenPLM, so getting an h100 build to work would be a luxury - and a luxury we might not even use.

# Make a clone, aptly named
# git clone https://huggingface.co/YuanTang96/GreenPLM GreenPLM_w_mgpt3d_backbone

# Clear old env if it exists
conda deactivate
conda remove -n greenplm_w_mgpt3d_backbone --all -y

#BEGIN ENV SETUP
# Clone from HuggingFace into a temporary directory
ml gcc/14.2.0
ml git-lfs
git lfs pull
ln -s /cluster/medbow/project/3dllms/melgin/datasets/GreenPLM data

conda create -n greenplm_w_mgpt3d_backbone python=3.10 -y

# make the activation script in the env/etc/conda/activate.d directory: lmod.sh (or-any-name.sh)
echo "
    module purge
    module load gcc/11.4.0
    module load cuda-toolkit/11.7.1
" > $CONDA_PREFIX/etc/conda/activate.d/lmod.sh

conda activate greenplm_w_mgpt3d_backbone

bash envInstall.sh
# Follow any remaining env setup steps
# for using .ply files and converting them to .npy, you may need to: python -m pip install open3d
python -m pip install open3d

#END ENV SETUP

# ----for setting up gplm to work with .ply files----

# You may need to replace the read_pc_2tensor function with the following code:

# import open3d as o3d

# def read_pc_2tensor(object_id):
#     data_path = './dataset/Objaverse/8192_npy'

#     filename = f"{object_id}_8192.npy"
#     file_path = os.path.join(data_path, filename)

#     if os.path.exists(file_path):
#         point_cloud = np.load(file_path)
#     else:  # If .npy file doesn't exist, try loading .ply
#         ply_filename = object_id + ".ply"
#         ply_path = os.path.join(data_path, ply_filename)
#         if os.path.exists(ply_path):
#             pcd = o3d.io.read_point_cloud(ply_path)
#             xyz = np.asarray(pcd.points)
#             if pcd.has_colors():
#                 colors = np.asarray(pcd.colors)
#             else:
#                 colors = np.zeros_like(xyz)
#             # Stack to get (N, 6): x, y, z, r, g, b
#             pc6 = np.hstack([xyz, colors])
#             target_n = 8192
#             if pc6.shape[0] >= target_n:
#                 idx = np.random.choice(pc6.shape[0], target_n, replace=False)
#                 pc6 = pc6[idx]
#             else:
#                 pad = np.zeros((target_n - pc6.shape[0], 6), dtype=pc6.dtype)
#                 pc6 = np.vstack([pc6, pad])
#             point_cloud = pc6
#         else:
#             raise FileNotFoundError(f"Neither {filename} nor {ply_filename} found in {data_path}")

#     point_cloud = pc_norm(point_cloud)
#     point_cloud = torch.from_numpy(point_cloud.astype(np.float32))
#     return point_cloud

# -----
# Dataset modifications
#     ft-comb
#         dataset/Objaverse
#             PointLLM_complex_50k_brief_40k_all_90k.json has UPD data combined into it
#         dataset/Objaverse/8192_npy (has soft links to 3D-FRONT point clouds laundered in)
#             'ffa406e2-6e48-4c38-8072-cffca7b2633b@Hallway-2369.ply' -> /gscratch/melgin/3d-grand_unzipped/3D-FRONT/ffa406e2-6e48-4c38-8072-cffca7b2633b/Hallway-2369/Hallway-2369.ply
#             'ffa406e2-6e48-4c38-8072-cffca7b2633b@StorageRoom-2326.ply' -> /gscratch/melgin/3d-grand_unzipped/3D-FRONT/ffa406e2-6e48-4c38-8072-cffca7b2633b/StorageRoom-2326/StorageRoom-2326.ply
#             ...
#         dataset/T3D
#             stage_1
#                 brief_1M_caption.json has UPD data combined into it
#             stage_2
#                 stage_2_data_5M.json has UPD data combined into it
#                 stage_2_data_210k.json has UPD data combined into it
#     ft-upd-only
#         dataset/Objaverse/8192_npy
#             has only soft links to 3D-FRONT point clouds
#         dataset/Objaverse
#             PointLLM_brief_description_val_200_GT.json -> /project/3dllms/melgin/UPD-3D/utils/data_reformats/overall_3D-FRONT_val_subset_of_train.json
#             PointLLM_complex_50k_brief_40k_all_90k.json -> /project/3dllms/melgin/UPD-3D/utils/data_reformats/overall_3D-FRONT_train_minus_val.json
#         dataset/T3D
#             stage_1
#                 brief_1M_caption.json -> /project/3dllms/melgin/UPD-3D/utils/data_reformats/overall_3D-FRONT_train_captions.json
#             stage_2
#                 stage_2_data_210k.json -> /project/3dllms/melgin/UPD-3D/utils/data_reformats/overall_3D-FRONT_train_captions.json
#                 stage_2_data_5M.json -> /project/3dllms/melgin/UPD-3D/utils/data_reformats/overall_3D-FRONT_train_captions.json
