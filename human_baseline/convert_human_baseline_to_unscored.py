#!/usr/bin/env python3
"""
Convert human baseline collected answers to unscored model response format.

This script takes human baseline data from collected_answers/pcl_lists/ and
converts it to the format used in unscored_model_responses/ for scoring.
"""

import json
import argparse
from pathlib import Path
from collections import defaultdict
from typing import Dict, List


# Expected question types - all 12 must be present in each file
EXPECTED_QUESTION_TYPES = [
    'aad_additional_instruction',
    'aad_additional_option',
    'aad_base',
    'iasd_additional_instruction',
    'iasd_additional_option',
    'iasd_base',
    'ivqd_additional_instruction',
    'ivqd_additional_option',
    'ivqd_base',
    'open_ended',
    'open_ended_additional_instruction',
    'standard'
]


def validate_responses(responses: List[Dict], identifier_scene: str, file_path: str) -> None:
    """
    Validate that all 12 expected question types are present.
    
    Args:
        responses: List of response dictionaries
        identifier_scene: Scene identifier for error reporting
        file_path: Original file path for error reporting
    
    Raises:
        ValueError: If not all question types are present
    """
    found_types = {r['question_type'] for r in responses}
    missing_types = set(EXPECTED_QUESTION_TYPES) - found_types
    
    if missing_types:
        raise ValueError(
            f"Missing question types in file: {file_path}\n"
            f"  Scene: {identifier_scene}\n"
            f"  Missing types: {sorted(missing_types)}\n"
            f"  Found {len(found_types)} of {len(EXPECTED_QUESTION_TYPES)} expected types"
        )
    
    if len(responses) != len(EXPECTED_QUESTION_TYPES):
        extra_types = found_types - set(EXPECTED_QUESTION_TYPES)
        raise ValueError(
            f"Unexpected question types in file: {file_path}\n"
            f"  Scene: {identifier_scene}\n"
            f"  Extra types: {sorted(extra_types)}\n"
            f"  Found {len(responses)} responses, expected {len(EXPECTED_QUESTION_TYPES)}"
        )


def process_human_baseline_files(input_dir: Path, output_dir: Path, dataset_name: str) -> None:
    """
    Process all human baseline files and organize them by question type.
    
    Args:
        input_dir: Directory containing human baseline JSON files
        output_dir: Directory to write converted files
        dataset_name: Name of the dataset (e.g., '3D-FRONT_test', 'Crops3D_test')
    """
    # Dictionary to hold responses organized by question type
    # question_type -> {identifier_scene: {prompt, response, timestamp, metadata}}
    organized_data = defaultdict(dict)
    
    # Get all JSON files
    json_files = sorted(input_dir.glob('*.json'))
    
    if not json_files:
        raise ValueError(f"No JSON files found in {input_dir}")
    
    print(f"Processing {len(json_files)} files from {input_dir}")
    
    # Process each file
    for file_idx, json_file in enumerate(json_files, 1):
        if file_idx % 100 == 0:
            print(f"  Processed {file_idx}/{len(json_files)} files...")
        
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            identifier_scene = data['identifier_scene']
            responses = data['responses']
            
            # Validate that all 12 question types are present
            validate_responses(responses, identifier_scene, str(json_file))
            
            # Organize responses by question type
            for response_data in responses:
                question_type = response_data['question_type']
                
                # Create entry for this scene in the organized data
                organized_data[question_type][identifier_scene] = {
                    'prompt': response_data['prompt'],
                    'response': response_data['response'],
                    'timestamp': data['timestamp'],
                    # Preserve additional metadata
                    'annotated_by': data.get('annotated_by', 'Unknown'),
                    'original_file_path': data.get('file_path', ''),
                    'dataset': data.get('dataset', dataset_name)
                }
        
        except Exception as e:
            print(f"\nError processing file: {json_file}")
            raise e
    
    print(f"  Processed all {len(json_files)} files successfully!")
    
    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Write one file per question type
    print(f"\nWriting output files to {output_dir}")
    for question_type in EXPECTED_QUESTION_TYPES:
        if question_type not in organized_data:
            print(f"  Warning: No data found for question type '{question_type}'")
            continue
        
        output_file = output_dir / f"inf_rslts_human_{dataset_name}_{question_type}.json"
        
        with open(output_file, 'w') as f:
            json.dump(organized_data[question_type], f, indent=2)
        
        print(f"  Wrote {len(organized_data[question_type])} responses to {output_file.name}")
    
    print(f"\nConversion complete! Output written to: {output_dir}")


def main():
    parser = argparse.ArgumentParser(
        description='Convert human baseline data to unscored model response format',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process 3D-FRONT_test dataset
  python convert_human_baseline_to_unscored.py \\
    --input human_baseline/collected_answers/pcl_lists/3D-FRONT_test \\
    --output ../unscored_model_responses/3D-FRONT_test_human \\
    --dataset 3D-FRONT_test
  
  # Process Crops3D_test dataset
  python convert_human_baseline_to_unscored.py \\
    --input human_baseline/collected_answers/pcl_lists/Crops3D_test \\
    --output ../unscored_model_responses/Crops3D_test_human \\
    --dataset Crops3D_test
        """
    )
    
    parser.add_argument(
        '--input',
        type=Path,
        required=True,
        help='Input directory containing human baseline JSON files'
    )
    
    parser.add_argument(
        '--output',
        type=Path,
        required=True,
        help='Output directory for converted files (will be created if it doesn\'t exist)'
    )
    
    parser.add_argument(
        '--dataset',
        type=str,
        required=True,
        help='Dataset name (e.g., "3D-FRONT_test", "Crops3D_test")'
    )
    
    args = parser.parse_args()
    
    # Validate input directory exists
    if not args.input.exists():
        parser.error(f"Input directory does not exist: {args.input}")
    
    if not args.input.is_dir():
        parser.error(f"Input path is not a directory: {args.input}")
    
    # Process the files
    try:
        process_human_baseline_files(args.input, args.output, args.dataset)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())
