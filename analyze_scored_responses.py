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
    results_count = {}
    for json_file in json_files:
        with open(json_file, 'r') as f:
            data = json.load(f)

        # Extract scores from the data
        results[json_file] = [item["score"] for item in data.values()]
        results_count[json_file] = len([score for score in results[json_file] if score == 'T'])

    plt.figure(figsize=(10, 5))
    keys, values = zip(*results_count.items())
    plt.bar(keys, values, color='blue')

    plt.xlabel("JSON File")
    plt.ylabel("Count of 'T'")
    plt.title("Count of 'T' in Scored Responses")
    plt.tight_layout()
    plt.savefig("asdf.png")

if __name__ == "__main__":
    main()