# Experiment Setup Instructions for GreenPLM
Do heavy CPU work on slurm partition `mb`, not login nodes. Inspect large files efficiently.
Conda env: `greenplm`. Train/infer on `mb-a30` or `mb-l40s` (**not H100** — `sm_90` / CUDA build failures).
Never modify anything under `/project/3dllms/melgin/datasets/` in place — always create a **new** folder there for the experiment. Also never modify `/project/3dllms/melgin/GreenPLM_base`.
**Symlink first:** wherever a file/dir can be reused unchanged, prefer a symlink (`ln -s` / `cp -as`) over copying. Only materialize a real file when you must modify it (e.g. train JSONs that get UPD appends).

High-level steps (one or more):
1. Create a custom dataset
2. Custom / Melgin patches (only if missing from the ft-comb repo; usually already present)
3. Set up the repo and launch train → infer → score

Reference copies of Melgin-added scripts live in `/project/3dllms/melgin/UPD-3D/utils/greenplm/`. Live working tree: `/project/3dllms/melgin/GreenPLM_ft-comb`.

## Creating a custom dataset
Reference (do not modify): `/project/3dllms/melgin/datasets/GreenPLM_base`

New folder under `/project/3dllms/melgin/datasets`, named `GreenPLM_ft-comb_<dataset>_<experiment shorthand>` (omit shorthand if redundant, e.g. `GreenPLM_ft-comb_GIW529_gpt-5-nano`).

"Laundered" = GreenPLM base training artefacts + the extra point-cloud dataset, combined in those artefacts.

Required layout (exactly what `GreenPLM_ft-comb` / modern `GreenPLM_ft-comb_*` contain; base may have the same skeleton without laundered `.ply` / UPD appends):

```
GreenPLM_ft-comb_<...>
├── Objaverse/
│   ├── PointLLM_complex_50k_brief_40k_all_90k.json      # stage3 train — real file (MODIFY)
│   ├── PointLLM_brief_description_val_200_GT.json       # val — symlink to base (unmodified)
│   └── 8192_npy/                                        # cp -as base npy + laundered *.ply symlinks
├── T3D/
│   ├── stage_1/brief_1M_caption.json                    # stage1 — real file (MODIFY)
│   └── stage_2/
│       ├── stage_2_data_210k.json                       # stage2 (used by 2.sh) — real file (MODIFY)
│       └── stage_2_data_5M.json                         # also real file (MODIFY; 2.sh uses 210k)
└── modelnet40_data/
    └── modelnet40_test_8192pts_fps.dat                  # symlink to base
```

Compared to base: val unchanged (symlink); the four train JSONs grow by the same number of new samples; `8192_npy` gains `.ply` symlinks (base has `.npy` only).

### Build steps

1. **Skeleton from base** (symlink anything unchanged)
   - Val JSON: symlink to base’s `PointLLM_brief_description_val_200_GT.json`.
   - `modelnet40_data/modelnet40_test_8192pts_fps.dat`: symlink to base’s (or MiniGPT’s shared dat if that is what base already uses).
   - Train JSONs (must become writable): copy from base into the new folder, then append in step 3 — do **not** symlink these four, or you would mutate base.
   - Base Objaverse clouds (`mb`) — symlink farm, not a content copy:
     ```bash
     mkdir -p /project/3dllms/melgin/datasets/<new_dataset_folder>/Objaverse/8192_npy
     cp -as /project/3dllms/melgin/datasets/GreenPLM_base/Objaverse/8192_npy/. \
       /project/3dllms/melgin/datasets/<new_dataset_folder>/Objaverse/8192_npy/
     ```
   - Base names are `{id}_8192.npy`. Never add `_8192` to laundered clouds.

