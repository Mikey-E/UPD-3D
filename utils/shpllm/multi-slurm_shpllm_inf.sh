subfolders=(
    "standard"
    "open_ended"
    "open_ended_additional_instruction"
    "aad_base"
    "aad_additional_option"
    "aad_additional_instruction"
    "iasd_base"
    "iasd_additional_option"
    "iasd_additional_instruction"
    "ivqd_base"
    "ivqd_additional_option"
    "ivqd_additional_instruction"
)

for subfolder in "${subfolders[@]}"; do
    sbatch slurm_shpllm_inf.sh \
    --model_path checkpoints/shapellm-13b-general-v1.0-finetune \
    --upd_text_folder_path /project/3dllms/melgin/UPD-3D/upd_text \
    --unzipped_point_cloud_path /gscratch/melgin/3d-grand_unzipped/3D-FRONT \
    --pcl_list_txt_file_path /project/3dllms/melgin/UPD-3D/pcl_lists/3D-FRONT_test.txt \
    --json_tag ft-cap3d \
    --upd_version_name_subfolder "${subfolder}"
done

for subfolder in "${subfolders[@]}"; do
    sbatch slurm_shpllm_inf.sh \
    --model_path checkpoints/shapellm-13b-general-v1.0-finetune-upd \
    --upd_text_folder_path /project/3dllms/melgin/UPD-3D/upd_text \
    --unzipped_point_cloud_path /gscratch/melgin/3d-grand_unzipped/3D-FRONT \
    --pcl_list_txt_file_path /project/3dllms/melgin/UPD-3D/pcl_lists/3D-FRONT_test.txt \
    --json_tag ft-upd \
    --upd_version_name_subfolder "${subfolder}"
done