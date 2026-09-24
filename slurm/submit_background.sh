#!/bin/bash
# Submit the background-pattern annotation of the FHA reports as resumable chunks, one field at a
# time. Output -> results/background/<FIELD>/labels_<start>_<end>.json (rowid slices).
#
#   bash slurm/submit_background.sh                                  # all three fields
#   FIELDS="burst_suppression" CHUNK=2000 bash slurm/submit_background.sh
#   DRYRUN=1 bash slurm/submit_background.sh
set -euo pipefail

PROJECT="$HOME/test-fir"; cd "$PROJECT"
FIELDS="${FIELDS:-discontinuous burst_suppression suppressed}"
QUANT="${QUANT:-Q4_K_S}"
CHUNK="${CHUNK:-2000}"
WALLTIME="${WALLTIME:-8:00:00}"
CTX_SIZE="${CTX_SIZE:-4096}"
LABEL_DB="${LABEL_DB:-/project/6019337/vvakorin/incoming/processed_reports_240325.db}"

mkdir -p logs
TOTAL=$(python3 -c "import sqlite3;print(sqlite3.connect('file:$LABEL_DB?mode=ro',uri=True).execute('SELECT COUNT(*) FROM reports').fetchone()[0])")
echo "reports: $TOTAL | fields: $FIELDS | chunk: $CHUNK | walltime: $WALLTIME"
echo "------------------------------------------------------------"

sub=0; skip=0
for FIELD in $FIELDS; do
    OUTDIR="$PROJECT/results/background/$FIELD"; mkdir -p "$OUTDIR"
    start=0
    while [ "$start" -lt "$TOTAL" ]; do
        size=$CHUNK; [ $((start + size)) -gt "$TOTAL" ] && size=$((TOTAL - start))
        end=$((start + size - 1)); sp=$(printf "%05d" "$start"); ep=$(printf "%05d" "$end")
        out="$OUTDIR/labels_${sp}_${ep}.json"
        done_n=0
        [ -f "$out" ] && done_n=$(python3 -c "import json;print(len(json.load(open('$out')).get('cases',[])))" 2>/dev/null || echo 0)
        if [ "$done_n" -ge "$size" ]; then
            echo "skip  $FIELD [$sp,$ep] already processed ($done_n/$size)"; skip=$((skip + 1)); start=$((start + CHUNK)); continue
        fi
        if [ "${DRYRUN:-0}" = "1" ]; then
            echo "DRYRUN submit $FIELD [$sp,$ep] size=$size (have $done_n)"
        else
            jid=$(sbatch --parsable --time="$WALLTIME" \
                --export=ALL,GGUF_QUANT="$QUANT",CTX_SIZE="$CTX_SIZE",MAX_TOKENS=32,FIELD="$FIELD",LABEL_DB="$LABEL_DB" \
                slurm/label_background.sbatch "$start" "$size" "$out")
            echo "submit $FIELD [$sp,$ep] size=$size (have $done_n) -> job $jid"
        fi
        sub=$((sub + 1)); start=$((start + CHUNK))
    done
done
echo "------------------------------------------------------------"
echo "submitted: $sub  skipped(complete): $skip"
