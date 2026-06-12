"""Map question-only model responses onto MCQ choices via an LLM judge.

Stage 2 of the q_no_c pipeline:
  1. Present the free-form response and choice list to an OpenAI judge.
  2. If a choice matches in meaning, output that choice text.
  3. Otherwise, keep the original free-form response.

Writes two unscored JSON files (standard and aad_base), matching the
cosine_choice_select.py output layout.
"""

import argparse
import json
import os
import re
import time

import openai

CHOICE_LINE_RE = re.compile(r"^([A-D])\.\s+(.*)$")
DEFAULT_JUDGE_MODEL = "gpt-4.1-mini"
DEFAULT_PROMPT_FILE = os.path.join(
    os.path.dirname(__file__), "llm_judge_choice_prompt.txt"
)
VALID_JUDGE_OUTPUTS = {"A", "B", "C", "D", "NONE"}


def resolve_responses_dir(responses_dir):
    if not os.path.isabs(responses_dir) and not os.path.isdir(responses_dir):
        candidate = os.path.join("q_no_c_model_responses", responses_dir)
        if os.path.isdir(candidate):
            return candidate
    return responses_dir


def find_responses_json(responses_dir):
    candidates = sorted(
        f
        for f in os.listdir(responses_dir)
        if f.startswith("inf_rslts") and f.endswith(".json")
    )
    if not candidates:
        raise FileNotFoundError(f"No inf_rslts*.json found in {responses_dir}")
    if len(candidates) > 1:
        raise FileNotFoundError(
            f"Expected one inf_rslts*.json in {responses_dir}, found {len(candidates)}"
        )
    return os.path.join(responses_dir, candidates[0])


def parse_choices_file(path):
    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    choices = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        match = CHOICE_LINE_RE.match(line)
        if not match:
            raise ValueError(f"Invalid choice line in {path}: {line!r}")
        choices.append(
            {
                "letter": match.group(1),
                "text": match.group(2).strip(),
                "line": f"{match.group(1)}. {match.group(2).strip()}",
            }
        )
    if not choices:
        raise ValueError(f"No choices found in {path}")
    return choices


def load_text_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def derive_output_filenames(input_json_name):
    base, ext = os.path.splitext(input_json_name)
    if "standard_question_no_choices" in base:
        std_name = base.replace("standard_question_no_choices", "standard") + ext
        aad_name = base.replace("standard_question_no_choices", "aad_base") + ext
    else:
        std_name = f"{base}_standard{ext}"
        aad_name = f"{base}_aad_base{ext}"
    return std_name, aad_name


def derive_output_suffix(judge_model, output_suffix):
    if output_suffix:
        return output_suffix
    slug = judge_model.replace("/", "_")
    return f"judge_{slug}"


def format_choices_for_prompt(choices):
    return "\n".join(choice["line"] for choice in choices)


def build_judge_prompt(base_prompt, free_form_response, choices):
    prompt = base_prompt.strip()
    prompt += f"\nFREE_FORM_RESPONSE: {free_form_response}"
    prompt += "\nCHOICES:"
    prompt += "\n" + format_choices_for_prompt(choices)
    return prompt


def call_judge(client, judge_model, prompt, max_attempts=5):
    last_error = None
    for _ in range(max_attempts):
        try:
            response = client.chat.completions.create(
                model=judge_model,
                messages=[{"role": "user", "content": prompt}],
                max_completion_tokens=4,
            )
            generated_text = (
                response.choices[0].message.content.strip()
                if response.choices[0].message.content
                else ""
            )
            token = generated_text.strip().upper().split()[0].rstrip(".")
            if token in VALID_JUDGE_OUTPUTS:
                return token, generated_text
            last_error = f"Invalid judge output: {generated_text!r}"
        except Exception as exc:
            last_error = str(exc)
            time.sleep(1)
    raise RuntimeError(last_error or "Judge call failed")


def select_response_from_judgment(original_response, choices, judge_letter):
    if judge_letter == "NONE":
        return original_response, None, False

    for choice in choices:
        if choice["letter"] == judge_letter:
            return choice["line"], choice["letter"], True

    return original_response, judge_letter, False


def build_output_entry(
    prompt,
    original_response,
    selected_response,
    judge_letter,
    judge_model,
    selected_from_choices,
    judge_raw=None,
):
    entry = {
        "prompt": prompt,
        "response": selected_response,
        "judge_choice_letter": judge_letter,
        "judge_model": judge_model,
        "selected_from_choices": selected_from_choices,
    }
    if judge_raw is not None:
        entry["judge_raw"] = judge_raw
    if selected_from_choices:
        entry["original_response"] = original_response
    return entry


