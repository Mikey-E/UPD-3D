"""
This file takes a path to a version of the UPD dataset, where it will then create a dictionary of answers based on the standard_answer file
"""

import argparse
import os
import json

def main():
    parser = argparse.ArgumentParser(description="Create an answer key dictionary from the standard_answer subfolder.")
    parser.add_argument("version_path", type=str, help="Path to the version of the UPD dataset.")
    args = parser.parse_args()

    version_path = args.version_path
    standard_answer_path = os.path.join(version_path, "standard_answer")
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

    # Determine the output JSON file name
    folder_name = os.path.basename(os.path.normpath(version_path))
    output_file = os.path.join(output_dir, f"{folder_name}.json")

    # Dump the dictionary into the JSON file
    with open(output_file, 'w') as f:
        json.dump(answer_key, f, indent=4)

if __name__ == "__main__":
    main()