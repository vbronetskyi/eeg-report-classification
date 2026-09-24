#!/bin/bash
# Session-independent watchdog for the Harvard slowing runs. Runs on the cluster (not in an
# interactive Claude session), so it survives the session ending — which is what left the first
# Harvard wave half-finished. Every cycle:
#   * if any eeg-slowing label jobs are still queued/running -> do nothing, reschedule (avoids
#     submitting a duplicate for a chunk that is already being worked on);
#   * else, resubmit unfinished chunks (submit_slowing_harvard.sh is idempotent: it skips the
#     complete ones and only resubmits the rest, resuming each from its partial file);
#   * when nothing is left to submit, run the comparison and STOP (no reschedule).
# It reschedules itself with `sbatch --begin=now+2hour`, forming a self-perpetuating chain until
# the whole Harvard set is done.
#
#   sbatch slurm/babysit_slowing.sbatch          # start the chain
#SBATCH --job-name=slow-babysit
#SBATCH --account=rrg-rmcintos_cpu
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:15:00
#SBATCH --output=logs/slow_babysit_%j.out
#SBATCH --error=logs/slow_babysit_%j.err
set -euo pipefail

PROJECT="$HOME/test-fir"; cd "$PROJECT"
INTERVAL="${INTERVAL:-2hour}"
SELF="slurm/babysit_slowing.sbatch"

reschedule() { sbatch --begin="now+${INTERVAL}" "$SELF" >/dev/null && echo "rescheduled +$INTERVAL"; }

echo "=== babysit $(date --iso-8601=seconds) ==="
INQ=$(squeue -u "$USER" -n eeg-slowing -h -o "%T" 2>/dev/null | grep -cE 'RUNNING|PENDING' || true)
if [ "$INQ" -gt 0 ]; then
    echo "$INQ label jobs still in queue — waiting."
    reschedule; exit 0
fi

echo "queue drained — resubmitting any unfinished Harvard chunks..."
OUT=$(bash slurm/submit_slowing_harvard.sh 2>&1 | grep -vE "^sbatch: NOTE")
echo "$OUT" | tail -3
N=$(echo "$OUT" | sed -n 's/^submitted: \([0-9]*\).*/\1/p' | tail -1)
N="${N:-0}"

if [ "$N" -eq 0 ]; then
    echo "nothing left to submit — Harvard complete. Running comparison."
    module --force purge || true
    module load StdEnv/2023 python/3.12.4 || true
    source .venv/bin/activate || true
    python -m analysis.slowing_vs_harvard 2>&1 | tee results/harvard/slowing_vs_harvard.txt || true
    echo "=== babysit chain finished ==="
    exit 0
fi

echo "resubmitted $N chunk(s)."
reschedule
