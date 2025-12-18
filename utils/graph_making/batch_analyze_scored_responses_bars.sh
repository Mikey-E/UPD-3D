#!/bin/bash

# This script iterates through all folders in scored_model_responses/ 
# and generates bar charts for each using analyze_scored_responses_bars.py

# Function to convert model shorthand to full name
get_model_name() {
    local model_str="$1"
    
    # Extract base model name (handle ft-* variants)
    local base_model=$(echo "$model_str" | sed -E 's/_ft-.*//')
    
    case "$base_model" in
        *mgpt3d*)
            echo "MiniGPT-3D"
            ;;
        *gplm*)
            echo "GreenPLM"
            ;;
        *pllm*)
            echo "PointLLM"
            ;;
        *shpllm*)
            echo "ShapeLLM"
            ;;
        *llava3d*)
            echo "LLaVA-3D"
            ;;
        *3dllm*)
            echo "3D-LLM"
            ;;
        *human*)
            echo "Human Baseline"
            ;;
        *gpt4point*)
            echo "GPT4Point"
            ;;
        *pointreason*)
            echo "PointReason"
            ;;
        *)
            echo "$model_str"
            ;;
    esac
}

# Function to format model variant (base, ft-comb, etc.)
get_model_variant() {
    local model_str="$1"
    
    if [[ "$model_str" == *"_base"* ]]; then
        echo "Base"
    elif [[ "$model_str" == *"ft-comb"* ]]; then
        echo "Finetuned (Combined)"
    elif [[ "$model_str" == *"ft-upd"* ]]; then
        echo "Finetuned (UPD Only)"
    elif [[ "$model_str" == *"ckpt"* ]]; then
        # Extract checkpoint number if present
        local ckpt=$(echo "$model_str" | grep -oP 'ckpt\d+')
        echo "Finetuned (${ckpt})"
    else
        echo ""
    fi
}

# Function to clean up dataset name
get_dataset_name() {
    local dataset="$1"
    
    case "$dataset" in
        "3D-FRONT")
            echo "3D-FRONT"
            ;;
        "Crops3D_gpt-5-nano")
            echo "Crops3D"
            ;;
        "GIW529_gpt-5-nano")
            echo "GIW529"
            ;;
        *)
            echo "$dataset"
            ;;
    esac
}

# Main directory containing scored model responses
SCORED_DIR="./scored_model_responses"

# Check if directory exists
if [ ! -d "$SCORED_DIR" ]; then
    echo "Error: Directory $SCORED_DIR does not exist"
    exit 1
fi

# Counter for progress
total_folders=$(find "$SCORED_DIR" -mindepth 1 -maxdepth 1 -type d | wc -l)
current=0

echo "========================================"
echo "Batch Bar Chart Generation"
echo "Processing $total_folders folders..."
echo "========================================"
echo ""

# Iterate through each folder in scored_model_responses
for folder in "$SCORED_DIR"/*/ ; do
    ((current++))
    
    # Remove trailing slash and get basename
    folder_name=$(basename "${folder%/}")
    
    echo "[$current/$total_folders] Processing: $folder_name"
    
    # Parse folder name: [dataset]_test_[model]_[scoring_model]
    # Extract components using pattern matching
    if [[ "$folder_name" =~ ^([^_]+(_[^_]+)?)_test_(.+)_([^_]+)$ ]]; then
        dataset="${BASH_REMATCH[1]}"
        model_part="${BASH_REMATCH[3]}"
        scoring_model="${BASH_REMATCH[4]}"
    else
        echo "  WARNING: Could not parse folder name pattern, skipping..."
        echo ""
        continue
    fi
    
    # Get clean names
    dataset_clean=$(get_dataset_name "$dataset")
    model_name=$(get_model_name "$model_part")
    model_variant=$(get_model_variant "$model_part")
    
    # Construct title
    if [ -n "$model_variant" ]; then
        title="$model_name ($model_variant) - $dataset_clean Test Set"
    else
        title="$model_name - $dataset_clean Test Set"
    fi
    
    # Determine naming delimiter based on dataset
    naming_delim="${dataset}_test_"
    
    # Check if folder has any JSON files
    json_count=$(find "$folder" -maxdepth 1 -name "*.json" -type f | wc -l)
    if [ "$json_count" -eq 0 ]; then
        echo "  WARNING: No JSON files found in folder, skipping..."
        echo ""
        continue
    fi
    
    echo "  Title: $title"
    echo "  Delimiter: $naming_delim"
    echo "  Running analysis..."
    
    # Run the bar chart generation script
    python analyze_scored_responses_bars.py \
        "$folder" \
        --naming_delim "$naming_delim" \
        --title "$title"
    
    echo "  ✓ Completed"
    echo ""
done

echo "========================================"
echo "All folders processed!"
echo "Bar charts saved to: ./results/bar_graphs/"
echo "========================================"
