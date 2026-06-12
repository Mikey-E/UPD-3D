"""Map question-only model responses onto MCQ choices via cosine similarity.

Stage 2 of the q_no_c pipeline:
  1. Embed the free-form model response and each choice (without letter prefix).
  2. If top-1 similarity >= threshold, output that choice text.
  3. Otherwise, keep the original free-form response.

Calibration (--calibrate) estimates threshold on train by finding the histogram
intersection between std and aad top-1 similarity distributions (Option B).

Requires sentence-transformers (conda env upd-3d).
"""

import argparse
import json
import os
import re

import numpy as np

try:
    from sentence_transformers import SentenceTransformer
except ImportError as exc:
    raise SystemExit(
        "sentence-transformers is required. "
        "Try: /project/3dllms/melgin/conda/envs/upd-3d/bin/python ..."
    ) from exc

CHOICE_LINE_RE = re.compile(r"^([A-D])\.\s+(.*)$")
DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


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


def compute_similarities(model, response, choices):
    if not response.strip():
        return [
            {
                "letter": c["letter"],
                "choice": c["text"],
                "line": c["line"],
                "similarity": 0.0,
            }
            for c in choices
        ]

    texts = [response] + [c["text"] for c in choices]
    embeddings = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
    response_emb = embeddings[0]
    choice_embs = embeddings[1:]
    sims = choice_embs @ response_emb

    return [
        {
            "letter": choice["letter"],
            "choice": choice["text"],
            "line": choice["line"],
            "similarity": float(sim),
        }
        for choice, sim in zip(choices, sims)
    ]


def select_response(original_response, similarities, threshold):
    if not similarities:
        return original_response, None, False

    best = max(similarities, key=lambda x: x["similarity"])
    if best["similarity"] >= threshold:
        return best["line"], best, True
    return original_response, best, False


def find_threshold_intersection(std_sims, aad_sims, num_bins=200):
    std_sims = np.asarray(std_sims, dtype=float)
    aad_sims = np.asarray(aad_sims, dtype=float)

    if std_sims.size == 0 or aad_sims.size == 0:
        raise ValueError("Cannot calibrate threshold without std and aad similarities")

    low = float(min(std_sims.min(), aad_sims.min()))
    high = float(max(std_sims.max(), aad_sims.max()))
    if np.isclose(low, high):
        return low

    bins = np.linspace(low, high, num_bins + 1)
    centers = (bins[:-1] + bins[1:]) / 2
    std_hist, _ = np.histogram(std_sims, bins=bins, density=True)
    aad_hist, _ = np.histogram(aad_sims, bins=bins, density=True)
    diff = std_hist - aad_hist

    crossings = []
    for i in range(len(diff) - 1):
        if diff[i] == 0:
            crossings.append(float(centers[i]))
        elif diff[i] * diff[i + 1] < 0:
            # Linear interpolation inside the bin.
            frac = abs(diff[i]) / (abs(diff[i]) + abs(diff[i + 1]))
            crossing = bins[i + 1] * frac + centers[i] * (1 - frac)
            crossings.append(float(crossing))

    if crossings:
        return float(np.median(crossings))

    return float((np.median(std_sims) + np.median(aad_sims)) / 2)


def summarize_similarities(values):
    arr = np.asarray(values, dtype=float)
    return {
        "count": int(arr.size),
        "mean": float(arr.mean()),
        "median": float(np.median(arr)),
        "min": float(arr.min()),
        "max": float(arr.max()),
    }


def derive_output_filenames(input_json_name):
    base, ext = os.path.splitext(input_json_name)
    if "standard_question_no_choices" in base:
        std_name = base.replace("standard_question_no_choices", "standard") + ext
        aad_name = base.replace("standard_question_no_choices", "aad_base") + ext
    else:
        std_name = f"{base}_standard{ext}"
        aad_name = f"{base}_aad_base{ext}"
    return std_name, aad_name


def derive_output_suffix(threshold, output_suffix):
    if output_suffix:
        return output_suffix
    return f"cosine_{threshold:.3f}"


def collect_top1_similarities(model, responses, choices_dir):
    top1_sims = []
    missing = 0

    for scene_id, item in responses.items():
        choices_path = os.path.join(choices_dir, f"{scene_id}.txt")
        if not os.path.exists(choices_path):
            missing += 1
            continue
        choices = parse_choices_file(choices_path)
        similarities = compute_similarities(model, item["response"], choices)
        top1_sims.append(max(s["similarity"] for s in similarities))

    if missing:
        print(f"Warning: skipped {missing} samples missing choices in {choices_dir}")
    return top1_sims


def build_output_entry(
    prompt,
    original_response,
    similarities,
    threshold,
    selected_response,
    top1_match,
    selected_from_choices,
):
    entry = {
        "prompt": prompt,
        "response": selected_response,
        "all_similarities": similarities,
        "top1_choice": top1_match["choice"] if top1_match else None,
        "threshold_used": threshold,
        "selected_from_choices": selected_from_choices,
    }
    if selected_from_choices:
        entry["original_response"] = original_response
    return entry