2. **Launder UPD train point clouds** into `Objaverse/8192_npy/` as `{object_id}.ply` **symlinks** (never copy the clouds).
   - Unique **train** ids only (test list → inference `--pcl_list_txt_file_path` only). Prefer train-only even if some past runs also linked test.
   - `@` = one `/` in the source tree (`Wheat@49` ↔ `Wheat/49`). Multi-`@` OK. Never invent `hash@…` for flat Objaverse hashes.
   - Source roots: `/project/3dllms/melgin/UPD-3D/utils/dataset_locations.md`. Prefer `/project/...` targets when available (older links may use `/gscratch/...`).
   - Per unique train `object_id` (usually `.ply`):
     - name: `Objaverse/8192_npy/{object_id}.ply` (keep `@`)
     - target: `{dataset_root}/{object_id with @→/}.ply`
   - Path nesting:
     - Crops3D / GIW: `{id}/{scene}.ply` → `{id}@{scene}.ply`
     - 3D-FRONT: `{uuid}/{Room}/{Room}.ply` → `{uuid}@{Room}.ply`

3. **Append UPD/CoT train samples**

   S1/S2 (`brief_1M_caption.json`, `stage_2_data_210k.json`, `stage_2_data_5M.json`) are **caption + `text_encoder`**. Rows need a `caption` field; CoT/`conversations`-only QA **must not** go here (S1 crashes with `UnboundLocalError` on `image`; S1 `model_max_length` is 150). Leave those three as **base copies** unless the extras are true captions.

   S3 (`Objaverse/PointLLM_complex_50k_brief_40k_all_90k.json`) is **`pc_encoder`**. Append CoT/UPD QA at end. Prepend `<point>\n` on human turns that lack `<point>`/`<image>` so PC tokens fuse.

   Do **not** touch val JSON.

   Rules:
   - **Required field:** `object_id` (loader looks up `./dataset/Objaverse/8192_npy` via this). Extra fields (`id`, `point`, `caption`, `conversation_type`, …) OK.
   - `conversations`: list of `{from: human|gpt, value: ...}`. Wording is per-experiment.
   - Train list only. Append ready-made samples as-is (still train-filtered). Do not drop texts to unique-ify.
   - One-to-many common: many texts → one cloud. Unique `.ply` count ≪ JSON append count is OK.

### Dataset sanity checks
1. Unique `@` ids among new **S3** JSON samples == new `8192_npy/*.ply` symlinks (JSON count may be larger if many texts/cloud). S1/S2 stay at base size when extras are CoT QA.
2. Val JSON resolves to base (symlink OK) and is unmodified.
3. Spot-check laundered / `cp -as` links (`readlink` / `test -e`), especially 3D-FRONT triple-path targets. Confirm base `*_8192.npy` entries are symlinks, not duplicated files.

## Custom / Melgin patches
`/project/3dllms/melgin/GreenPLM_ft-comb` already has these. If bootstrapping a fresh clone, view helpers from `UPD-3D/utils/greenplm/` into `REPO`; these are often files to edit. Verify `train.py` ply support. Do **not** edit `GreenPLM_base`.

| File | Role |
|------|------|
| `llava/train/train.py` | Open3D `read_pc_2tensor`: try `{id}_8192.npy`, else `{id}.ply` → 8192×6 → `pc_norm`. Needs `open3d` in env. |
| `release/paper/scripts/train/{1,2,3}.sh` | Require `EXP_NAME`; write/read `checkpoints/stage_N_${EXP_NAME}` |
| `gplm_inf_upd.py` | UPD inference CLI |
| `gplm_inf_upd_ft-comb.sh` | ft-comb weight paths + UPD args (edit per experiment) |
| `slurm_gplm_inf_upd.sh` | must `bash gplm_inf_upd_ft-comb.sh "$1"` for ft-comb |
| `multi-slurm_gplm_inf.sh` | submits one job per UPD prompt subfolder |
| `slurm_gplm_train_stage{1,2,3}.sh` | train wrappers (`WANDB_MODE=disabled`, `mb-a30`, 64G); take `<experiment_name>` arg → `EXP_NAME` |

Only add further architectural changes if the experiment explicitly needs them.

## Repo setup: `/project/3dllms/melgin/GreenPLM_ft-comb`
Below, `REPO` means that path. In shells/CLI write absolute paths (do not literal `$REPO`).
Logs: `REPO/slurm_logs` → `/project/3dllms/melgin/slurm_logs/GreenPLM_ft-comb`.

Pick a unique `<experiment_name>` per run (filesystem-safe; e.g. `GIW529_gpt-5-nano_GIW_cot_v2`). This is **not** the same as `--upd_version_name` — many experiments can share one UPD version. Checkpoints use `stage_N_<experiment_name>`.

