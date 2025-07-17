export PYTHONPATH=$PWD

SUBFOLDER_ARG="$1"

CUDA_VISIBLE_DEVICES=0 python gplm_inf_upd.py \
    --batch_size 10 \
    --max_new_tokens 50 \
    --num_beams 5 \
    --temperature 0.1 \
    --top_p 0.1 \
    --lora_path ./checkpoints/stage_3 \
    --get_pc_tokens_way "OM_Pooling" \
    --out_path ./inf_rslts \
    --pretrain_mm_mlp_adapter ./checkpoints/stage_3/non_lora_trainables.bin \
    --pc_encoder_type small \
    --pc_ckpt_path /cluster/medbow/project/3dllms/melgin/GreenPLM_ft-upd-only/checkpoints/stage_3/checkpoint-9000/global_step9000/mp_rank_00_model_states.pt \
    --upd_text_folder_path /project/3dllms/melgin/UPD-3D/upd_text \
    --upd_version_name_subfolder "${SUBFOLDER_ARG}" \
    --unzipped_point_cloud_path /gscratch/melgin/3d-grand_unzipped/3D-FRONT \
    --pcl_list_txt_file_path /project/3dllms/melgin/UPD-3D/pcl_lists/3D-FRONT_test.txt \
	--json_tag ft-upd-only \