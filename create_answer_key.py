"""
This file takes a path to a version of the UPD dataset, where it will then create a dictionary of answers based on the standard_answer files
"""

import argparse
import os
import json

def count_answer_values(data):
    """
    Counts the occurrences of each answer value (A, B, C, D) in a dictionary.
    Args:
        data (dict): A dictionary where keys are filenames and values are answers.
    Returns:
        dict: A dictionary containing the counts of each answer value.
    """
    counts = {'A': 0, 'B': 0, 'C': 0, 'D': 0}
    for value in data.values():
        if value in counts:
            counts[value] += 1
    return counts

def main():
    # Parse only the folder name of the version
    parser = argparse.ArgumentParser(description="Create an answer key dictionary from the standard_answer subfolder.")
    parser.add_argument("version_folder", type=str, help="Name or path of the version folder or its standard_answer subfolder.")
    args = parser.parse_args()

    # Resolve version_folder input (absolute path, relative path, under upd_text/)
    vf = args.version_folder
    if os.path.isabs(vf) and os.path.exists(vf):
        base_path = vf
    elif os.path.exists(vf):
        base_path = vf
    elif os.path.exists(os.path.join("upd_text", vf)):
        base_path = os.path.join("upd_text", vf)
    else:
        raise FileNotFoundError(f"Version folder '{vf}' not found as absolute path, relative path, or under 'upd_text/'.")

    # Determine the standard_answer directory
    if os.path.basename(os.path.normpath(base_path)) == "standard_answer":
        standard_answer_path = base_path
    else:
        standard_answer_path = os.path.join(base_path, "standard_answer")
    if not os.path.isdir(standard_answer_path):
        raise FileNotFoundError(f"'standard_answer' directory not found at '{standard_answer_path}'.")

    answer_key = {}

    # Process each file in the standard_answer subfolder
    for filename in os.listdir(standard_answer_path):
        file_path = os.path.join(standard_answer_path, filename)
        if os.path.isfile(file_path):
            with open(file_path, 'r') as f:
                content = f.read()
                if content:  # Ensure the file is not empty
                    answer_key[filename.replace(".txt", "")] = content[-1]  # Last character of the file

    # Create the output directory if it doesn't exist
    output_dir = "./answer_keys"
    os.makedirs(output_dir, exist_ok=True)

    # Determine the output JSON file name using the version folder name
    output_file = os.path.join(output_dir, f"{os.path.basename(os.path.normpath(base_path))}.json")

    # Dump the dictionary into the JSON file
    with open(output_file, 'w') as f:
        json.dump(answer_key, f, indent=4)

    # Count and print the answer values
    counts = count_answer_values(answer_key)
    print("Counts of each answer value:")
    for key, value in counts.items():
        print(f"{key}: {value}")

if __name__ == "__main__":
    main()