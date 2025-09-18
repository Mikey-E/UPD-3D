python analyze_scored_responses_radar_models.py \
  --title "Model Performance Comparison" \
  --series "Standard QA Performance" \
    ./scored_model_responses/3D-FRONT_test_mgpt3d/inference_results_MiniGPT-3D_3D-FRONT_test_standard_scored.json \
    scored_model_responses/3D-FRONT_test_gplm/inf_rslts_gplm_3D-FRONT_test_standard_scored.json \
    scored_model_responses/3D-FRONT_test_pllm/inf_rslts_pllm_base_3D-FRONT_test_standard_scored.json \
    scored_model_responses/3D-FRONT_test_shpllm_ft-upd/inf_rslts_shapellm-13b-general-v1.0-finetune-upd_ft-upd_3D-FRONT_test_standard_scored.json \
    --series "AAD_base Performance" \
    ./scored_model_responses/3D-FRONT_test_mgpt3d/inference_results_MiniGPT-3D_3D-FRONT_test_aad_base_scored.json \
    scored_model_responses/3D-FRONT_test_gplm/inf_rslts_gplm_3D-FRONT_test_aad_base_scored.json \
    scored_model_responses/3D-FRONT_test_pllm/inf_rslts_pllm_base_3D-FRONT_test_aad_base_scored.json \
    scored_model_responses/3D-FRONT_test_shpllm_ft-upd/inf_rslts_shapellm-13b-general-v1.0-finetune-upd_ft-upd_3D-FRONT_test_aad_base_scored.json \
  --output_name "model_comparison_standard_qa"