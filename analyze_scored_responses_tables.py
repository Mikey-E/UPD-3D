"""
This file takes a folder of _scored json files of model responses to UPD subsets, and computes percentages for LaTeX table generation
"""

import argparse
import json
import os
import re

def main():
    parser = argparse.ArgumentParser(description="Analyze scored responses and output data for LaTeX tables.")
    parser.add_argument("folder_path", type=str, help="Path to the folder containing JSON files with scored responses.")
    parser.add_argument("--dual", action="store_true", help="Calculate dual accuracies instead of standard-upd accuracies.")
    args = parser.parse_args()
    
    folder_path = args.folder_path
    json_files = [os.path.join(folder_path, file) for file in os.listdir(folder_path) if file.endswith('.json')]
    
    results = {}
    standard_upd_accuracies = {}
    standard_file = None  # To be set if a standard file is found
    
    for json_file in json_files:
        with open(json_file, 'r') as f:
            data = json.load(f)
        if "standard" in json_file:
            standard_file = json_file
        # Extract scores from the data
        results[json_file] = [item["score"] for item in data.values()]
        standard_upd_accuracies[json_file] = len([score for score in results[json_file] if score == 'T'])
    
    # Check if sample counts are consistent across categories
    sample_counts = [len(results[k]) for k in standard_upd_accuracies.keys()]
    if len(set(sample_counts)) != 1:
        print("WARNING: Not all categories have the same number of samples.", file=__import__('sys').stderr)
    
    # Compute dual accuracies
    dual_accuracies = {}
    if standard_file and args.dual:
        standard_score_list = results[standard_file]
        for json_file in json_files:
            if "standard" in json_file or "open_ended" in json_file:
                dual_accuracies[json_file] = 0
                continue
            if json_file != standard_file:
                upd_score_list = results[json_file]
                dual_accuracies[json_file] = 0  # Initialize to 0
                for i in range(len(standard_score_list)):
                    if standard_score_list[i] == 'T' and upd_score_list[i] == 'T':
                        dual_accuracies[json_file] += 1
    
    # Extract category names and compute percentages
    category_data = {}
    
    for filepath in standard_upd_accuracies.keys():
        # Get just the filename
        basename = os.path.basename(filepath)
        
        # Extract category using regex pattern: _test_[category]_[scoring_model]_scored.json
        match = re.search(r'_test_(.+?)_[^_/]+_scored\.json$', basename)
        if match:
            category = match.group(1)
        else:
            # Fallback: try to extract anything after _test_
            if '_test_' in basename:
                category = basename.split('_test_')[-1].replace('_scored.json', '').split('_')[0]
            else:
                category = basename
        
        # Format the category name
        category = category.replace("_", " ")
        category = category.title()
        
        # Fix acronyms
        for acr in ["aad", "iasd", "ivqd"]:
            category = re.sub(r'(?i)\b' + acr + r'\b', acr.upper(), category)
        
        # Calculate percentage
        total = len(results[filepath])
        
        if args.dual:
            if filepath in dual_accuracies:
                correct = dual_accuracies[filepath]
                if "standard" in filepath or "open_ended" in filepath:
                    percentage = None  # N/A for dual
                else:
                    percentage = (correct / total) * 100 if total > 0 else 0
            else:
                percentage = None
        else:
            correct = standard_upd_accuracies[filepath]
            percentage = (correct / total) * 100 if total > 0 else 0
        
        category_data[category] = {
            'correct': correct if args.dual and filepath in dual_accuracies else standard_upd_accuracies[filepath],
            'total': total,
            'percentage': percentage
        }
    
    # Return data for further processing
    return category_data, os.path.basename(os.path.normpath(folder_path))

if __name__ == "__main__":
    category_data, folder_name = main()
    print(f"Folder: {folder_name}")
    for category, data in sorted(category_data.items()):
        if data['percentage'] is not None:
            print(f"{category}: {data['correct']}/{data['total']} = {data['percentage']:.1f}%")
        else:
            print(f"{category}: N/A (Dual)")
