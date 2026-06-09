# Format UPD .txt QA files for MiniGPT-3D / PointLLM-style JSON, using only
# standard_answer and aad_base (no additional_option / additional_instruction variants).
# For aad_base, the gpt response is the correct option text from the matching
# standard_answer file, not "There is no correct answer".

import os
import re
import json
import argparse

ALLOWED_SUBFOLDERS = frozenset({"standard_answer", "aad_base"})


def extract_correct_option_text(lines):
    """Parse standard_answer content; return (option_text, question_and_options_text)."""
    correct_idx = None
    correct_letter = None
    for i, line in enumerate(lines):
        if line.strip().startswith("Correct answer:"):
            correct_idx = i
            m = re.search(r"Correct answer:\s*([A-Za-z])", line)
            if m:
                correct_letter = m.group(1).strip()
            break
    human_text = (
        "".join(lines[:correct_idx]).strip()
        if correct_idx is not None
        else "".join(lines).strip()
    )
    option_text = ""
    if correct_letter:
        for line in human_text.splitlines():
            m = re.match(r"([A-Za-z])\.\s+(.*)", line)
            if m and m.group(1).strip().upper() == correct_letter.upper():
                option_text = m.group(2).strip()
                break
    return option_text, human_text


def build_standard_answer_lookup(standard_answer_dir, pcl_set=None):
    """Map scene base_name -> correct option text from standard_answer files."""
    lookup = {}
    for filename in os.listdir(standard_answer_dir):
        if not filename.lower().endswith(".txt"):
            continue
        base_name = os.path.splitext(filename)[0]
        if pcl_set is not None and base_name not in pcl_set:
            continue
        file_path = os.path.join(standard_answer_dir, filename)
        with open(file_path, "r", encoding="utf-8") as f:
            option_text, _ = extract_correct_option_text(f.readlines())
        if option_text:
            lookup[base_name] = option_text
    return lookup


def parse_txt_file(
    file_path,
    subfolder,
    standard_answer_lookup=None,
    caption_folder=None,
    conversation_type="single_round",
    point_ext=".ply",
):
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    base_name = os.path.splitext(os.path.basename(file_path))[0]

    if subfolder == "standard_answer":
        option_text, human_text = extract_correct_option_text(lines)
    elif subfolder == "aad_base":
        human_text = "".join(lines).strip()
        option_text = ""
        if standard_answer_lookup is not None:
            option_text = standard_answer_lookup.get(base_name, "")
        if not option_text:
            raise ValueError(
                f"No standard_answer correct option for aad_base file: {base_name}"
            )
    else:
        raise ValueError(f"Unexpected subfolder: {subfolder}")

    result = {
        "id": base_name,
        "object_id": base_name,
        "point": base_name + point_ext,
        "rotation": [0, 0, 0],
        "conversation_type": conversation_type,
        "conversations": [
            {"from": "human", "value": human_text},
            {"from": "gpt", "value": option_text},
        ],
    }
    if caption_folder:
        caption_path = os.path.join(
            caption_folder, base_name + ".txt"
        )
        if os.path.exists(caption_path):
            with open(caption_path, "r", encoding="utf-8") as cf:
                result["caption"] = cf.read().strip()
    return result


def process_directory(
    input_dir,
    output_file,
    subfolder,
    standard_answer_lookup=None,
    pcl_set=None,
    caption_folder=None,
    conversation_type="single_round",
    point_ext=".ply",
):
    objects = []
    for filename in os.listdir(input_dir):
        if filename.lower().endswith(".txt"):
            base_name = os.path.splitext(filename)[0]
            if pcl_set is not None and base_name not in pcl_set:
                continue
            file_path = os.path.join(input_dir, filename)
            objects.append(
                parse_txt_file(
                    file_path,
                    subfolder,
                    standard_answer_lookup,
                    caption_folder,
                    conversation_type,
                    point_ext,
                )
            )
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(objects, f, indent=2)


