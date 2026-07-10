#!/bin/bash
# Submit a scoring SLURM job for every JSON file in a directory.
# Usage:  ./multi-slurm_score_model_responses.sh <directory> --answer_key <answer_key.json> --openai_api_key_script <export_openai_api_key.sh> [--sleep <seconds>]
# Notes:
#   - For each *.json file directly inside <directory>, this script submits
#     slurm_score_model_responses.sh via sbatch.
#   - An answer key must always be provided via --answer_key. It is passed to jobs
#     whose filename ends with "standard.json" or contains "_aad_", "_iasd_", or
#     "_oe_solvable". Other files run without it.
#   - Non-JSON files are ignored. Subdirectories are not traversed.
#   - Flags may appear in any order after <directory>.
#   - Prefer: ./multi-slurm_score_model_responses.sh ...  (not: . multi-slurm_...)

set -uo pipefail

is_sourced() {
    [[ "${BASH_SOURCE[0]}" != "$0" ]]
}

die() {
    echo "Error: $*" >&2
    return 1
}

usage() {
    echo "Usage: $0 <directory> --answer_key <answer_key.json> --openai_api_key_script <export_openai_api_key.sh> [--sleep <seconds>]" >&2
    echo "Pass --openai_api_key_script with a shell script that exports OPENAI_API_KEY." >&2
}

main() {
    if [ $# -lt 1 ]; then
        usage
        return 1
    fi

    local TARGET_DIR=""
    local ANSWER_KEY=""
    local OPENAI_API_KEY_SCRIPT=""
    local SLEEP_INCREMENT=600

    while [ $# -gt 0 ]; do
        case "$1" in
            --answer_key)
                [ -n "${2:-}" ] || { die "--answer_key requires a path"; return 1; }
                ANSWER_KEY="$2"
                shift 2
                ;;
            --openai_api_key_script)
                [ -n "${2:-}" ] || { die "--openai_api_key_script requires a path"; return 1; }
                OPENAI_API_KEY_SCRIPT="$2"
                shift 2
                ;;
            --sleep)
                [ -n "${2:-}" ] || { die "--sleep requires a value in seconds"; return 1; }
                SLEEP_INCREMENT="$2"
                shift 2
                if ! [[ "$SLEEP_INCREMENT" =~ ^[0-9]+$ ]]; then
                    die "--sleep value must be a positive integer: $SLEEP_INCREMENT"
                    return 1
                fi
                ;;
            -*)
                die "unknown option: $1"
                return 1
                ;;
            *)
                if [ -n "$TARGET_DIR" ]; then
                    die "unexpected extra argument: $1"
                    return 1
                fi
                TARGET_DIR="$1"
                shift
                ;;
        esac
    done

    [ -n "$TARGET_DIR" ] || { usage; die "<directory> is required"; return 1; }
    [ -n "$ANSWER_KEY" ] || { die "--answer_key <answer_key.json> is required"; return 1; }
    if [ -z "$OPENAI_API_KEY_SCRIPT" ]; then
        echo "Error: --openai_api_key_script <path> is required." >&2
        echo "Pass a shell script that exports OPENAI_API_KEY (e.g. ./export_openai_api_key.sh)." >&2
        return 1
    fi

    if [ ! -d "$TARGET_DIR" ]; then
        die "Directory not found: $TARGET_DIR"
        return 1
    fi

    if [ ! -f "$ANSWER_KEY" ]; then
        die "Answer key path does not exist: $ANSWER_KEY"
        return 1
    fi

    if [ ! -f "$OPENAI_API_KEY_SCRIPT" ]; then
        die "OpenAI API key script does not exist: $OPENAI_API_KEY_SCRIPT"
        return 1
    fi

    echo "Submitting scoring jobs for JSON files in: $TARGET_DIR" >&2
    echo "Answer key provided: $ANSWER_KEY" >&2
    echo "OpenAI API key script: $OPENAI_API_KEY_SCRIPT" >&2
    if [ "$SLEEP_INCREMENT" -gt 0 ]; then
        echo "Sleep increment: $SLEEP_INCREMENT seconds (cumulative per job)" >&2
    fi

    local submitted=0
    local skipped=0
    local cumulative_sleep=0
    local file base

    for file in "$TARGET_DIR"/*.json; do
        if [ ! -e "$file" ]; then
            echo "No JSON files found in $TARGET_DIR" >&2
            break
        fi

        if [ ! -f "$file" ]; then
            continue
        fi

        base="$(basename "$file")"

        if [[ "$base" == *standard.json || "$base" == *_aad_* || "$base" == *_iasd_* || "$base" == *_oe_solvable* ]]; then
            if [ "$cumulative_sleep" -gt 0 ]; then
                echo "Submitting: $base (with answer key, sleep=${cumulative_sleep}s)" >&2
            else
                echo "Submitting: $base (with answer key)" >&2
            fi
            sbatch slurm_score_model_responses.sh --openai_api_key_script "$OPENAI_API_KEY_SCRIPT" --sleep "$cumulative_sleep" "$file" --answer_key "$ANSWER_KEY"
        else
            if [ "$cumulative_sleep" -gt 0 ]; then
                echo "Submitting: $base (sleep=${cumulative_sleep}s)" >&2
            else
                echo "Submitting: $base" >&2
            fi
            sbatch slurm_score_model_responses.sh --openai_api_key_script "$OPENAI_API_KEY_SCRIPT" --sleep "$cumulative_sleep" "$file"
        fi
        submitted=$((submitted+1))
        cumulative_sleep=$((cumulative_sleep + SLEEP_INCREMENT))
        sleep 0.2
    done

    echo "Done. Submitted: $submitted  Skipped: $skipped" >&2
}

if is_sourced; then
    main "$@" || return $?
else
    main "$@" || exit $?
fi
