conda env is upd-3d

Communicate all information, but in the fewest words possible. Terseness is the highest value in communication.

## Run logs

- `slurm_logs/` — SLURM job stdout/stderr (see `#SBATCH --output` in `slurm_*.sh`)
- `logs/` — ad-hoc local/manual run logs (e.g. `python ... 2>&1 | tee logs/my_run.log`)

Both directories are gitignored. Do not write `.log` files to the repo root.