def process_overall_directory(
    overall_dir,
    output_file,
    pcl_set=None,
    caption_folder=None,
    conversation_type="single_round",
    point_ext=".ply",
):
    subfolders = [
        d
        for d in os.listdir(overall_dir)
        if os.path.isdir(os.path.join(overall_dir, d))
    ]
    if "standard_answer" not in subfolders:
        raise ValueError("The overall directory must contain a 'standard_answer' subfolder.")
    if "aad_base" not in subfolders:
        raise ValueError("The overall directory must contain an 'aad_base' subfolder.")

    standard_answer_dir = os.path.join(overall_dir, "standard_answer")
    standard_answer_lookup = build_standard_answer_lookup(
        standard_answer_dir, pcl_set
    )

    all_objects = []
    for subfolder in sorted(ALLOWED_SUBFOLDERS):
        if subfolder not in subfolders:
            continue
        subfolder_path = os.path.join(overall_dir, subfolder)
        print(f"Current folder: {subfolder}")
        file_count = 0
        lookup = (
            standard_answer_lookup if subfolder == "aad_base" else None
        )
        for filename in os.listdir(subfolder_path):
            if filename.lower().endswith(".txt"):
                base_name = os.path.splitext(filename)[0]
                if pcl_set is not None and base_name not in pcl_set:
                    continue
                file_path = os.path.join(subfolder_path, filename)
                all_objects.append(
                    parse_txt_file(
                        file_path,
                        subfolder,
                        lookup,
                        caption_folder,
                        conversation_type,
                        point_ext,
                    )
                )
                file_count += 1
        print(f"File count processed: {file_count}")

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_objects, f, indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Convert standard_answer and aad_base .txt files to JSON. "
            "aad_base uses correct answers from matching standard_answer files."
        )
    )
    parser.add_argument(
        "input_dir",
        help="Path to standard_answer/, aad_base/, or overall dataset directory",
    )
    parser.add_argument(
        "--overall_directory",
        action="store_true",
        help="Process overall directory (standard_answer + aad_base only)",
    )
    parser.add_argument(
        "--pcl_list",
        help="Path to .txt file of allowed scene names (no .txt extension per line)",
    )
    parser.add_argument(
        "--caption",
        help="Path to folder containing caption .txt files (text_basis)",
    )
    parser.add_argument(
        "--conversation_type",
        default="single_round",
        help="Conversation type to include in each object",
    )
    parser.add_argument(
        "--point_ext", default=".ply", help="Extension for the point field"
    )
    parser.add_argument(
        "--output",
        help="Output JSON path (default: utils/upd-3d/overall_<tag>_AAD.json)",
    )
    args = parser.parse_args()

    pcl_set = None
    pcl_list_tag = None
    if args.pcl_list:
        with open(args.pcl_list, "r", encoding="utf-8") as f:
            pcl_set = {line.strip() for line in f if line.strip()}
        pcl_list_tag = os.path.splitext(os.path.basename(args.pcl_list))[0]

    caption_folder = args.caption
    conversation_type = args.conversation_type
    point_ext = args.point_ext

    if args.output:
        output_file = args.output
    elif args.overall_directory:
        tag = pcl_list_tag or os.path.basename(os.path.abspath(args.input_dir))
        output_file = os.path.join(
            os.path.dirname(__file__),
            f"overall_{tag}_AAD" + ("_captions" if caption_folder else "") + ".json",
        )
    else:
        tag = pcl_list_tag or os.path.basename(os.path.abspath(args.input_dir))
        subfolder = os.path.basename(os.path.abspath(args.input_dir))
        output_file = os.path.join(
            os.path.dirname(__file__),
            f"{tag}_{subfolder}_AAD"
            + ("_captions" if caption_folder else "")
            + ".json",
        )

    if args.overall_directory:
        process_overall_directory(
            args.input_dir,
            output_file,
            pcl_set,
            caption_folder,
            conversation_type,
            point_ext,
        )
    else:
        input_dir = os.path.abspath(args.input_dir)
        subfolder = os.path.basename(input_dir)
        if subfolder not in ALLOWED_SUBFOLDERS:
            raise ValueError(
                f"Single-directory mode requires one of {sorted(ALLOWED_SUBFOLDERS)}, "
                f"got: {subfolder}"
            )
        lookup = None
        if subfolder == "aad_base":
            parent = os.path.dirname(input_dir)
            standard_answer_dir = os.path.join(parent, "standard_answer")
            if not os.path.isdir(standard_answer_dir):
                raise ValueError(
                    f"aad_base requires sibling standard_answer at {standard_answer_dir}"
                )
            lookup = build_standard_answer_lookup(standard_answer_dir, pcl_set)
        process_directory(
            input_dir,
            output_file,
            subfolder,
            lookup,
            pcl_set,
            caption_folder,
            conversation_type,
            point_ext,
        )

    print(f"Output written to {output_file}")
