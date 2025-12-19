#!/bin/bash

python analyze_scored_responses_radar.py \
    ./scored_model_responses/3D-FRONT_test_3dllm_base_gpt-4.1-mini \
    ./scored_model_responses/3D-FRONT_test_mgpt3d_gpt-4.1-mini \
    ./scored_model_responses/3D-FRONT_test_gplm_gpt-4.1-mini \
    ./scored_model_responses/3D-FRONT_test_pllm_gpt-4.1-mini \
    ./scored_model_responses/3D-FRONT_test_shpllm_ft-cap3d_gpt-4.1-mini \
    ./scored_model_responses/3D-FRONT_test_llava3d_base_gpt-4.1-mini \
    --legend_names "3D-LLM" "MiniGPT-3D" "GreenPLM" "PointLLM" "ShapeLLM" "LLaVA-3D" \
    --title "Model Comparison on UPD Tasks" \
    --no_plot_dual \
    --legend_bbox_to_anchor 1.3,1.115