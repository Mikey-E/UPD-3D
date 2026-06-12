"""Split MCQ .txt files into question-only and/or choices-only folders.

Standard mode (default) reads upd_text/<dataset>/standard and writes:
  - standard_question_no_choices
  - standard_choices_no_question

AAD mode (--aad-choices) reads upd_text/<dataset>/aad_base and writes:
  - aad_choices_no_question

Split boundary: first line whose trimmed content starts with A. / B. / C. / D.
"""

import argparse
import os
import re

CHOICE_LINE_RE = re.compile(r"^[A-D]\.\s")


def extract_choices(text):
    """Return choices block from MCQ text with surrounding whitespace stripped."""
    lines = text.splitlines()
    choice_idx = next(
        (i for i, line in enumerate(lines) if CHOICE_LINE_RE.match(line.strip())),
        None,
    )
    if choice_idx is None:
        raise ValueError("No A-D choice lines found")

    choice_lines = [line.strip() for line in lines[choice_idx:] if line.strip()]
    choices = "\n".join(choice_lines).strip()
    if not choices:
        raise ValueError("Choices text is empty after stripping")
    return choices


def split_standard_content(text):
    """Return (question_text, choices_text) with surrounding whitespace stripped."""
    lines = text.splitlines()
    choice_idx = next(
        (i for i, line in enumerate(lines) if CHOICE_LINE_RE.match(line.strip())),
        None,
    )
    if choice_idx is None:
        raise ValueError("No A-D choice lines found")

    question_lines = lines[:choice_idx]
    while question_lines and not question_lines[-1].strip():
        question_lines.pop()

    question = "\n".join(line.strip() for line in question_lines if line.strip()).strip()
    choices = extract_choices(text)

    if not question:
        raise ValueError("Question text is empty after stripping")

    return question, choices


def write_text(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def process_standard_folder(standard_dir, dry_run=False):
    dataset_dir = os.path.dirname(os.path.abspath(standard_dir))
    question_dir = os.path.join(dataset_dir, "standard_question_no_choices")
    choices_dir = os.path.join(dataset_dir, "standard_choices_no_question")

    if not dry_run:
        os.makedirs(question_dir, exist_ok=True)
        os.makedirs(choices_dir, exist_ok=True)

    processed = 0
    errors = []

    for filename in sorted(os.listdir(standard_dir)):
        if not filename.lower().endswith(".txt"):
            continue
        input_path = os.path.join(standard_dir, filename)
        question_path = os.path.join(question_dir, filename)
        choices_path = os.path.join(choices_dir, filename)

        try:
            with open(input_path, "r", encoding="utf-8") as f:
                text = f.read()
            question, choices = split_standard_content(text)
            if not dry_run:
                write_text(question_path, question)
                write_text(choices_path, choices)
            processed += 1
        except ValueError as exc:
            errors.append((filename, str(exc)))

    return {
        "processed": processed,
        "errors": errors,
        "question_dir": question_dir,
        "choices_dir": choices_dir,
    }


def process_aad_base_folder(aad_base_dir, dry_run=False):
    dataset_dir = os.path.dirname(os.path.abspath(aad_base_dir))
    choices_dir = os.path.join(dataset_dir, "aad_choices_no_question")

    if not dry_run:
        os.makedirs(choices_dir, exist_ok=True)

    processed = 0
    errors = []

    for filename in sorted(os.listdir(aad_base_dir)):
        if not filename.lower().endswith(".txt"):
            continue
        input_path = os.path.join(aad_base_dir, filename)
        choices_path = os.path.join(choices_dir, filename)

        try:
            with open(input_path, "r", encoding="utf-8") as f:
                text = f.read()
            choices = extract_choices(text)
            if not dry_run:
                write_text(choices_path, choices)
            processed += 1
        except ValueError as exc:
            errors.append((filename, str(exc)))

    return {
        "processed": processed,
        "errors": errors,
        "choices_dir": choices_dir,
    }


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Split MCQ .txt files into question-only and/or choices-only folders."
        )
    )
    parser.add_argument(
        "dataset",
        help="Dataset name under upd_text/ (e.g. 3D-FRONT)",
    )
    parser.add_argument(
        "--standard_dir",
        help="Override path to standard/ (default: upd_text/<dataset>/standard)",
    )
    parser.add_argument(
        "--aad_base_dir",
        help="Override path to aad_base/ (default: upd_text/<dataset>/aad_base)",
    )
    parser.add_argument(
        "--aad-choices",
        action="store_true",
        help="Also extract choices from aad_base into aad_choices_no_question",
    )
    parser.add_argument(
        "--aad-choices-only",
        action="store_true",
        help="Only extract choices from aad_base (skip standard split)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and validate without writing output files",
    )
    args = parser.parse_args()

    run_standard = not args.aad_choices_only
    run_aad = args.aad_choices or args.aad_choices_only

    if not run_standard and not run_aad:
        raise SystemExit("Nothing to do. Use default standard split, --aad-choices, or --aad-choices-only.")

    all_errors = []

    if run_standard:
        if args.standard_dir:
            standard_dir = os.path.abspath(args.standard_dir)
        else:
            standard_dir = os.path.join("upd_text", args.dataset, "standard")

        if not os.path.isdir(standard_dir):
            raise SystemExit(f"Standard directory not found: {standard_dir}")

        result = process_standard_folder(standard_dir, dry_run=args.dry_run)

        print(f"Standard dir: {standard_dir}")
        if args.dry_run:
            print("Mode: dry-run (no files written)")
        else:
            print(f"Question dir: {result['question_dir']}")
            print(f"Choices dir: {result['choices_dir']}")
        print(f"Processed: {result['processed']}")
        all_errors.extend(result["errors"])

    if run_aad:
        if args.aad_base_dir:
            aad_base_dir = os.path.abspath(args.aad_base_dir)
        else:
            aad_base_dir = os.path.join("upd_text", args.dataset, "aad_base")

        if not os.path.isdir(aad_base_dir):
            raise SystemExit(f"AAD base directory not found: {aad_base_dir}")

        result = process_aad_base_folder(aad_base_dir, dry_run=args.dry_run)

        print(f"AAD base dir: {aad_base_dir}")
        if args.dry_run:
            print("Mode: dry-run (no files written)")
        else:
            print(f"AAD choices dir: {result['choices_dir']}")
        print(f"Processed: {result['processed']}")
        all_errors.extend(result["errors"])

    if all_errors:
        print(f"Errors: {len(all_errors)}")
        for filename, message in all_errors[:20]:
            print(f"  {filename}: {message}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