Train configs are shell scripts (not YAML): `REPO/release/paper/scripts/train/{1,2,3}.sh`  
They hardcode `./dataset/...` and write/read `./checkpoints/stage_{1,2,3}_${EXP_NAME}` (`EXP_NAME` required).
**Do not edit `data_path` for a normal ft-comb run** — retarget the `dataset` symlink instead.
Reference copies of the EXP_NAME-aware train scripts: `UPD-3D/utils/greenplm/train_scripts/{1,2,3}.sh`.

Stage wiring (same `EXP_NAME` for the whole chain):
- stage1 → `./checkpoints/stage_1_${EXP_NAME}` (`mm_projector.bin`); data `./dataset/T3D/stage_1/brief_1M_caption.json`
- stage2 reads `./checkpoints/stage_1_${EXP_NAME}/mm_projector.bin` → `./checkpoints/stage_2_${EXP_NAME}`; data `./dataset/T3D/stage_2/stage_2_data_210k.json`
- stage3 reads stage2 (`non_lora_trainables.bin` + `--lora_path ./checkpoints/stage_2_${EXP_NAME}`) → `./checkpoints/stage_3_${EXP_NAME}` (final LoRA + `non_lora_trainables.bin`; mid-train `checkpoint-*` dirs are ephemeral under `save_total_limit`); data `./dataset/Objaverse/PointLLM_complex_50k_brief_40k_all_90k.json`

### `dataset` symlink
Retarget via symlink only (never copy the dataset into `REPO`):

```bash
ln -sfn /project/3dllms/melgin/datasets/<new_dataset_folder> \
  /project/3dllms/melgin/GreenPLM_ft-comb/dataset
```

Verify: `readlink -f REPO/dataset` → new folder. `slurm_logs` is likewise a symlink to `/project/3dllms/melgin/slurm_logs/GreenPLM_ft-comb` — keep it that way.

### Checkpoints / naming
No post-hoc `mv`. Pass the same `<experiment_name>` into every stage so dirs are created as `stage_{1,2,3}_<experiment_name>` from the start.
Before launching: confirm `checkpoints/stage_{1,2,3}_<experiment_name>` do **not** already exist (or you will mix/overwrite). Older runs may still use legacy bare `stage_N` or `stage_N_<upd_version_name>` names.

### Inference wrapper (`gplm_inf_upd_ft-comb.sh`)
Edit for the new experiment (overwrite in place; comment out prior active lines):
- `--lora_path ./checkpoints/stage_3_<experiment_name>`
- `--pretrain_mm_mlp_adapter ./checkpoints/stage_3_<experiment_name>/non_lora_trainables.bin`
- `--pc_ckpt_path` = **Uni3D PC encoder** only, e.g.  
  `./pretrained_weight/Uni3D_PC_encoder/modelzoo/uni3d-small/model.pt`  
  **Never** point this at `checkpoints/stage_3_*/checkpoint-*/global_step*/mp_rank_00_model_states.pt` (DeepSpeed train shards). Those are the wrong artifact (LoRA/finetune state, not Uni3D), and mid-train dirs are often deleted by `save_total_limit` after a later save — a common cause of empty `inf_rslts` + `DependencyNeverSatisfied` on move/score.
- `--upd_version_name`, `--unzipped_point_cloud_path`, `--pcl_list_txt_file_path` (UPD prompt/cloud triple; independent of `<experiment_name>`)
- `--json_tag ft-comb`
- `$1` → `--upd_version_name_subfolder`

Point-cloud path rules in `gplm_inf_upd.py` (must match unzipped layout):
- `upd_version_name == "3D-FRONT"`: `{unzipped}/{id}/{scene}/{scene}.ply`
- else: `{unzipped}/{id}/{scene}.ply`

Prompts: `/project/3dllms/melgin/UPD-3D/upd_text/<upd_version_name>/<subfolder>/{id}@{scene}.txt`

Outputs: `REPO/inf_rslts/evaluation/inf_rslts_gplm_<json_tag>_<pcl_list_stem>_<subfolder>.json`

### Inference CLI triples (matched; exhaustive until new datasets exist)

