#!/bin/bash
# Submit a scoring SLURM job for every JSON file in a directory.
# Usage:  ./multi-slurm_score_model_responses.sh <directory> --answer_key <answer_key.json>
# Notes:
#   - For each *.json file directly inside <directory>, this script submits
#     slurm_score_model_responses.sh via sbatch.
#   - An answer key must always be provided via --answer_key. It is passed to jobs
#     whose filename ends with "standard.json" or contains "_aad_", "_iasd_", or
#     "_oe_solvable". Other files run without it.
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
    echo "Usage: $0 <directory> --answer_key <answer_key.json> [--sleep <seconds>]" >&2
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

# Optional --sleep parameter (default: 600 seconds = 10 minutes)
SLEEP_INCREMENT=600
if [ "${1:-}" = "--sleep" ]; then
    if [ -z "${2:-}" ]; then
        die "--sleep requires a value in seconds"
    fi
    SLEEP_INCREMENT="$2"
    shift 2
    # Validate it's a number
    if ! [[ "$SLEEP_INCREMENT" =~ ^[0-9]+$ ]]; then
        die "--sleep value must be a positive integer: $SLEEP_INCREMENT"
    fi
fi

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
if [ "$SLEEP_INCREMENT" -gt 0 ]; then
    echo "Sleep increment: $SLEEP_INCREMENT seconds (cumulative per job)" >&2
fi

submitted=0
skipped=0
cumulative_sleep=0

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

    # Pass answer key for standard, AAD, IASD, and oe_solvable subsets (including variants)
    if [[ "$base" == *standard.json || "$base" == *_aad_* || "$base" == *_iasd_* || "$base" == *_oe_solvable* ]]; then
        if [ "$cumulative_sleep" -gt 0 ]; then
            echo "Submitting: $base (with answer key, sleep=${cumulative_sleep}s)" >&2
        else
            echo "Submitting: $base (with answer key)" >&2
        fi
        sbatch --export=SLEEP_SECONDS=$cumulative_sleep slurm_score_model_responses.sh "$file" --answer_key "$ANSWER_KEY"
    else
        if [ "$cumulative_sleep" -gt 0 ]; then
            echo "Submitting: $base (sleep=${cumulative_sleep}s)" >&2
        else
            echo "Submitting: $base" >&2
        fi
        sbatch --export=SLEEP_SECONDS=$cumulative_sleep slurm_score_model_responses.sh "$file"
    fi
    submitted=$((submitted+1))
    cumulative_sleep=$((cumulative_sleep + SLEEP_INCREMENT))
    sleep 0.2 # Tiny sleep to avoid hammering scheduler
done

echo "Done. Submitted: $submitted  Skipped: $skipped" >&2