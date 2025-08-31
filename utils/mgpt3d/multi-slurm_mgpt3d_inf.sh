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
    --cfg-path ./eval_configs/MiniGPT_3D_conv_UI_demo.yaml \
    --upd_text_folder_path /project/3dllms/melgin/UPD-3D/upd_text \
    --upd_version_name "Crops3D_gpt-5-nano" \
    --upd_version_name_subfolder "${subfolder}" \
    --unzipped_point_cloud_path /gscratch/melgin/CEA/Crops3D \
    --pcl_list_txt_file_path /project/3dllms/melgin/UPD-3D/pcl_lists/Crops3D_test.txt \
    --json_tag ft-comb
done