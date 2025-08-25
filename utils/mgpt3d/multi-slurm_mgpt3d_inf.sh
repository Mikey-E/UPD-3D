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
    sbatch slurm_mgpt3d_inf.sh \
    --cfg-path ./eval_configs/mgpt3d_eval-config_ft-comb.yaml \
    --upd_text_folder_path /project/3dllms/melgin/UPD-3D/upd_text \
    --unzipped_point_cloud_path /gscratch/melgin/3d-grand_unzipped/3D-FRONT \
    --pcl_list_txt_file_path /project/3dllms/melgin/UPD-3D/pcl_lists/3D-FRONT_test.txt \
    --json_tag ft-comb \
    --upd_version_name_subfolder "${subfolder}"
done