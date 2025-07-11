"""
This is generating multiple choice questions so the OPENAI_API_KEY must be set.
This allows for parallel processing the 3D-FRONT_1, 3D-FRONT_2, ..., 3D-FRONT_79 folders
to make the mc text for all scenes (if you have unpacked them that way)
"""

import subprocess
import sys

def submit_slurm_jobs(max_jobnum, prefix="3D-FRONT_"):
    """Submits n Slurm jobs from slurm_mc.sh."""
    for i in range(1, max_jobnum + 1):
        command = ["sbatch", "slurm_mc.sh", prefix + str(i)]
        result = subprocess.run(command, capture_output=True, text=True)
        print(f"Submitted job {i}:")
        print(result.stdout)
        if result.stderr:
            print(f"Error submitting job {i}:")
            print(result.stderr)

if __name__ == "__main__":
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print("Usage: python multi-slurm_mc.py <number_of_jobs> [prefix]")
        sys.exit(1)

    try:
        num_jobs = int(sys.argv[1])
        if num_jobs <= 0:
            raise ValueError("Number of jobs must be a positive integer.")
    except ValueError as e:
        print(f"Invalid number of jobs: {e}")
        sys.exit(1)

    prefix = sys.argv[2] if len(sys.argv) == 3 else "3D-FRONT_"

    submit_slurm_jobs(num_jobs, prefix)