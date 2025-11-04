# Human Baseline to Unscored Model Response Conversion

## Overview
This document describes the conversion of human baseline data from the collected format to the unscored model response format for scoring.

## Script Location
`human_baseline/convert_human_baseline_to_unscored.py`

## What It Does
The script converts human baseline data from:
- **Input**: `human_baseline/collected_answers/pcl_lists/{dataset}/` 
  - Each file contains 1 scene with 12 responses (one per question type)
- **Output**: `unscored_model_responses/{dataset}_human/`
  - 12 files (one per question type), each containing all scenes

## Conversion Details

### Input Format
Each JSON file in `collected_answers/pcl_lists/` contains:
```json
{
  "identifier_scene": "scene_id@room",
  "dataset": "3D-FRONT_test",
  "annotated_by": "User 4",
  "timestamp": "2025-10-20T08:11:03.167002",
  "file_path": "/path/to/ply/file.ply",
  "responses": [
    {
      "question_number": 1,
      "question_type": "aad_additional_instruction",
      "prompt": "Question text...",
      "response": "answer"
    },
    // ... 11 more responses (12 total)
  ]
}
```

### Output Format
Each JSON file in `unscored_model_responses/{dataset}_human/` contains:
```json
{
  "scene_id@room": {
    "prompt": "Question text...",
    "response": "answer",
    "timestamp": "2025-10-20T08:11:03.167002",
    "annotated_by": "User 4",
    "original_file_path": "/path/to/ply/file.ply",
    "dataset": "3D-FRONT_test"
  },
  // ... more scenes
}
```

### File Naming Convention
Output files follow the same naming pattern as model responses:
```
inf_rslts_human_{dataset}_{question_type}.json
```

Where:
- `human` replaces the model name
- `{dataset}` is the dataset name (e.g., `3D-FRONT_test`, `Crops3D_test`)
- `{question_type}` is one of 12 types (see below)

### Question Types (12 total)
1. `aad_additional_instruction`
2. `aad_additional_option`
3. `aad_base`
4. `iasd_additional_instruction`
5. `iasd_additional_option`
6. `iasd_base`
7. `ivqd_additional_instruction`
8. `ivqd_additional_option`
9. `ivqd_base`
10. `open_ended`
11. `open_ended_additional_instruction`
12. `standard`

## Usage

### Process 3D-FRONT_test dataset
```bash
python3 human_baseline/convert_human_baseline_to_unscored.py \
  --input human_baseline/collected_answers/pcl_lists/3D-FRONT_test \
  --output unscored_model_responses/3D-FRONT_test_human \
  --dataset 3D-FRONT_test
```

### Process Crops3D_test dataset
```bash
python3 human_baseline/convert_human_baseline_to_unscored.py \
  --input human_baseline/collected_answers/pcl_lists/Crops3D_test \
  --output unscored_model_responses/Crops3D_test_human \
  --dataset Crops3D_test
```

## Validation
The script validates that:
- All 12 question types are present in each input file
- No duplicate or extra question types exist
- If validation fails, it throws a clear error showing:
  - Which file has the issue
  - Which scene identifier
  - What question types are missing or unexpected

## Results

### 3D-FRONT_test
- **Input**: 2,993 files (one per scene)
- **Output**: 12 files (one per question type)
- **Location**: `unscored_model_responses/3D-FRONT_test_human/`

### Crops3D_test
- **Input**: 357 files (one per scene)
- **Output**: 12 files (one per question type)
- **Location**: `unscored_model_responses/Crops3D_test_human/`

## Metadata Preservation
The following metadata from the human baseline is preserved:
- `timestamp` - Original annotation timestamp
- `annotated_by` - Which user annotated the sample
- `original_file_path` - Path to the original PLY file
- `dataset` - Dataset name

This allows tracing back to the original human annotations if needed.