| `--upd_version_name` | `--unzipped_point_cloud_path` | `--pcl_list_txt_file_path` |
|---|---|---|
| `Crops3D_gpt-5-nano` | `/project/3dllms/melgin/datasets/CEA/Crops3D` | `/project/3dllms/melgin/UPD-3D/pcl_lists/Crops3D_test.txt` |
| `3D-FRONT` | `/project/3dllms/melgin/datasets/3d-grand_unzipped/3D-FRONT` | `/project/3dllms/melgin/UPD-3D/pcl_lists/3D-FRONT_test.txt` |
| `GIW529_gpt-5-nano` | `/project/3dllms/melgin/datasets/GIW/giw529subcat` | `/project/3dllms/melgin/UPD-3D/pcl_lists/GIW529_test.txt` |

### Repo sanity checks
- `readlink -f REPO/dataset` → new dataset
- `checkpoints/stage_{1,2,3}_<experiment_name>` absent before train
- `train.py` has the active Open3D `read_pc_2tensor` (not the commented stock-only version)
- `slurm_gplm_inf_upd.sh` calls `gplm_inf_upd_ft-comb.sh`
- Before infer: `test -f` on `--lora_path`’s `adapter_model.safetensors` (or dir), `non_lora_trainables.bin`, and the **Uni3D** `--pc_ckpt_path` file; confirm `pc_ckpt_path` does **not** contain `checkpoint-` / `mp_rank_`
- Clear or move old `REPO/inf_rslts/evaluation/*` before a new inf run so later scoring only sees this experiment

### Launch: train → infer → score
From `REPO` (or absolute paths + that cwd). Same `<experiment_name>` on every stage:

```bash
EXP=<experiment_name>   # e.g. GIW529_gpt-5-nano_GIW_cot_v2
sbatch /project/3dllms/melgin/GreenPLM_ft-comb/slurm_gplm_train_stage1.sh "$EXP"            # → J1
sbatch --dependency=afterok:J1 /project/3dllms/melgin/GreenPLM_ft-comb/slurm_gplm_train_stage2.sh "$EXP"  # → J2
sbatch --dependency=afterok:J2 /project/3dllms/melgin/GreenPLM_ft-comb/slurm_gplm_train_stage3.sh "$EXP"  # → J3
```

(Alternatively `EXP_NAME=<experiment_name> sbatch ...` with no arg.)

After J3 succeeds: point `gplm_inf_upd_ft-comb.sh` at `stage_3_<experiment_name>`, then:

```bash
bash /project/3dllms/melgin/GreenPLM_ft-comb/multi-slurm_gplm_inf.sh
```

Subfolders submitted (must all finish before move/score):
`standard`, `open_ended`, `open_ended_additional_instruction`, `aad_base`, `aad_additional_option`, `aad_additional_instruction`, `iasd_base`, `iasd_additional_option`, `iasd_additional_instruction`, `ivqd_base`, `ivqd_additional_option`, `ivqd_additional_instruction`

**No auto move/score** (unlike MiniGPT’s Option A). After **all** inf jobs succeed:

1. Move `REPO/inf_rslts/evaluation/*.json` into a **new unique** folder:  
   `/project/3dllms/melgin/UPD-3D/unscored_model_responses/<folder>`  
   Name: `<upd_version_name>_test_gplm_ft-comb[_<experiment shorthand>]`  
   e.g. `GIW529_gpt-5-nano_test_gplm_ft-comb` or `..._ft-comb_GIW_cot_v2`.
2. Score:
   ```bash
   /project/3dllms/melgin/gpt-oss_scoring/multi-slurm_score_model_responses.sh \
     /project/3dllms/melgin/UPD-3D/unscored_model_responses/<folder> \
     --partition l40s \
     --answer_key /project/3dllms/melgin/UPD-3D/answer_keys/<upd_version_name>.json
   ```
   Score-submit ≠ scoring done. Results →  
   `/project/3dllms/melgin/UPD-3D/scored_model_responses/<folder>_oss120`  
   (or similarly named; follow the scoring script’s output).

Collect inf job IDs from `sbatch` output / `slurm_logs/gplm_inf_upd_*.out` if chaining move/score with `afterok`.