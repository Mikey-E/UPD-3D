#!/bin/bash
# Submit a scoring SLURM job for every JSON file in a directory.
# Usage:  ./multi-slurm_score_model_responses.sh <directory> [--answer-key <answer_key.json>]
# Notes:
#   - For each *.json file directly inside <directory>, this script submits
#     slurm_score_model_responses.sh via sbatch.
#   - If a filename contains the substring "standard" then an answer key MUST
#     be provided (mirrors logic in score_model_responses.py). The key used is:
#         1) The one supplied via --answer-key argument (highest priority), or
#         2) The value of $ANSWER_KEY_DEFAULT env var, or
#         3) answer_keys/3D-FRONT.json if it exists.
#   - Non-JSON files are ignored. Subdirectories are not traversed.
#   - Additional arguments after the file path are not currently supported; if
#     needed you can extend this script.

set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: $0 <directory> [--answer-key <answer_key.json>]" >&2
    exit 1
fi

TARGET_DIR="$1"
shift || true # Save first arg to TARGET_DIR, remove it safely

USER_SUPPLIED_KEY=""
if [ "${1:-}" = "--answer-key" ]; then
    if [ $# -lt 2 ]; then
        echo "Error: --answer-key flag provided but no path given" >&2
        exit 1
    fi
    USER_SUPPLIED_KEY="$2"
    shift 2
fi

if [ ! -d "$TARGET_DIR" ]; then
    echo "Error: Directory not found: $TARGET_DIR" >&2
    exit 1
fi

# Resolve default answer key fallback order.
DEFAULT_KEY=""
if [ -n "$USER_SUPPLIED_KEY" ]; then
    DEFAULT_KEY="$USER_SUPPLIED_KEY"
elif [ -n "${ANSWER_KEY_DEFAULT:-}" ]; then
    DEFAULT_KEY="$ANSWER_KEY_DEFAULT"
elif [ -f "answer_keys/3D-FRONT.json" ]; then
    DEFAULT_KEY="answer_keys/3D-FRONT.json"
fi

if [ -n "$DEFAULT_KEY" ] && [ ! -f "$DEFAULT_KEY" ]; then
    echo "Error: Default answer key path does not exist: $DEFAULT_KEY" >&2
    exit 1
fi

echo "Submitting scoring jobs for JSON files in: $TARGET_DIR" >&2
if [ -n "$DEFAULT_KEY" ]; then
    echo "Default answer key (used when required): $DEFAULT_KEY" >&2
else
    echo "No default answer key resolved yet (will error if a 'standard' file needs one)." >&2
fi

submitted=0
skipped=0

for file in "$TARGET_DIR"/*.json; do
    # If the glob does not match, it stays literal
    if [ ! -e "$file" ]; then
        echo "No JSON files found in $TARGET_DIR" >&2
        break
    fi

    if [ ! -f "$file" ]; then
        continue
    fi

    base="$(basename "$file")"

    # Decide if we need an answer key.
    if [[ "$base" == *standard* ]]; then
        if [ -z "$DEFAULT_KEY" ]; then
            echo "SKIP (needs answer key, none available): $base" >&2
            skipped=$((skipped+1))
            continue
        fi
        echo "Submitting (with answer key): $base" >&2
        sbatch slurm_score_model_responses.sh "$file" --answer_key "$DEFAULT_KEY"
    else
        echo "Submitting: $base" >&2
        sbatch slurm_score_model_responses.sh "$file"
    fi
    submitted=$((submitted+1))
    sleep 0.2 # Tiny sleep to avoid hammering scheduler
done

echo "Done. Submitted: $submitted  Skipped: $skipped" >&2