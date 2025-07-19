"""
This file takes a folder of _scored json files of model responses to UPD subsets, and makes a radar chart of the scores
"""

import argparse
import json
import matplotlib.pyplot as plt
import numpy as np
import os
import re

def main():
    parser = argparse.ArgumentParser(description="Analyze scored responses and create a radar chart.")
    parser.add_argument("folder_path", type=str, help="Path to the folder containing JSON files with scored responses.")
    parser.add_argument("--naming_delim", type=str, help="Delimiter in the file names to separate out subset name.", default="_3D-FRONT_test_")
    parser.add_argument("--title", type=str, required=True, help="Graph title.")
    parser.add_argument("--tick_fontsize", type=int, default=14, help="Font size for axis ticks and labels.")
    parser.add_argument("--legend_fontsize", type=int, default=13, help="Font size for legend text.")
    parser.add_argument("--title_fontsize", type=int, default=19, help="Font size for title text.")
    args = parser.parse_args()

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
    if standard_file:
        standard_score_list = results[standard_file]
        dual_accuracies = {}
        for json_file in json_files:
            if "standard" in json_file or "open_ended" in json_file:
                dual_accuracies[json_file] = 0
                continue
            if json_file != standard_file:
                upd_score_list = results[json_file]
                for i in range(len(standard_score_list)):
                    if standard_score_list[i] == 'T' and upd_score_list[i] == 'T':
                        dual_accuracies[json_file] = dual_accuracies.get(json_file, 0) + 1
    
    # Prepare category names for the radar chart
    names_list = list(standard_upd_accuracies.keys())
    names_list = [name.replace("_scored.json", "") for name in names_list]
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
    categories = [fix_acronyms(name) for name in names_list]
    
    # Prepare data for radar chart
    N = len(categories)
    standard_values = list(standard_upd_accuracies.values())
    
    # Set up the angles for the radar chart (evenly spaced around the circle)
    angles = np.linspace(0, 2*np.pi, N, endpoint=False).tolist()
    
    # Close the radar chart by appending the first angle & value at the end
    angles += angles[:1]
    standard_values_plot = standard_values + [standard_values[0]]
    categories_plot = categories + [categories[0]]
    
    # Create figure and polar axis
    fig, ax = plt.subplots(figsize=(10, 8), subplot_kw=dict(polar=True))
    
    # Plot standard accuracies
    ax.plot(angles, standard_values_plot, 'o-', linewidth=2, label='UPD (or Standard) Accuracy', color='blue')
    ax.fill(angles, standard_values_plot, alpha=0.25, color='blue')
    
    # Plot dual accuracies if available
    if 'dual_accuracies' in locals():
        dual_values = [dual_accuracies.get(k, 0) for k in standard_upd_accuracies.keys()]
        dual_values_plot = dual_values + [dual_values[0]]
        ax.plot(angles, dual_values_plot, 'o-', linewidth=2, label='Dual Accuracy', color='red')
        ax.fill(angles, dual_values_plot, alpha=0.25, color='red')
    
    # Set category labels
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, size=args.tick_fontsize)
    
    # Set title and legend
    plt.title(args.title, size=args.title_fontsize, y=1.1)
    plt.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1), fontsize=args.legend_fontsize)
    
    # Set y-axis limit to the maximum number of samples in any category
    max_samples = max(len(results[k]) for k in standard_upd_accuracies.keys())
    ax.set_ylim(0, max_samples)
    
    plt.tight_layout()
    
    # Save the figure
    output_dir = "./results"
    os.makedirs(output_dir, exist_ok=True)
    
    name_for_saving = os.path.basename(os.path.normpath(folder_path))
    plt.savefig(os.path.join(output_dir, f"{name_for_saving}_radar.png"), dpi=300)

if __name__ == "__main__":
    main()