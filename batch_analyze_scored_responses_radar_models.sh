#!/bin/bash

# Check for --dual flag
DUAL_FLAG=""
if [[ "$1" == "--dual" ]]; then
    DUAL_FLAG="--dual"
    echo "Running in dual accuracy mode"
    shift  # Remove --dual from arguments
fi

# Array of all 12 UPD categories
categories=(
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

# Function to format category name for title
format_title() {
    local category="$1"
    case "$category" in
        "standard")
            echo "Standard"
            ;;
        "open_ended")
            echo "Open Ended"
            ;;
        "open_ended_additional_instruction")
            echo "Open Ended Additional Instruction"
            ;;
        "aad_base")
            echo "AAD Base"
            ;;
        "aad_additional_option")
            echo "AAD Additional Option"
            ;;
        "aad_additional_instruction")
            echo "AAD Additional Instruction"
            ;;
        "iasd_base")
            echo "IASD Base"
            ;;
        "iasd_additional_option")
            echo "IASD Additional Option"
            ;;
        "iasd_additional_instruction")
            echo "IASD Additional Instruction"
            ;;
        "ivqd_base")
            echo "IVQD Base"
            ;;
        "ivqd_additional_option")
            echo "IVQD Additional Option"
            ;;
        "ivqd_additional_instruction")
            echo "IVQD Additional Instruction"
            ;;
        *)
            echo "$category"
            ;;
    esac
}

# Loop through each category
for category in "${categories[@]}"; do
    echo "Processing category: $category"
    
    # Format the title
    formatted_title=$(format_title "$category")
    
    # Set output folder name based on dual mode
    if [[ -n "$DUAL_FLAG" ]]; then
        formatted_title="$formatted_title Dual Accuracy"
        output_folder="UPD-3D-FRONT_Model_Performance_Comparison_Dual"
    else
        output_folder="UPD-3D-FRONT_Model_Performance_Comparison"
    fi
    
    # Build file lists for current category
    base_model_files=(
        "./scored_model_responses/3D-FRONT_test_mgpt3d/inf_rslts_mgpt3d_3D-FRONT_test_${category}_scored.json"
        "scored_model_responses/3D-FRONT_test_gplm/inf_rslts_gplm_3D-FRONT_test_${category}_scored.json"
        "scored_model_responses/3D-FRONT_test_pllm/inf_rslts_pllm_base_3D-FRONT_test_${category}_scored.json"
        "scored_model_responses/3D-FRONT_test_shpllm_ft-cap3d/inf_rslts_shapellm-13b-general-v1.0-finetune_ft-cap3d_3D-FRONT_test_${category}_scored.json"
        "scored_model_responses/3D-FRONT_test_llava3d_base/inf_rslts_llava3d_base_3D-FRONT_test_${category}_scored.json"
    )
    
    trained_model_files=(
        "./scored_model_responses/3D-FRONT_test_mgpt3d_ft-comb/inf_rslts_mgpt3d_ft-comb_3D-FRONT_test_${category}_scored.json"
        "scored_model_responses/3D-FRONT_test_gplm_ft-comb/inf_rslts_gplm_ft-comb_3D-FRONT_test_${category}_scored.json"
        "scored_model_responses/3D-FRONT_test_pllm_ft-comb/inf_rslts_pllm_ft-comb_3D-FRONT_test_${category}_scored.json"
        "scored_model_responses/3D-FRONT_test_shpllm_ft-upd/inf_rslts_shapellm-13b-general-v1.0-finetune-upd_ft-upd_3D-FRONT_test_${category}_scored.json"
        "scored_model_responses/3D-FRONT_test_llava3d_ft-upd_3D-FRONT/inf_rslts_llava3d_ft-upd_3D-FRONT_3D-FRONT_test_${category}_scored.json"
    )
    
    # If in dual mode and not processing standard/open_ended, add standard files to each series
    if [[ -n "$DUAL_FLAG" && "$category" != "standard" && "$category" != "open_ended"* ]]; then
        # Add corresponding standard files to each series
        base_model_files+=(
            "./scored_model_responses/3D-FRONT_test_mgpt3d/inf_rslts_mgpt3d_3D-FRONT_test_standard_scored.json"
            "scored_model_responses/3D-FRONT_test_gplm/inf_rslts_gplm_3D-FRONT_test_standard_scored.json"
            "scored_model_responses/3D-FRONT_test_pllm/inf_rslts_pllm_base_3D-FRONT_test_standard_scored.json"
            "scored_model_responses/3D-FRONT_test_shpllm_ft-cap3d/inf_rslts_shapellm-13b-general-v1.0-finetune_ft-cap3d_3D-FRONT_test_standard_scored.json"
            "scored_model_responses/3D-FRONT_test_llava3d_base/inf_rslts_llava3d_base_3D-FRONT_test_standard_scored.json"
        )
        
        trained_model_files+=(
            "./scored_model_responses/3D-FRONT_test_mgpt3d_ft-comb/inf_rslts_mgpt3d_ft-comb_3D-FRONT_test_standard_scored.json"
            "scored_model_responses/3D-FRONT_test_gplm_ft-comb/inf_rslts_gplm_ft-comb_3D-FRONT_test_standard_scored.json"
            "scored_model_responses/3D-FRONT_test_pllm_ft-comb/inf_rslts_pllm_ft-comb_3D-FRONT_test_standard_scored.json"
            "scored_model_responses/3D-FRONT_test_shpllm_ft-upd/inf_rslts_shapellm-13b-general-v1.0-finetune-upd_ft-upd_3D-FRONT_test_standard_scored.json"
            "scored_model_responses/3D-FRONT_test_llava3d_ft-upd_3D-FRONT/inf_rslts_llava3d_ft-upd_3D-FRONT_3D-FRONT_test_standard_scored.json"
        )
    fi
    
    python analyze_scored_responses_radar_models.py \
      --title "$formatted_title" \
      --output_folder_name "$output_folder" \
      --no_legend \
      $DUAL_FLAG \
      --series "Base Model $formatted_title Performance" \
        "${base_model_files[@]}" \
      --series "Trained/Finetuned $formatted_title Performance" green \
        "${trained_model_files[@]}"
    
    echo "Completed category: $category"
    echo "---"
done

echo "All categories processed!"