# GIW529 Test Set Support in Human Baseline Viewer

## Summary
Added support for the GIW529_test dataset to the human baseline viewer, enabling human annotation of the 150 test samples.

## Changes Made

### 1. Command Line Arguments
- Added `--giw529-path` argument (default: `/project/3dllms/melgin/datasets/GIW/giw529subcat`)

### 2. Dataset Support
- Added "GIW529_test" as a third option in the dataset selector dropdown
- Maps to `upd_text/GIW529_gpt-5-nano/` for question loading

### 3. Path Structure
GIW529 uses a flat structure:
- **Format**: `category@identifier` (e.g., `Lemons@04_18_2024_W_F_Lemons1_F_1`)
- **Path**: `giw529subcat/category/identifier.ply`
- **Example**: `giw529subcat/Lemons/04_18_2024_W_F_Lemons1_F_1.ply`

### 4. Modified Functions
Updated the following functions to handle GIW529:
- `load_questions()` - maps GIW529_test to GIW529_gpt-5-nano upd_text folder
- `get_next_point_cloud()` - constructs correct PLY file paths
- `extract_identifier_scene()` - parses category@identifier format
- `on_dataset_change()` - passes giw529_path parameter

### 5. Directory Structure
```
human_baseline/
└── collected_answers/
    └── pcl_lists/
        ├── 3D-FRONT_test/
        ├── Crops3D_test/
        └── GIW529_test/         # Created for GIW529 annotations
```

## Test Set Details
- **Total samples**: 150 scenes
- **Format**: Category@identifier naming convention
- **Point clouds**: Located at `/project/3dllms/melgin/datasets/GIW/giw529subcat/`
- **Questions**: Located at `upd_text/GIW529_gpt-5-nano/`
- **PCL list**: `pcl_lists/GIW529_test.txt`

## Usage
```bash
cd /project/3dllms/melgin/UPD-3D/human_baseline
python human_baseline_viewer.py --giw529-path /path/to/giw529subcat
```

Or submit via SLURM:
```bash
sbatch slurm_human_baseline_viewer.sh
```

## Verification
All changes have been validated:
- ✅ Python syntax check passed
- ✅ GIW529_test PCL list exists (150 entries)
- ✅ Point cloud files exist at expected paths
- ✅ UPD text files exist for all 13 question types
- ✅ Directory structure created for collected answers

## Example Entry
**PCL List Entry**: `Lemons@04_18_2024_W_F_Lemons1_F_1`
- **Point Cloud**: `/project/3dllms/melgin/datasets/GIW/giw529subcat/Lemons/04_18_2024_W_F_Lemons1_F_1.ply`
- **Question Files**: `upd_text/GIW529_gpt-5-nano/{question_type}/Lemons@04_18_2024_W_F_Lemons1_F_1.txt`
- **Output**: `human_baseline/collected_answers/pcl_lists/GIW529_test/Lemons@04_18_2024_W_F_Lemons1_F_1.json`
