# Experiment Setup Instructions for MiniGPT-3D
Do heavy CPU work on slurm partition `mb`, not login nodes. Inspect large files efficiently.

High-level steps (one or more):
1. Create a custom dataset
2. Custom architectural changes (only if the experiment needs them; often none)
3. Set up (or modify) the repo and launch train → infer → score

## Creating a custom dataset
Reference (do not modify/edit): `/project/3dllms/melgin/datasets/MiniGPT-3D_base`
New folder under `/project/3dllms/melgin/datasets`, named `MiniGPT-3D_ft-comb_<dataset>_<experiment shorthand>` (e.g. shorthand `cot_test1`).

"Laundered" = MiniGPT-3D base training artefacts + the extra point-cloud dataset, combined in those artefacts.

Required minimum layout:
- `anno_data/`
- `modelnet40_data/`
- root symlink `modelnet40_test_8192pts_fps.dat` → `../MiniGPT-3D_base/modelnet40_test_8192pts_fps.dat`
- `objaverse_data/`

### anno_data
- `object_ids_660K.txt`
- `PointLLM_brief_description_660K_filtered.json`
- `PointLLM_brief_description_660K.json`
- `PointLLM_brief_description_val_200_GT.json` (copy unmodified)
- `PointLLM_brief_description_val_3000_GT.json` (copy unmodified)
- `PointLLM_complex_instruction_70K.json` (copy unmodified)
- `val_object_ids_3000.txt` (copy unmodified)

#### object_ids_660K.txt
Copy from base, then append unique laundered **train** ids (not test). Example:

```
00000054c36d44a2a483bdbff31d8edf
...
Wheat@49
Wheat@58
```

`@` = one `/` in the source tree (nested extras only; multi-`@` OK, e.g. `a@b@c` ↔ `a/b/c`). Leave base Objaverse ids as flat hashes — never invent `hash@…`.

#### PointLLM_brief_description_660K_filtered.json, PointLLM_brief_description_660K.json
Copy from base; append train samples per the experiment. Both files get the **same** new appends (base content may still differ between them).

Rules:
- Min fields: `object_id`, `conversations` (extra fields OK). `conversations`: list of `{from: human|gpt, value: ...}`. Wording is per-experiment.
- Set `conversation_type: "single_round"` on appended UPD QA (MCQ / instruction). Stage 1/2 brief loader keeps `["simple_description", "single_round"]`; stage 3/4 `Objaverse_single_round` also reads brief so these rows are not dropped.
- No required `<point>` (loader always uses `object_id`). `<point>` still fine if present.
- Train list only for these JSONs / `object_ids_660K.txt` / laundered symlinks. Test list → inference `--pcl_list_txt_file_path` only.
- Ready-made PointLLM-style samples: append as-is (still train-filtered). Do not drop train texts to unique-ify.
- One-to-many is common: many texts → one cloud. Symlink/unique-id count ≪ JSON sample count is OK.
- Laundered `object_id` form: `"Cabbage@mvs_1005_01"` (`@` as above).

### modelnet40_data
Also symlink `modelnet40_data/modelnet40_test_8192pts_fps.dat` → `../modelnet40_test_8192pts_fps.dat`. Root + this link both required.

### objaverse_data

#### Base Objaverse (~660K) — on `mb`
```bash
mkdir -p /project/3dllms/melgin/datasets/<new_dataset_folder>/objaverse_data
cp -as /project/3dllms/melgin/datasets/MiniGPT-3D_base/objaverse_data/. \
  /project/3dllms/melgin/datasets/<new_dataset_folder>/objaverse_data/
```
Base names are `{id}_8192.npy`. Never add `_8192` to laundered clouds.

#### Laundered extras
Symlink unique **train** clouds only (not test, not whole tree). Source roots: `/project/3dllms/melgin/UPD-3D/utils/dataset_locations.md`. Prefer `mb` if large.

For each unique train `object_id` with extension `{ext}` (usually `.ply`):
- name: `objaverse_data/{object_id}.{ext}` (keep `@`)
- target: `{dataset_root}/{object_id with @→/}.{ext}`

Example: `Wheat@49` → `objaverse_data/Wheat@49.ply` → `/project/3dllms/melgin/datasets/CEA/Crops3D/Wheat/49.ply`

`.ply` / `.npy` both fine; MiniGPT-3D_ft-comb handles either — no conversion.

### Dataset sanity checks
1. New unique `@` ids in `object_ids_660K.txt` == new laundered symlinks (exclude `*_8192.npy`). JSON append count may be larger (~12× etc.) if many texts/cloud; both brief JSONs share the same appends.
2. Spot-check a few laundered symlinks (`readlink` / `test -e` target).

## Custom architectural changes
Only if the experiment requires them; otherwise train stock MiniGPT-3D on the custom dataset.

## Repo setup: `/project/3dllms/melgin/MiniGPT-3D_ft-comb`
Below, `REPO` means `/project/3dllms/melgin/MiniGPT-3D_ft-comb`. In YAML/CLI, write that absolute path (do not literal `$REPO`).

`<experiment folder name>` = new dataset folder name (prefer). Ignore older `combined_data_*` output names. Overwrite config lines in place (comment out prior active values); no needless file copies.

