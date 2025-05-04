"""
After you make a list of point cloud file names from 3D-GRAND's 3D-FRONT in the pcl_lists directory, this file will gather the text associated with each one. This text can then later be used to generate multiple choice questions about each point cloud.
"""

import argparse
import os
import json

# Set up argument parser
parser = argparse.ArgumentParser(description="Take a .txt list of pcl, gather text.")
parser.add_argument("txt_file", type=str, help="Name of the .txt file")
parser.add_argument("--json_file", type=str, default="grounded_scene_description.json", help="Name of the JSON file from 3D-GRAND")

# Parse arguments
args = parser.parse_args()

# Validate the file extension for the .txt file
if not args.txt_file.endswith('.txt'):
    print("Error: The provided file must have a .txt extension.")
    exit(1)

# Validate the file extension for the .json file
if not args.json_file.endswith('.json'):
    print("Error: The provided file must have a .json extension.")
    exit(1)

txt_file = args.txt_file
json_file = args.json_file

# Create the "text_basis" directory if it doesn't exist
os.makedirs("text_basis", exist_ok=True)

# Create a subdirectory inside "text_basis" named after the .txt file
subdir_name = os.path.splitext(os.path.basename(txt_file))[0]
subdir_path = os.path.join("text_basis", subdir_name)
os.makedirs(subdir_path, exist_ok=True)

# Open the JSON file and print the first item
json_file_path = os.path.join("data", "data", "3D-FRONT", "text_annotation", json_file)
text_file_path = os.path.join("pcl_lists", txt_file)
with open(json_file_path, 'r') as f:
    data = json.load(f)
    with open(text_file_path, 'r') as f2:
        while True:
            line = f2.readline().strip()
            if not line:  # Exit loop if we reach end of file
                break
            try:
                with open(os.path.join(subdir_path, line) + ".txt", 'w') as f3:
                    f3.write(str(data[line]))
            except Exception as e:
                print(f"Error: {str(e)}")
                exit(1)