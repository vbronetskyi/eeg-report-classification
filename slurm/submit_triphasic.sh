#!/bin/bash
# Submit the full triphasic annotation of the FHA reports as resumable chunks, per prompt
# variant. Outputs -> results/triphasic/<VARIANT>/labels_<start>_<end>.json (rowid slices).
# A chunk that has already processed all its reports is skipped, so re-running after a
# timeout resubmits only the unfinished chunks.
#
#   VARIANT=short CHUNK=2000 bash slurm/submit_triphasic.sh
#   VARIANT=long  CHUNK=2000 bash slurm/submit_triphasic.sh
#   DRYRUN=1 VARIANT=short bash slurm/submit_triphasic.sh
set -euo pipefail

PROJECT="$HOME/test-fir"; cd "$PROJECT"
VARIANT="${VARIANT:-short}"
QUANT="${QUANT:-Q4_K_S}"
CHUNK="${CHUNK:-2000}"
WALLTIME="${WALLTIME:-8:00:00}"
CTX_SIZE="${CTX_SIZE:-4096}"
LABEL_DB="${LABEL_DB:-/project/6019337/vvakorin/incoming/processed_reports_240325.db}"

OUTDIR="$PROJECT/results/triphasic/$VARIANT"
mkdir -p "$OUTDIR" logs
TOTAL=$(python3 -c "import sqlite3;print(sqlite3.connect('file:$LABEL_DB?mode=ro',uri=True).execute('SELECT COUNT(*) FROM reports').fetchone()[0])")
echo "variant: $VARIANT | reports: $TOTAL | chunk: $CHUNK | walltime: $WALLTIME"
echo "------------------------------------------------------------"

sub=0; skip=0; start=0
while [ "$start" -lt "$TOTAL" ]; do
    size=$CHUNK; [ $((start + size)) -gt "$TOTAL" ] && size=$((TOTAL - start))
    end=$((start + size - 1)); sp=$(printf "%05d" "$start"); ep=$(printf "%05d" "$end")
    out="$OUTDIR/labels_${sp}_${ep}.json"
    done_n=0
    [ -f "$out" ] && done_n=$(python3 -c "import json;print(len(json.load(open('$out')).get('cases',[])))" 2>/dev/null || echo 0)
    if [ "$done_n" -ge "$size" ]; then
        echo "skip  $VARIANT [$sp,$ep] already processed ($done_n/$size)"; skip=$((skip + 1)); start=$((start + CHUNK)); continue
    fi
    if [ "${DRYRUN:-0}" = "1" ]; then
        echo "DRYRUN submit $VARIANT [$sp,$ep] size=$size (have $done_n)"
    else
        jid=$(sbatch --parsable --time="$WALLTIME" \
            --export=ALL,GGUF_QUANT="$QUANT",CTX_SIZE="$CTX_SIZE",MAX_TOKENS=64,VARIANT="$VARIANT",LABEL_DB="$LABEL_DB" \
            slurm/label_triphasic.sbatch "$start" "$size" "$out")
        echo "submit $VARIANT [$sp,$ep] size=$size (have $done_n) -> job $jid"
    fi
    sub=$((sub + 1)); start=$((start + CHUNK))
done
echo "------------------------------------------------------------"
echo "submitted: $sub  skipped(complete): $skip"
