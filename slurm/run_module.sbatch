#!/bin/bash
#SBATCH --job-name=eeg-plot
#SBATCH --account=rrg-rmcintos_cpu
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:30:00
#SBATCH --output=logs/eeg_plot_%j.out
#SBATCH --error=logs/eeg_plot_%j.err

# Run a python module on a compute node — used when a login node's shared-FS mount is flaky.
#   sbatch slurm/run_module.sbatch analysis.triphasic_harvard_analysis
set -euo pipefail
MODULE="${1:?usage: sbatch run_module.sbatch <module.path>}"
PROJECT="$HOME/test-fir"; cd "$PROJECT"
module --force purge
module load StdEnv/2023 gcc/12.3 python/3.12.4
source .venv/bin/activate
export PYTHONUNBUFFERED=1 MPLBACKEND=Agg
echo "running: python -m $MODULE  on $SLURMD_NODENAME"
python -m "$MODULE"
echo "done."