def process_variant(
    client,
    judge_model,
    base_prompt,
    responses,
    prompts_dir,
    choices_dir,
    variant_name,
    limit=None,
):
    output = {}
    missing_prompt = 0
    missing_choices = 0
    processed = 0

    for scene_id, item in responses.items():
        if limit is not None and processed >= limit:
            break

        prompt_path = os.path.join(prompts_dir, f"{scene_id}.txt")
        choices_path = os.path.join(choices_dir, f"{scene_id}.txt")
        if not os.path.exists(prompt_path):
            missing_prompt += 1
            continue
        if not os.path.exists(choices_path):
            missing_choices += 1
            continue

        prompt = load_text_file(prompt_path)
        choices = parse_choices_file(choices_path)
        original_response = item["response"]

        if not original_response.strip():
            output[scene_id] = build_output_entry(
                prompt,
                original_response,
                original_response,
                "NONE",
                judge_model,
                False,
            )
            processed += 1
            continue

        judge_prompt = build_judge_prompt(base_prompt, original_response, choices)
        try:
            judge_letter, judge_raw = call_judge(client, judge_model, judge_prompt)
        except RuntimeError as exc:
            print(f"Warning: judge failed for {scene_id}: {exc}")
            output[scene_id] = build_output_entry(
                prompt,
                original_response,
                original_response,
                None,
                judge_model,
                False,
                judge_raw="ERROR",
            )
            processed += 1
            continue

        selected_response, mapped_letter, selected_from_choices = (
            select_response_from_judgment(original_response, choices, judge_letter)
        )
        output[scene_id] = build_output_entry(
            prompt,
            original_response,
            selected_response,
            mapped_letter if selected_from_choices else judge_letter,
            judge_model,
            selected_from_choices,
            judge_raw=judge_raw,
        )
        processed += 1

        if processed % 50 == 0:
            print(f"{variant_name}: processed {processed}", flush=True)

    if missing_prompt:
        print(f"Warning: skipped {missing_prompt} samples missing prompts in {prompts_dir}")
    if missing_choices:
        print(f"Warning: skipped {missing_choices} samples missing choices in {choices_dir}")

    print(f"{variant_name}: wrote {len(output)} entries")
    return output


def run_apply(args, responses, responses_dir):
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY environment variable is not set.")

    with open(args.judge_prompt_file, "r", encoding="utf-8") as f:
        base_prompt = f.read()

    client = openai.OpenAI()
    responses_dir = os.path.abspath(responses_dir)
    subfolder = os.path.basename(responses_dir)
    suffix = derive_output_suffix(args.judge_model, args.output_suffix)
    output_dir = os.path.join("unscored_model_responses", f"{subfolder}_{suffix}")
    os.makedirs(output_dir, exist_ok=True)

    input_json_name = os.path.basename(find_responses_json(responses_dir))
    std_name, aad_name = derive_output_filenames(input_json_name)

    std_output = process_variant(
        client,
        args.judge_model,
        base_prompt,
        responses,
        args.std_prompts_dir,
        args.std_choices_dir,
        "standard",
        args.limit,
    )
    aad_output = process_variant(
        client,
        args.judge_model,
        base_prompt,
        responses,
        args.aad_prompts_dir,
        args.aad_choices_dir,
        "aad_base",
        args.limit,
    )

    std_path = os.path.join(output_dir, std_name)
    aad_path = os.path.join(output_dir, aad_name)
    with open(std_path, "w", encoding="utf-8") as f:
        json.dump(std_output, f, indent=2)
    with open(aad_path, "w", encoding="utf-8") as f:
        json.dump(aad_output, f, indent=2)

    print(f"Standard output: {std_path}")
    print(f"AAD output: {aad_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Select MCQ answers from q_no_c responses via an LLM judge."
    )
    parser.add_argument(
        "--responses_dir",
        required=True,
        help="Subfolder under q_no_c_model_responses/ containing one inf_rslts*.json",
    )
    parser.add_argument(
        "--std_prompts_dir",
        required=True,
        help="Path to standard/ prompts (full MCQ text)",
    )
    parser.add_argument(
        "--aad_prompts_dir",
        required=True,
        help="Path to aad_base/ prompts (full MCQ text)",
    )
    parser.add_argument(
        "--std_choices_dir",
        required=True,
        help="Path to standard_choices_no_question/",
    )
    parser.add_argument(
        "--aad_choices_dir",
        required=True,
        help="Path to aad_choices_no_question/",
    )
    parser.add_argument(
        "--judge_model",
        default=DEFAULT_JUDGE_MODEL,
        help=f"OpenAI model for semantic matching (default: {DEFAULT_JUDGE_MODEL})",
    )
    parser.add_argument(
        "--judge_prompt_file",
        default=DEFAULT_PROMPT_FILE,
        help="Prompt template for the LLM judge",
    )
    parser.add_argument(
        "--output_suffix",
        help="Suffix for unscored_model_responses/<subfolder>_<suffix>/",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Process only the first N samples per variant (for testing)",
    )
    args = parser.parse_args()

    responses_dir = resolve_responses_dir(args.responses_dir)
    responses_json = find_responses_json(responses_dir)

    with open(responses_json, "r", encoding="utf-8") as f:
        responses = json.load(f)

    print(f"Judge model: {args.judge_model}")
    print(f"Loaded {len(responses)} responses from {responses_json}")
    run_apply(args, responses, responses_dir)


if __name__ == "__main__":
    main()
