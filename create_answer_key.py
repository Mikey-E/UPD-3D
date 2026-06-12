"""
Create an answer-key JSON from standard_answer files.

By default, values are the correct option text (e.g. "Blue"), not the letter.
Output is written to answer_keys/<dataset>_text.json so existing letter keys
are not overwritten. Use --letter-keys to write letter-only keys to the legacy
filename answer_keys/<dataset>.json.
"""

import argparse
import json
import os
import re

CHOICE_LINE_RE = re.compile(r"^([A-Za-z])[.)]\s+(.*)$")


def extract_correct_letter(content):
    for line in content.splitlines():
        if line.strip().startswith("Correct answer:"):
            match = re.search(r"Correct answer:\s*([A-Za-z])", line)
            if match:
                return match.group(1).strip().upper()
    if content.strip():
        last = content.strip()[-1].upper()
        if last in {"A", "B", "C", "D"}:
            return last
    return None


def extract_correct_answer_text(content):
    """Return the option text for the correct answer in a standard_answer file."""
    lines = content.splitlines()
    correct_letter = extract_correct_letter(content)
    if not correct_letter:
        raise ValueError("Could not determine correct answer letter")

    for line in lines:
        match = CHOICE_LINE_RE.match(line.strip())
        if match and match.group(1).upper() == correct_letter:
            return match.group(2).strip()

    raise ValueError(f"No option line found for correct answer {correct_letter}")


def count_letter_values(data):
    counts = {"A": 0, "B": 0, "C": 0, "D": 0}
    for value in data.values():
        if value in counts:
            counts[value] += 1
    return counts


def resolve_standard_answer_path(version_folder):
    if os.path.isabs(version_folder) and os.path.exists(version_folder):
        base_path = version_folder
    elif os.path.exists(version_folder):
        base_path = version_folder
    elif os.path.exists(os.path.join("upd_text", version_folder)):
        base_path = os.path.join("upd_text", version_folder)
    else:
        raise FileNotFoundError(
            f"Version folder '{version_folder}' not found as absolute path, "
            "relative path, or under 'upd_text/'."
        )

    if os.path.basename(os.path.normpath(base_path)) == "standard_answer":
        standard_answer_path = base_path
        answer_key_name = os.path.basename(os.path.dirname(os.path.normpath(base_path)))
    else:
        standard_answer_path = os.path.join(base_path, "standard_answer")
        answer_key_name = os.path.basename(os.path.normpath(base_path))

    if not os.path.isdir(standard_answer_path):
        raise FileNotFoundError(
            f"'standard_answer' directory not found at '{standard_answer_path}'."
        )

    return standard_answer_path, answer_key_name


def build_answer_key(standard_answer_path, use_letters):
    answer_key = {}
    errors = []

    for filename in sorted(os.listdir(standard_answer_path)):
        if not filename.lower().endswith(".txt"):
            continue
        file_path = os.path.join(standard_answer_path, filename)
        scene_id = filename.replace(".txt", "")
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        if not content.strip():
            errors.append((scene_id, "empty file"))
            continue
        try:
            if use_letters:
                letter = extract_correct_letter(content)
                if not letter:
                    raise ValueError("missing correct answer letter")
                answer_key[scene_id] = letter
            else:
                answer_key[scene_id] = extract_correct_answer_text(content)
        except ValueError as exc:
            errors.append((scene_id, str(exc)))

    return answer_key, errors


def main():
    parser = argparse.ArgumentParser(
        description="Create an answer-key dictionary from standard_answer files."
    )
    parser.add_argument(
        "version_folder",
        help="Dataset folder name/path, or path to its standard_answer subfolder.",
    )
    parser.add_argument(
        "--letter-keys",
        action="store_true",
        help="Write legacy letter-only keys to answer_keys/<dataset>.json",
    )
    parser.add_argument(
        "--output",
        help="Override output JSON path",
    )
    args = parser.parse_args()

    standard_answer_path, answer_key_name = resolve_standard_answer_path(
        args.version_folder
    )
    use_letters = args.letter_keys
    answer_key, errors = build_answer_key(standard_answer_path, use_letters=use_letters)

    output_dir = "./answer_keys"
    os.makedirs(output_dir, exist_ok=True)

    if args.output:
        output_file = args.output
    elif use_letters:
        output_file = os.path.join(output_dir, f"{answer_key_name}.json")
    else:
        output_file = os.path.join(output_dir, f"{answer_key_name}_text.json")

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(answer_key, f, indent=4)

    print(f"Wrote {len(answer_key)} entries to {output_file}")
    if use_letters:
        counts = count_letter_values(answer_key)
        print("Counts of each answer letter:")
        for key, value in counts.items():
            print(f"{key}: {value}")
    if errors:
        print(f"Errors: {len(errors)}")
        for scene_id, message in errors[:10]:
            print(f"  {scene_id}: {message}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
