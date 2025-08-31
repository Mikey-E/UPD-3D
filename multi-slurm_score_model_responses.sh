#!/bin/bash
# Submit a scoring SLURM job for every JSON file in a directory.
# Usage:  ./multi-slurm_score_model_responses.sh <directory> --answer_key <answer_key.json>
# Notes:
#   - For each *.json file directly inside <directory>, this script submits
#     slurm_score_model_responses.sh via sbatch.
#   - An answer key must always be provided via --answer_key, but it will only be
#     passed to jobs whose filename ends with "standard.json". Other files run without it.
#   - Non-JSON files are ignored. Subdirectories are not traversed.
#   - Additional arguments after the required ones are not currently supported; if
#     needed you can extend this script.

# Be strict but avoid exiting the parent shell if sourced
set -uo pipefail

# Detect if the script is being sourced
is_sourced() {
    # When sourced, BASH_SOURCE[0] != $0
    [[ "${BASH_SOURCE[0]}" != "$0" ]]
}

# Exit this script safely: return if sourced, exit otherwise
safe_exit() {
    local code=${1:-0}
    if is_sourced; then
        return "$code"
    else
        exit "$code"
    fi
}

die() {
    # Print an error message and exit this script without killing the terminal
    echo "Error: $*" >&2
    safe_exit 1
}

if [ $# -lt 3 ]; then
    echo "Usage: $0 <directory> --answer_key <answer_key.json>" >&2
    safe_exit 1
fi

TARGET_DIR="$1"
shift || true # Save first arg to TARGET_DIR, remove it safely

# Require explicit --answer_key
if [ "${1:-}" != "--answer_key" ] || [ -z "${2:-}" ]; then
    die "--answer_key <answer_key.json> is required"
fi
ANSWER_KEY="$2"
shift 2

# No additional arguments supported
if [ $# -gt 0 ]; then
    die "unexpected extra arguments: $*"
fi

if [ ! -d "$TARGET_DIR" ]; then
    die "Directory not found: $TARGET_DIR"
fi

# Validate provided answer key path exists
if [ ! -f "$ANSWER_KEY" ]; then
    die "Answer key path does not exist: $ANSWER_KEY"
fi

echo "Submitting scoring jobs for JSON files in: $TARGET_DIR" >&2
echo "Answer key provided: $ANSWER_KEY" >&2

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

    # Pass answer key only if filename ends with "standard.json"; otherwise omit
    if [[ "$base" == *standard.json ]]; then
        echo "Submitting: $base (with answer key)" >&2
        sbatch slurm_score_model_responses.sh "$file" --answer_key "$ANSWER_KEY"
    else
        echo "Submitting: $base" >&2
        sbatch slurm_score_model_responses.sh "$file"
    fi
    submitted=$((submitted+1))
    sleep 0.2 # Tiny sleep to avoid hammering scheduler
done

echo "Done. Submitted: $submitted  Skipped: $skipped" >&2