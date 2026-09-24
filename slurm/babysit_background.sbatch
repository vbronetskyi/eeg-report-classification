#!/bin/bash
# Session-independent watchdog for the background-pattern runs (FHA + Harvard). Runs on the
# cluster, so it survives the interactive session ending. Every cycle:
#   * if any eeg-background label jobs are still queued/running -> wait, reschedule (no duplicates);
#   * else resubmit unfinished chunks (both submit scripts are idempotent: skip complete, resume rest);
#   * when nothing is left to submit -> stop.
# Reschedules itself with `sbatch --begin=now+2hour` until everything is done.
#
#   sbatch slurm/babysit_background.sbatch
#SBATCH --job-name=bg-babysit
#SBATCH --account=rrg-rmcintos_cpu
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:15:00
#SBATCH --output=logs/bg_babysit_%j.out
#SBATCH --error=logs/bg_babysit_%j.err
set -euo pipefail

PROJECT="$HOME/test-fir"; cd "$PROJECT"
INTERVAL="${INTERVAL:-2hour}"
SELF="slurm/babysit_background.sbatch"

reschedule() { sbatch --begin="now+${INTERVAL}" "$SELF" >/dev/null && echo "rescheduled +$INTERVAL"; }

echo "=== bg babysit $(date --iso-8601=seconds) ==="
INQ=$(squeue -u "$USER" -n eeg-background -h -o "%T" 2>/dev/null | grep -cE 'RUNNING|PENDING' || true)
if [ "$INQ" -gt 0 ]; then
    echo "$INQ label jobs still in queue — waiting."
    reschedule; exit 0
fi

echo "queue drained — resubmitting any unfinished chunks..."
A=$(bash slurm/submit_background.sh 2>&1 | grep -vE "^sbatch: NOTE"); echo "$A" | tail -1
B=$(bash slurm/submit_background_harvard.sh 2>&1 | grep -vE "^sbatch: NOTE"); echo "$B" | tail -1
na=$(echo "$A" | sed -n 's/^submitted: \([0-9]*\).*/\1/p' | tail -1); na="${na:-0}"
nb=$(echo "$B" | sed -n 's/^submitted: \([0-9]*\).*/\1/p' | tail -1); nb="${nb:-0}"
tot=$((na + nb))

if [ "$tot" -eq 0 ]; then
    echo "nothing left to submit — background runs complete."
    echo "=== bg babysit chain finished ==="
    exit 0
fi
echo "resubmitted $tot chunk(s) (FHA $na, Harvard $nb)."
reschedule
