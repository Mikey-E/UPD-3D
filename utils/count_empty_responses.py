# This file will take a .json file or a folder of .json files of inference results, and count the number of empty responses.
# Usage:
# python count_empty_responses.py path/to/your/file_or_folder.json
# This script will read the JSON file(s), count the number of items with empty 'response' fields, and print the count.
# Make sure to replace 'path/to/your/file_or_folder.json' with the actual path to your JSON file or folder.

# Example JSON structure:
"""
{
    "bf18f2a4-e180-4990-9ebb-1e52f4ab4e37@Lounge-55050": {
        "prompt": "What is the color of the top surface of the coffee table in the lounge?\n\nA. Black\nB. White\nC. Brown\nIf none of the above answers are correct, answer: 'F'",
        "response": "The color of the top surface of the coffee table in the lounge is brown."
    },
    "007c0c17-cd85-400a-bdf0-80f0e1eefe2d@MasterBedroom-36811": {
        "prompt": "What color is the ceiling lamp located in the room?\n\nA. Blue\nB. Green\nC. Yellow\nIf none of the above answers are correct, answer: 'F'",
        "response": "The ceiling lamp is not specified in the description."
    },
    ...
}
"""

import json
import argparse
import os
import glob

def count_empty_responses(file_path):
    """Count the number of empty responses and total responses in a JSON file."""
    try:
        with open(file_path, 'r') as file:
            data = json.load(file)
        total_count = len(data)
        empty_count = sum(1 for item in data.values() if not item.get('response', '').strip())
        return empty_count, total_count
    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found.")
        return 0, 0
    except json.JSONDecodeError:
        print(f"Error: The file '{file_path}' is not a valid JSON file.")
        return 0, 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Count empty responses in a JSON file or folder containing JSON files."
    )
    parser.add_argument(
        'path', type=str,
        help='Path to the JSON file or folder containing inference result JSON files.'
    )
    args = parser.parse_args()

    if os.path.isdir(args.path):
        for json_file in glob.glob(os.path.join(args.path, "*.json")):
            empty_count, total_count = count_empty_responses(json_file)
            percent = (empty_count / total_count * 100) if total_count else 0
            print(f"{os.path.basename(json_file)}: {empty_count}/{total_count} empty responses ({percent:.2f}%)")
    else:
        empty_count, total_count = count_empty_responses(args.path)
        percent = (empty_count / total_count * 100) if total_count else 0
        print(f"Number of empty responses: {empty_count}/{total_count} ({percent:.2f}%)")