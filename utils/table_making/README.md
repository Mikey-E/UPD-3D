# Table Making Utilities

This folder contains utilities to generate LaTeX tables from scored model responses.

## Files

- `generate_latex_table.sh`: Main script that iterates through all folders in `scored_model_responses/` and generates a LaTeX table

## Usage

### Generate Standard-UPD Accuracy Table (Default)

From the project root directory, run:

```bash
./utils/table_making/generate_latex_table.sh --3D-FRONT
./utils/table_making/generate_latex_table.sh --Crops3D
./utils/table_making/generate_latex_table.sh --GIW529
```

**A dataset filter flag is required**. Choose one of:
- `--3D-FRONT` - Only process folders starting with `3D-FRONT`
- `--Crops3D` - Only process folders starting with `Crops3D_gpt-5-nano`
- `--GIW529` - Only process folders starting with `GIW529_gpt-5-nano`

This will output a raw LaTeX table showing the percentage of test samples that were correct for each model across all 12 UPD categories.

By default, this calculates **Standard-UPD accuracy**: the percentage of samples where the model got either the standard version OR the UPD version correct.

### Generate Dual Accuracy Table

To calculate **Dual accuracy** (where the model must get BOTH the standard AND UPD version correct), add the `--dual` flag:

```bash
./utils/table_making/generate_latex_table.sh --3D-FRONT --dual
./utils/table_making/generate_latex_table.sh --Crops3D --dual
./utils/table_making/generate_latex_table.sh --GIW529 --dual
```

Note: In dual mode, the "Standard", "Open Ended", and "Open Ended Additional Instruction" categories will show "N/A" since dual accuracy doesn't apply to them.

## Output

The script outputs a complete LaTeX table that can be copied directly into a paper. The table includes:

- **Rows**: Model names (extracted from folder names in `scored_model_responses/`)
- **Columns**: 12 UPD categories:
  - AAD-AI (AAD Additional Instruction)
  - AAD-AO (AAD Additional Option)
  - AAD (AAD Base)
  - IASD-AI (IASD Additional Instruction)
  - IASD-AO (IASD Additional Option)
  - IASD (IASD Base)
  - IVQD-AI (IVQD Additional Instruction)
  - IVQD-AO (IVQD Additional Option)
  - IVQD (IVQD Base)
  - OE-AI (Open Ended Additional Instruction)
  - OE (Open Ended)
  - Std (Standard)

- **Cells**: Percentage correct (e.g., "85.3\%")

## Related Scripts

The main analysis logic is in `analyze_scored_responses_tables.py` at the project root, which can also be run standalone on individual model folders:

```bash
python analyze_scored_responses_tables.py scored_model_responses/3D-FRONT_test_gplm_base_gpt-4.1-mini
python analyze_scored_responses_tables.py scored_model_responses/3D-FRONT_test_gplm_base_gpt-4.1-mini --dual
```

## How it Works

The script:
1. Iterates through all folders in `scored_model_responses/`
2. For each folder, runs `analyze_scored_responses_tables.py` to extract accuracy percentages
3. Parses the JSON files in each folder (ending in `_scored.json`)
4. Computes percentages based on the scoring logic from `analyze_scored_responses_bars.py`
5. Formats the results into a LaTeX table

The scoring logic mirrors that used in `analyze_scored_responses_bars.py`:
- **Standard-UPD accuracy**: Counts samples where `score == 'T'` in the UPD variant files
- **Dual accuracy**: Counts samples where both the standard baseline AND the UPD variant have `score == 'T'`
