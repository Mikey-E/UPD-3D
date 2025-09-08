#File to take standard_answer .txt files and convert them to a single json file that can be pretty much just concatenated to the existing MiniGPT-3D training data file PointLLM_brief_description_660K.json
#May also be fit for greenplm assuming captions are handled as well

import os
import re
import json
import argparse

def parse_txt_file(file_path, is_standard_answer, dataset):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    if is_standard_answer:
        correct_idx = None
        correct_letter = None
        for i, line in enumerate(lines):
            if line.strip().startswith("Correct answer:"):
                correct_idx = i
                m = re.search(r"Correct answer:\s*([A-Za-z])", line)
                if m:
                    correct_letter = m.group(1).strip()
                break
        human_text = ''.join(lines[:correct_idx]).strip() if correct_idx is not None else ''.join(lines).strip()
        option_text = ""
        for line in human_text.splitlines():
            m = re.match(r"([A-Za-z])\.\s+(.*)", line)
            if m and m.group(1).strip().upper() == correct_letter.upper():
                option_text = m.group(2).strip()
                break
    else:
        human_text = ''.join(lines).strip()
        option_text = "There is no correct answer"
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    result = {
        "video": base_name,
        "conversations": [
            {"from": "human", "value": human_text},
            {"from": "gpt", "value": option_text}
        ],
        "metadata": {
            "dataset": dataset,
            "question_type": "single-round"
        }
    }
    return result

def process_directory(input_dir, output_file, dataset, pcl_set=None):
    objects = []
    is_standard_answer = os.path.basename(os.path.abspath(input_dir)) == "standard_answer"
    for filename in os.listdir(input_dir):
        if filename.lower().endswith('.txt'):
            base_name = os.path.splitext(filename)[0]
            if pcl_set is not None and base_name not in pcl_set:
                continue
            file_path = os.path.join(input_dir, filename)
            obj = parse_txt_file(file_path, is_standard_answer, dataset)
            objects.append(obj)
    # assign sequential id starting at 0
    for idx, obj in enumerate(objects):
        obj['id'] = idx
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(objects, f, indent=2)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Process txt files and convert them to a single json file."
    )
    parser.add_argument("input_dir", help="Path to the directory containing standard_answer .txt files or overall directory")
    parser.add_argument("--overall_directory", action="store_true", help="Process overall directory containing multiple subfolders")
    parser.add_argument("--pcl_list", help="Path to a .txt file containing allowed file names (each scene name inside the file should not end with .txt extension)")
    parser.add_argument("--dataset", required=True, help="Dataset to include in metadata")
    args = parser.parse_args()

    pcl_set = None
    pcl_list_tag = None
    if args.pcl_list:
        with open(args.pcl_list, 'r', encoding='utf-8') as f:
            pcl_set = {line.strip() for line in f if line.strip()}
        pcl_list_tag = os.path.splitext(os.path.basename(args.pcl_list))[0]

    if args.overall_directory:
        overall_dir = args.input_dir
        subfolders = [d for d in os.listdir(overall_dir) if os.path.isdir(os.path.join(overall_dir, d))]
        if "standard_answer" not in subfolders:
            raise ValueError("The overall directory must contain a 'standard_answer' subfolder.")
        all_objects = []
        for subfolder in subfolders:
            if subfolder == "standard":
                continue
            subfolder_path = os.path.join(overall_dir, subfolder)
            is_standard_answer = (subfolder == "standard_answer")
            print(f"Current folder: {subfolder}")
            file_count = 0
            for filename in os.listdir(subfolder_path):
                if filename.lower().endswith('.txt'):
                    base_name = os.path.splitext(filename)[0]
                    if pcl_set is not None and base_name not in pcl_set:
                        continue
                    file_path = os.path.join(subfolder_path, filename)
                    all_objects.append(parse_txt_file(file_path, is_standard_answer, args.dataset))
                    file_count += 1
            print(f"File count processed: {file_count}")
        for idx, obj in enumerate(all_objects):
            obj['id'] = idx
        output_file = os.path.join(
            os.path.dirname(__file__),
            f"overall_{pcl_list_tag if pcl_list_tag else os.path.basename(os.path.abspath(overall_dir))}.json"
        )
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_objects, f, indent=2)
        print(f"Output written to {output_file}")
    else:
        input_dir = args.input_dir
        output_file = os.path.join(
            os.path.dirname(__file__),
            f"{pcl_list_tag if pcl_list_tag else os.path.basename(os.path.abspath(input_dir))}.json"
        )
        process_directory(input_dir, output_file, args.dataset, pcl_set)
        print(f"Output written to {output_file}")