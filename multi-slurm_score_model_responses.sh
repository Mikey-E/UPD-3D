#!/bin/bash
# Submit a scoring SLURM job for every JSON file in a directory.
# Usage:  ./multi-slurm_score_model_responses.sh <directory> --answer-key <answer_key.json>
# Notes:
#   - For each *.json file directly inside <directory>, this script submits
#     slurm_score_model_responses.sh via sbatch.
#   - An answer key must always be provided via --answer-key and will be passed
#     to every job (including non-"standard" files).
#   - Non-JSON files are ignored. Subdirectories are not traversed.
#   - Additional arguments after the required ones are not currently supported; if
#     needed you can extend this script.

set -euo pipefail

if [ $# -lt 3 ]; then
    echo "Usage: $0 <directory> --answer-key <answer_key.json>" >&2
    exit 1
fi

TARGET_DIR="$1"
shift || true # Save first arg to TARGET_DIR, remove it safely

# Require explicit --answer-key
if [ "${1:-}" != "--answer-key" ] || [ -z "${2:-}" ]; then
    echo "Error: --answer-key <answer_key.json> is required" >&2
    exit 1
fi
ANSWER_KEY="$2"
shift 2

# No additional arguments supported
if [ $# -gt 0 ]; then
    echo "Error: unexpected extra arguments: $*" >&2
    exit 1
fi

if [ ! -d "$TARGET_DIR" ]; then
    echo "Error: Directory not found: $TARGET_DIR" >&2
    exit 1
fi

# Validate provided answer key path exists
if [ ! -f "$ANSWER_KEY" ]; then
    echo "Error: Answer key path does not exist: $ANSWER_KEY" >&2
    exit 1
fi

echo "Submitting scoring jobs for JSON files in: $TARGET_DIR" >&2
echo "Using answer key: $ANSWER_KEY" >&2

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

    # Always submit with the provided answer key
    echo "Submitting: $base (with answer key)" >&2
    sbatch slurm_score_model_responses.sh "$file" --answer_key "$ANSWER_KEY"
    submitted=$((submitted+1))
    sleep 0.2 # Tiny sleep to avoid hammering scheduler
done

echo "Done. Submitted: $submitted  Skipped: $skipped" >&2