def process_variant(
    model,
    responses,
    prompts_dir,
    choices_dir,
    threshold,
    variant_name,
):
    output = {}
    missing_prompt = 0
    missing_choices = 0

    for scene_id, item in responses.items():
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
        similarities = compute_similarities(model, original_response, choices)
        selected_response, top1_match, selected_from_choices = select_response(
            original_response, similarities, threshold
        )
        output[scene_id] = build_output_entry(
            prompt,
            original_response,
            similarities,
            threshold,
            selected_response,
            top1_match,
            selected_from_choices,
        )

    if missing_prompt:
        print(f"Warning: skipped {missing_prompt} samples missing prompts in {prompts_dir}")
    if missing_choices:
        print(f"Warning: skipped {missing_choices} samples missing choices in {choices_dir}")

    print(f"{variant_name}: wrote {len(output)} entries")
    return output


def load_threshold(args):
    if args.threshold is not None:
        return float(args.threshold)
    if not args.threshold_file:
        raise SystemExit("Provide --threshold or --threshold_file (or use --calibrate).")
    with open(args.threshold_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return float(data["threshold"])


def run_calibrate(args, model, responses, responses_dir):
    std_top1 = collect_top1_similarities(model, responses, args.std_choices_dir)
    aad_top1 = collect_top1_similarities(model, responses, args.aad_choices_dir)
    threshold = find_threshold_intersection(std_top1, aad_top1, args.num_bins)

    result = {
        "threshold": threshold,
        "method": "histogram_intersection",
        "model": args.model,
        "std_top1_stats": summarize_similarities(std_top1),
        "aad_top1_stats": summarize_similarities(aad_top1),
    }

    output_path = args.threshold_output
    if not output_path:
        subfolder = os.path.basename(os.path.abspath(responses_dir))
        output_path = os.path.join("thresholds", f"{subfolder}_cosine_threshold.json")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"Calibrated threshold: {threshold:.6f}")
    print(f"Threshold file: {output_path}")
    return threshold


def run_apply(args, model, responses, threshold, responses_dir):
    responses_dir = os.path.abspath(responses_dir)
    subfolder = os.path.basename(responses_dir)
    suffix = derive_output_suffix(threshold, args.output_suffix)
    output_dir = os.path.join("unscored_model_responses", f"{subfolder}_{suffix}")
    os.makedirs(output_dir, exist_ok=True)

    input_json_name = os.path.basename(find_responses_json(responses_dir))
    std_name, aad_name = derive_output_filenames(input_json_name)

    std_output = process_variant(
        model,
        responses,
        args.std_prompts_dir,
        args.std_choices_dir,
        threshold,
        "standard",
    )
    aad_output = process_variant(
        model,
        responses,
        args.aad_prompts_dir,
        args.aad_choices_dir,
        threshold,
        "aad_base",
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
        description="Select MCQ answers from q_no_c responses via cosine similarity."
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
        "--model",
        default=DEFAULT_MODEL,
        help=f"Sentence-transformer model name (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--calibrate",
        action="store_true",
        help="Estimate threshold from std/aad top-1 similarity distributions",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        help="Fixed similarity threshold for selection",
    )
    parser.add_argument(
        "--threshold_file",
        help="JSON file containing a calibrated threshold",
    )
    parser.add_argument(
        "--threshold_output",
        help="Where to write calibrated threshold JSON (calibrate mode)",
    )
    parser.add_argument(
        "--output_suffix",
        help="Suffix for unscored_model_responses/<subfolder>_<suffix>/ (default: cosine_<threshold>)",
    )
    parser.add_argument(
        "--num_bins",
        type=int,
        default=200,
        help="Histogram bins for threshold intersection (calibrate mode)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write unscored_model_responses outputs (default when not calibrating)",
    )
    args = parser.parse_args()

    responses_dir = resolve_responses_dir(args.responses_dir)
    responses_json = find_responses_json(responses_dir)

    with open(responses_json, "r", encoding="utf-8") as f:
        responses = json.load(f)

    print(f"Loading model: {args.model}")
    model = SentenceTransformer(args.model)
    print(f"Loaded {len(responses)} responses from {responses_json}")

    if args.calibrate:
        threshold = run_calibrate(args, model, responses, responses_dir)
        if args.apply or args.threshold is not None or args.threshold_file:
            if args.threshold is None and not args.threshold_file:
                args.threshold = threshold
        else:
            return

    should_apply = args.apply or not args.calibrate
    if should_apply:
        threshold = load_threshold(args)
        run_apply(args, model, responses, threshold, responses_dir)


if __name__ == "__main__":
    main()
