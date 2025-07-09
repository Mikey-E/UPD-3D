#Combines 2 json files into one single json file to make a file for MiniGPT-3D finetuning.
#ie this file exists to concatenate a json file of training data in a minigpt-3d repo with a formatted json file of upd training data.
#May also be fit for greenplm assuming captions are handled as well

import json
import argparse
import os

def combine_json_files(json_file1, json_file2, output_file):
    with open(json_file1, 'r', encoding='utf-8') as f:
        data1 = json.load(f)
    with open(json_file2, 'r', encoding='utf-8') as f:
        data2 = json.load(f)
    if not isinstance(data1, list) or not isinstance(data2, list):
        raise ValueError("Both JSON files must contain a list of objects.")
    combined = data1 + data2
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(combined, f, indent=2)
    print(f"Combined JSON written to {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Combine two JSON files into one single JSON file."
    )
    parser.add_argument("json_file1", help="Path to the first JSON file")
    parser.add_argument("json_file2", help="Path to the second JSON file")
    parser.add_argument("output_file", nargs="?", help="Path to output JSON file (default: combined.json in json_file1 directory)")
    args = parser.parse_args()

    output_file = args.output_file
    if not output_file:
        dir_name = os.path.dirname(os.path.abspath(args.json_file1))
        output_file = os.path.join(dir_name, "combined.json")

    combine_json_files(args.json_file1, args.json_file2, output_file)
