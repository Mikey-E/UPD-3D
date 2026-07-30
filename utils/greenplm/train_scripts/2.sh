#!/bin/bash
export PYTHONPATH=$PWD

: "${EXP_NAME:?Set EXP_NAME to the experiment name (used as checkpoint dir suffix)}"

deepspeed --master_port 29522 --include localhost:0 llava/train/train_mem.py \
    --lora_enable True --lora_r 32 --lora_alpha 64 --mm_projector_lr 2e-5 \
    --deepspeed ./scripts/zero2.json \
    --model_name_or_path ./lava-vicuna_2024_4_Phi-3-mini-4k-instruct \
    --version phi3_instruct \
    --data_path ./dataset/T3D/stage_2/stage_2_data_210k.json \
    --pretrain_mm_mlp_adapter ./checkpoints/stage_1_${EXP_NAME}/mm_projector.bin \
    --mm_projector_type mlp2x_gelu \
    --mm_vision_select_layer -2 \
    --mm_use_im_start_end False \
    --mm_use_im_patch_token False \
    --group_by_modality_length True \
    --bf16 True \
    --output_dir ./checkpoints/stage_2_${EXP_NAME} \
    --num_train_epochs 1 \
    --per_device_train_batch_size 14 \
    --per_device_eval_batch_size 4 \
    --gradient_accumulation_steps 1 \
    --evaluation_strategy "no" \
    --save_strategy "steps" \
    --save_steps 3000 \
    --save_total_limit 1 \
    --learning_rate 2e-4 \
    --weight_decay 0. \
    --warmup_ratio 0.03 \
    --lr_scheduler_type "cosine" \
    --logging_steps 1 \
    --tf32 True \
    --encoder_type text_encoder  \
    --model_max_length 512 \
    --gradient_checkpointing True \
    --dataloader_num_workers 4 \
    --lazy_preprocess True \
    --report_to wandb \
    --std 0.05