### Eval config
`REPO/eval_configs/mgpt3d_eval-config_ft-comb.yaml`:
- `ckpt`: `REPO/output/<experiment folder name>/stage_3/checkpoint_2.pth`
- `second_ckpt`: `REPO/output/<experiment folder name>/stage_4/checkpoint_0.pth`

### Train configs
In `REPO/train_configs/MiniGPT_3D/mgpt3d_train-config_stage{1,2,3,4}_combined.yaml`:
- stage1: `output_dir` → `REPO/output/<experiment folder name>/stage_1`
- stage2: `second_ckpt` → `REPO/output/<experiment folder name>/stage_1/checkpoint_0.pth`; `output_dir` → `REPO/output/<experiment folder name>/stage_2`
- stage3: `ckpt` → `REPO/output/<experiment folder name>/stage_2/checkpoint_0.pth`; `output_dir` → `REPO/output/<experiment folder name>/stage_3`
- stage4: `ckpt` → `REPO/output/<experiment folder name>/stage_3/checkpoint_2.pth`; `output_dir` → `REPO/output/<experiment folder name>/stage_4`

### Inference CLI (pass to `multi-slurm_mgpt3d_inf.sh`; do not edit the script for dataset choice)
Matched triple only (exhaustive until new datasets exist):

| `--upd_version_name` | `--unzipped_point_cloud_path` | `--pcl_list_txt_file_path` |
|---|---|---|
| `Crops3D_gpt-5-nano` | `/project/3dllms/melgin/datasets/CEA/Crops3D` | `/project/3dllms/melgin/UPD-3D/pcl_lists/Crops3D_test.txt` |
| `3D-FRONT` | `/project/3dllms/melgin/datasets/3d-grand_unzipped/3D-FRONT` | `/project/3dllms/melgin/UPD-3D/pcl_lists/3D-FRONT_test.txt` |
| `GIW529_gpt-5-nano` | `/project/3dllms/melgin/datasets/GIW/giw529subcat` | `/project/3dllms/melgin/UPD-3D/pcl_lists/GIW529_test.txt` |

### `data` symlink
1. `REPO/data_<dataset_folder_name>` → absolute path of the new dataset (`<dataset_folder_name>` exact folder name; ignore older shortened `data_*` suffixes).
2. Repoint `REPO/data` → that link. Keep other `data_*`; only re-point `data`.

### Repo sanity checks
- `readlink -f` on `REPO/data` → new dataset
- `REPO/inf_rslts` empty (script refuses otherwise)

### Launch: train → infer → score
From `REPO` (or absolute script paths + that cwd). Ignore stage `4-1`, `4-2`, … scripts.

```bash
sbatch /project/3dllms/melgin/MiniGPT-3D_ft-comb/slurm_mgpt3d_train_stage1_combined.sh            # note ID → J1
sbatch --dependency=afterok:J1 /project/3dllms/melgin/MiniGPT-3D_ft-comb/slurm_mgpt3d_train_stage2_combined.sh  # → J2
sbatch --dependency=afterok:J2 /project/3dllms/melgin/MiniGPT-3D_ft-comb/slurm_mgpt3d_train_stage3_combined.sh  # → J3
sbatch --dependency=afterok:J3 /project/3dllms/melgin/MiniGPT-3D_ft-comb/slurm_mgpt3d_train_stage4_combined.sh  # → J4
```

Then (depends on J4). Unscored dir must be **new/unique**:
`<upd_version_name>_<partition (usually test)>_mgpt3d_<paradigm>[_<experiment shorthand>]`  
e.g. `Crops3D_gpt-5-nano_test_mgpt3d_ft-comb` or `..._ft-comb_Crops3D_cot_test1`.  
`--answer_key` = `/project/3dllms/melgin/UPD-3D/answer_keys/<upd_version_name>.json`.

```bash
sbatch --dependency=afterok:J4 \
  --account=3dllms --partition=mb --job-name=mgpt3d_inf_submit \
  --time=00:10:00 --mem=1G --chdir=/project/3dllms/melgin/MiniGPT-3D_ft-comb \
  --output=/project/3dllms/melgin/MiniGPT-3D_ft-comb/slurm_logs/mgpt3d_inf_submit_%j.out \
  --wrap="bash /project/3dllms/melgin/MiniGPT-3D_ft-comb/multi-slurm_mgpt3d_inf.sh \
    --upd_version_name <upd_version_name> \
    --unzipped_point_cloud_path <unzipped_point_cloud_path> \
    --pcl_list_txt_file_path <pcl_list_txt_file_path> \
    --unscored_dir /project/3dllms/melgin/UPD-3D/unscored_model_responses/<experiment name> \
    --answer_key /project/3dllms/melgin/UPD-3D/answer_keys/<answer key> \
    --score_partition l40s"
```

`multi-slurm_mgpt3d_inf.sh` submits all inf jobs, then afterok-chains move (`inf_rslts/*` → `--unscored_dir`) and score-submit. Score-submit ≠ scoring done; results → `/project/3dllms/melgin/UPD-3D/scored_model_responses/<experiment name>_oss120`. No manual inf job-ID collection.
