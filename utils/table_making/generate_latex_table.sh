#!/bin/bash

# This script iterates through all folders in scored_model_responses/ 
# and generates LaTeX table data for each using analyze_scored_responses_tables.py

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
        *shpllm*)
            echo "ShapeLLM"
            ;;
        *pllm*)
            echo "PointLLM"
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
    
    if [[ "$model_str" == *"ft-comb"* ]]; then
        echo "Fine-tuned (Combined)"
    elif [[ "$model_str" == *"ft-upd"* ]]; then
        echo "Fine-tuned (UPD)"
    elif [[ "$model_str" == *"base"* ]]; then
        echo "Base"
    elif [[ "$model_str" == *"ckpt"* ]]; then
        # Extract checkpoint number
        local ckpt_num=$(echo "$model_str" | grep -oP 'ckpt\K\d+')
        echo "Checkpoint $ckpt_num"
    else
        echo ""
    fi
}

# Helper function to exit gracefully (works whether script is sourced or executed)
exit_script() {
    local exit_code=$1
    # Check if script is being sourced
    if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
        return $exit_code
    else
        exit $exit_code
    fi
}

# Parse command line arguments
DUAL_FLAG=""
DATASET_FILTER=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dual)
            DUAL_FLAG="--dual"
            shift
            ;;
        --3D-FRONT)
            DATASET_FILTER="3D-FRONT"
            shift
            ;;
        --Crops3D)
            DATASET_FILTER="Crops3D_gpt-5-nano"
            shift
            ;;
        --GIW529)
            DATASET_FILTER="GIW529_gpt-5-nano"
            shift
            ;;
        *)
            echo "Unknown option: $1" >&2
            echo "Usage: $0 [--dual] [--3D-FRONT|--Crops3D|--GIW529]" >&2
            exit_script 1
            return 2>/dev/null || exit 1
            ;;
    esac
done

# Check if dataset filter was provided
if [ -z "$DATASET_FILTER" ]; then
    echo "Error: A dataset filter is required." >&2
    echo "Usage: $0 [--dual] [--3D-FRONT|--Crops3D|--GIW529]" >&2
    exit_script 1
    return 2>/dev/null || exit 1
fi

# Directory containing scored model responses
SCORED_DIR="scored_model_responses"

# Check if directory exists
if [ ! -d "$SCORED_DIR" ]; then
    echo "Error: Directory $SCORED_DIR not found" >&2
    exit_script 1
    return 2>/dev/null || exit 1
fi

# Define the 12 UPD categories in order
CATEGORIES=("AAD Additional Instruction" "AAD Additional Option" "AAD Base" 
           "IASD Additional Instruction" "IASD Additional Option" "IASD Base"
           "IVQD Additional Instruction" "IVQD Additional Option" "IVQD Base"
           "Open Ended Additional Instruction" "Open Ended" "Standard")

# Store all model data - reset arrays to avoid accumulation when sourcing
unset ALL_MODEL_DATA
unset MODEL_ORDER
declare -A ALL_MODEL_DATA
declare -a MODEL_ORDER

echo "Collecting data from scored model responses..."
echo "Filtering for dataset: $DATASET_FILTER"
echo ""

# Iterate through each folder in scored_model_responses
for folder in "$SCORED_DIR"/*; do
    if [ -d "$folder" ]; then
        folder_name=$(basename "$folder")
        
        # Skip folders that don't match the dataset filter
        if [[ ! "$folder_name" == "$DATASET_FILTER"* ]]; then
            continue
        fi
        
        echo "Processing: $folder_name"
        
        # Run the analysis script
        result=$(python analyze_scored_responses_tables.py "$folder" $DUAL_FLAG 2>/dev/null)
        
        if [ $? -eq 0 ]; then
            # Store the result
            ALL_MODEL_DATA["$folder_name"]="$result"
            MODEL_ORDER+=("$folder_name")
        else
            echo "  Warning: Failed to process $folder_name"
        fi
    fi
done

echo ""
echo "Generating LaTeX table..."
echo ""

# Generate LaTeX table header
echo "\\begin{table}[h]"
echo "\\centering"
echo "\\resizebox{\\textwidth}{!}{%"
echo "\\begin{tabular}{|l|c|c|c|c|c|c|c|c|c|c|c|c|}"
echo "\\hline"

# Header row
echo -n "\\textbf{Model}"
for cat in "${CATEGORIES[@]}"; do
    # Abbreviate for table header
    case "$cat" in
        "AAD Additional Instruction") echo -n " & \\textbf{AAD-AI}" ;;
        "AAD Additional Option") echo -n " & \\textbf{AAD-AO}" ;;
        "AAD Base") echo -n " & \\textbf{AAD}" ;;
        "IASD Additional Instruction") echo -n " & \\textbf{IASD-AI}" ;;
        "IASD Additional Option") echo -n " & \\textbf{IASD-AO}" ;;
        "IASD Base") echo -n " & \\textbf{IASD}" ;;
        "IVQD Additional Instruction") echo -n " & \\textbf{IVQD-AI}" ;;
        "IVQD Additional Option") echo -n " & \\textbf{IVQD-AO}" ;;
        "IVQD Base") echo -n " & \\textbf{IVQD}" ;;
        "Open Ended Additional Instruction") echo -n " & \\textbf{OE-AI}" ;;
        "Open Ended") echo -n " & \\textbf{OE}" ;;
        "Standard") echo -n " & \\textbf{Std}" ;;
    esac
done
echo " \\\\"
echo "\\hline"

# Data rows
for folder_name in "${MODEL_ORDER[@]}"; do
    # Extract model info from folder name
    model_base=$(get_model_name "$folder_name")
    model_variant=$(get_model_variant "$folder_name")
    
    # Create display name
    if [ -n "$model_variant" ]; then
        display_name="$model_base ($model_variant)"
    else
        display_name="$model_base"
    fi
    
    echo -n "$display_name"
    
    # Get the stored result for this model
    result="${ALL_MODEL_DATA[$folder_name]}"
    
    # Parse each category percentage
    for cat in "${CATEGORIES[@]}"; do
        # Extract percentage for this category from the result
        percentage=$(echo "$result" | grep -i "^$cat:" | grep -oP '\d+\.\d+%' | grep -oP '\d+\.\d+')
        
        if [ -z "$percentage" ]; then
            # Check if it's N/A (for dual mode)
            is_na=$(echo "$result" | grep -i "^$cat:" | grep "N/A")
            if [ -n "$is_na" ]; then
                echo -n " & N/A"
            else
                echo -n " & --"
            fi
        else
            echo -n " & ${percentage}\\%"
        fi
    done
    
    echo " \\\\"
done

echo "\\hline"
echo "Dataset: $DATASET_FILTER"
echo "\\end{tabular}%"
echo "}"
echo "\\caption{Model Performance Across UPD Categories}"
echo "\\label{tab:upd_results}"
echo "\\end{table}"

echo ""
echo "LaTeX table generated successfully!"
if [ -n "$DUAL_FLAG" ]; then
    echo "Mode: Dual accuracy (Standard AND UPD both correct)"
else
    echo "Mode: Standard-UPD accuracy (Standard OR UPD correct)"
fi
