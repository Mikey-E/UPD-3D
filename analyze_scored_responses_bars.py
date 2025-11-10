"""
This file takes a folder of _scored json files of model responses to UPD subsets, and makes a graph of the scores
"""

import argparse
import json
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import os
import re

def main():
    parser = argparse.ArgumentParser(description="Analyze scored responses and create a bar graph.")
    parser.add_argument("folder_path", type=str, help="Path to the folder containing JSON files with scored responses.")
    parser.add_argument("--naming_delim", type=str, help="Delimiter in the file names to separate out subset name.", default="_3D-FRONT_test_")
    parser.add_argument("--title", type=str, required=True, help="Graph title.")
    parser.add_argument("--bar_fontsize", type=int, default=13, help="Font size for bar label text.")
    parser.add_argument("--tick_fontsize", type=int, default=14, help="Font size for axis ticks and labels.")
    parser.add_argument("--legend_fontsize", type=int, default=13, help="Font size for legend text.")
    parser.add_argument("--title_fontsize", type=int, default=19, help="Font size for title text.")
    parser.add_argument("--fontscale", type=float, default=1.0, help="Scale factor to multiply all font sizes.")
    parser.add_argument("--fig_pad", type=float, default=1.5, help="Padding for the figure to prevent cutoff.")
    args = parser.parse_args()

    # Apply font scaling
    bar_fontsize = int(args.bar_fontsize * args.fontscale)
    tick_fontsize = int(args.tick_fontsize * args.fontscale)
    legend_fontsize = int(args.legend_fontsize * args.fontscale)
    title_fontsize = int(args.title_fontsize * args.fontscale)
    
    folder_path = args.folder_path
    json_files = [os.path.join(folder_path, file) for file in os.listdir(folder_path) if file.endswith('.json')]
    
    results = {}
    standard_upd_accuracies = {}
    standard_file = None #To be set if a standard file is found
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
        print("WARNING: Not all categories have the same number of samples.")
    
    #Compute dual accuracies
    dual_accuracies = {}
    if standard_file:
        standard_score_list = results[standard_file]
        for json_file in json_files:
            if "standard" in json_file or "open_ended" in json_file:
                dual_accuracies[json_file] = 0
                continue
            if json_file != standard_file:
                upd_score_list = results[json_file]
                for i in range(len(standard_score_list)):
                    if standard_score_list[i] == 'T' and upd_score_list[i] == 'T':
                        dual_accuracies[json_file] = dual_accuracies.get(json_file, 0) + 1
    plt.figure(figsize=(10, 6))
    bar_height = 0.35
    y = list(range(len(standard_upd_accuracies)))  # y positions for bars
    
    # Plot standard accuracies as horizontal bars
    standard_values = list(standard_upd_accuracies.values())
    plt.barh(y, standard_values, height=bar_height, label='UPD (or Standard) Accuracy', color='blue')

    # Add raw and percent labels for standard accuracies with larger font size
    for i, (key, value) in enumerate(standard_upd_accuracies.items()):
        if value == 0:
            plt.text(value, y[i], "0", va='center', ha='left', rotation=0, fontsize=bar_fontsize)
        else:
            total = len(results[key])
            perc = (value / total) * 100
            plt.text(value, y[i], f"{value} ({perc:.1f}%)", va='center', ha='left', rotation=0, fontsize=bar_fontsize)
    
    # Plot dual accuracies as horizontal bars (increased thickness)
    if dual_accuracies:
        dual_values = [dual_accuracies.get(k, 0) for k in standard_upd_accuracies.keys()]
        plt.barh([yi + bar_height for yi in y], dual_values, height=bar_height, label='Dual Accuracy',
                 color='red')
    
        # Add raw and percent labels above dual accuracy bars with larger font size
        for i, (key, value) in enumerate(zip(standard_upd_accuracies.keys(), dual_values)):
            if "standard" in key or "open_ended" in key:
                plt.text(value, y[i] + bar_height, "Dual Acc N/A", va='center', ha='left', rotation=0, fontsize=bar_fontsize)
            else:
                if value == 0:
                    plt.text(value, y[i] + bar_height, "0", va='center', ha='left', rotation=0, fontsize=bar_fontsize)
                else:
                    total = len(results[key])
                    perc = (value / total) * 100
                    plt.text(value, y[i] + bar_height, f"{value} ({perc:.1f}%)", va='center', ha='left', rotation=0, fontsize=bar_fontsize)
    
    plt.xlabel("Test Samples Graded Correct", fontsize=tick_fontsize)
    plt.title(args.title, fontsize=title_fontsize)
    
    # Use category names on the y-axis
    names_list = list(standard_upd_accuracies.keys())
    # Remove scoring model name pattern (e.g., _gpt-4.1-mini_scored.json or _gpt-5-nano_scored.json)
    names_list = [re.sub(r'_[^_/]+_scored\.json$', '', name) for name in names_list]
    names_list = [name.split(args.naming_delim)[1] for name in names_list]
    names_list = [name.replace("_", " ") for name in names_list]
    names_list = [name.title() for name in names_list]

    def fix_acronyms(s):
        """
        make acronyms uppercase in the string s
        e.g. "aad" -> "AAD", "iasd" -> "IASD", "ivqd" -> "IVQD"
        """
        for acr in ["aad", "iasd", "ivqd"]:
            s = re.sub(r'(?i)\b' + acr + r'\b', acr.upper(), s)
        return s
    names_list = [fix_acronyms(name) for name in names_list]

    plt.yticks([yi + bar_height/2 for yi in y], names_list, fontsize=tick_fontsize)
    plt.legend(fontsize=legend_fontsize)
    plt.tight_layout(pad=args.fig_pad)
    # Set x-axis limit to the maximum number of samples in any category
    max_samples = max(len(results[k]) for k in standard_upd_accuracies.keys())
    plt.xlim(0, max_samples)
    # Hide the final tick at the upper bound but keep the axis ending at max_samples
    ax = plt.gca()
    ax.xaxis.set_major_locator(MaxNLocator(integer=True, prune='upper'))
    plt.xlabel(f"Test Samples Graded Correct (of {max_samples})", fontsize=tick_fontsize)
    plt.tick_params(axis='x', labelsize=args.tick_fontsize)

    output_dir = "./results"
    os.makedirs(output_dir, exist_ok=True)
    
    # Extract scoring model name from first json file
    scoring_model = "unknown"
    if json_files:
        first_file = os.path.basename(json_files[0])
        # Extract model name between last underscore before _scored.json
        match = re.search(r'_([^_/]+)_scored\.json$', first_file)
        if match:
            scoring_model = match.group(1)
    
    name_for_saving = os.path.basename(os.path.normpath(folder_path))
    # Add scoring model to filename
    output_path = os.path.join(output_dir, f"{name_for_saving}_{scoring_model}_bars.png")
    plt.savefig(output_path, dpi=300)
    print(f"Bar chart saved to: {os.path.abspath(output_path)}")

if __name__ == "__main__":
    main()