"""
This file takes a folder of _scored json files of model responses to UPD subsets, and makes a graph of the scores
"""

import argparse
import json
import matplotlib.pyplot as plt
import os

def main():
    parser = argparse.ArgumentParser(description="Analyze scored responses and create a bar graph.")
    parser.add_argument("folder_path", type=str, help="Path to the folder containing JSON files with scored responses.")
    parser.add_argument("--naming_delim", type=str, help="Delimiter in the file names to separate out subset name.", default="_v1_")
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

    plt.figure(figsize=(10, 6))
    bar_width = 0.35
    spacing = 0.00  # Add spacing between bar groups
    x = [i * (1 + spacing) for i in range(len(standard_upd_accuracies))]  # Adjust x-coordinates with spacing
    
    # Plot standard accuracies
    standard_values = list(standard_upd_accuracies.values())
    plt.bar([i for i in x], standard_values, 
            bar_width, label='Standard or UPD Accuracy', color='blue')

    # Add numbers on top of standard accuracy bars
    for i, value in enumerate(standard_values):
        plt.text(x[i], value, str(value), ha='center', va='bottom')

    # Plot dual accuracies if they exist
    if dual_accuracies:
        dual_values = [dual_accuracies.get(k, 0) for k in standard_upd_accuracies.keys()]
        plt.bar([i + bar_width for i in x], dual_values,
                bar_width, label='Dual Accuracy', color='red')

        # Add numbers on top of dual accuracy bars
        for i, (key, value) in enumerate(zip(standard_upd_accuracies.keys(), dual_values)):
            if "standard" in key or "open_ended" in key:
                plt.text(x[i] + bar_width, value, "N/A", ha='center', va='bottom')
            else:
                plt.text(x[i] + bar_width, value, str(value), ha='center', va='bottom')

    plt.xlabel("Category")
    plt.ylabel("Count")
    plt.title("Standard (or UPD) and Dual Accuracies in Scored Responses")
    
    #Must reduce length of x axis labels to fit
    names_list = list(standard_upd_accuracies.keys())
    names_list = [name.replace("_scored.json", "") for name in names_list]
    names_list = [name.split(args.naming_delim)[1] for name in names_list]
    names_list = [name.replace("_", " ") for name in names_list]
    plt.xticks([i + bar_width/2 for i in x], names_list, rotation=45, ha='right', rotation_mode='anchor')

    plt.legend()
    plt.tight_layout()

    # Create the output directory if it doesn't exist
    output_dir = "./results"
    os.makedirs(output_dir, exist_ok=True)

    name_for_saving = os.path.basename(os.path.normpath(folder_path))
    plt.savefig(os.path.join(output_dir, f"{name_for_saving}_bars.png"))

if __name__ == "__main__":
    main()