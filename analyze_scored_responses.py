"""
This file takes a folder of _graded json files of model responses to UPD subsets, and makes a graph of the scores
"""

import argparse
import json
import matplotlib.pyplot as plt
import os

def main():
    parser = argparse.ArgumentParser(description="Analyze scored responses and create a bar graph.")
    parser.add_argument("folder_path", type=str, help="Path to the folder containing JSON files with scored responses.")
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
            if json_file != standard_file:
                upd_score_list = results[json_file]
                for i in range(len(standard_score_list)):
                    if standard_score_list[i] == 'T' and upd_score_list[i] == 'T':
                        dual_accuracies[json_file] = dual_accuracies.get(json_file, 0) + 1

    plt.figure(figsize=(10, 5))
    bar_width = 0.35
    x = range(len(standard_upd_accuracies))
    
    # Plot standard accuracies
    plt.bar([i for i in x], list(standard_upd_accuracies.values()), 
            bar_width, label='Standard Accuracy', color='blue')
    
    # Plot dual accuracies if they exist
    if dual_accuracies:
        # Only plot for keys that have dual accuracies
        dual_values = [dual_accuracies.get(k, 0) for k in standard_upd_accuracies.keys()]
        plt.bar([i + bar_width for i in x], dual_values,
                bar_width, label='Dual Accuracy', color='red')
    
    plt.xlabel("JSON File")
    plt.ylabel("Count")
    plt.title("Standard (or UPD) and Dual Accuracies in Scored Responses")
    plt.xticks([i + bar_width/2 for i in x], list(standard_upd_accuracies.keys()), rotation=45)
    plt.legend()
    plt.tight_layout()

    # Create the output directory if it doesn't exist
    output_dir = "./results"
    os.makedirs(output_dir, exist_ok=True)

    plt.savefig(os.path.join(output_dir, f"{folder_path}_bars.png"))

if __name__ == "__main__":
    main()