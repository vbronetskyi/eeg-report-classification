#!/bin/bash
# Submit the full processed_reports labeling as resumable chunks for a chosen
# quantization. Outputs are quant-tagged and live in results/labels/<qtag>/ so a
# second quant never clobbers an existing labeling (e.g. Q4 does not touch Q2).
#
# Re-running is safe: a chunk whose output already holds all its reports is skipped,
# so after timeouts you just run this again to resubmit only the unfinished chunks.
#
#   QUANT=Q4_K_S CHUNK=1000 WALLTIME=11:59:00 bash slurm/submit_labels.sh
#   DRYRUN=1 bash slurm/submit_labels.sh          # print what would be submitted
#
# Fixed pipeline (matches the validated best config): prompt v5 + ENFORCE_CONSISTENCY
# (v5g), MAX_TOKENS=128, CTX_SIZE=8192.
set -euo pipefail

PROJECT="$HOME/test-fir"
cd "$PROJECT"

QUANT="${QUANT:-Q4_K_S}"
CHUNK="${CHUNK:-1000}"
WALLTIME="${WALLTIME:-10:00:00}"
CTX_SIZE="${CTX_SIZE:-8192}"
MAX_TOKENS="${MAX_TOKENS:-128}"
LABEL_DB="${LABEL_DB:-/project/6019337/vvakorin/incoming/processed_reports_240325.db}"

QTAG=$(echo "$QUANT" | tr 'A-Z' 'a-z')
OUTDIR="$PROJECT/results/labels/$QTAG"
mkdir -p "$OUTDIR" logs

# total rows in the dataset
TOTAL=$(python3 -c "import sqlite3;print(sqlite3.connect('file:$LABEL_DB?mode=ro',uri=True).execute('SELECT COUNT(*) FROM reports').fetchone()[0])")
echo "dataset: $LABEL_DB"
echo "rows: $TOTAL | quant: $QUANT | chunk: $CHUNK | walltime: $WALLTIME | ctx: $CTX_SIZE"
echo "outputs: $OUTDIR/labels_<start>_<end>.json"
echo "------------------------------------------------------------"

submitted=0; skipped=0
start=0
while [ "$start" -lt "$TOTAL" ]; do
    size=$CHUNK
    [ $((start + size)) -gt "$TOTAL" ] && size=$((TOTAL - start))
    end=$((start + size - 1))
    spad=$(printf "%05d" "$start"); epad=$(printf "%05d" "$end")
    out="$OUTDIR/labels_${spad}_${epad}.json"

    # skip chunks already fully labelled
    done_n=0
    if [ -f "$out" ]; then
        done_n=$(python3 -c "import json,sys;d=json.load(open('$out'));print(sum(1 for c in d.get('cases',[]) if c.get('model')))" 2>/dev/null || echo 0)
    fi
    if [ "$done_n" -ge "$size" ]; then
        echo "skip  [$spad,$epad] already complete ($done_n/$size)"
        skipped=$((skipped + 1)); start=$((start + CHUNK)); continue
    fi

    if [ "${DRYRUN:-0}" = "1" ]; then
        echo "DRYRUN submit [$spad,$epad] size=$size (have $done_n)"
    else
        jid=$(sbatch --parsable \
            --time="$WALLTIME" \
            --export=ALL,GGUF_QUANT="$QUANT",PROMPT_VARIANT=v5,ENFORCE_CONSISTENCY=1,CTX_SIZE="$CTX_SIZE",MAX_TOKENS="$MAX_TOKENS",LABEL_DB="$LABEL_DB" \
            slurm/label_reports.sbatch "$start" "$size" "$out")
        echo "submit [$spad,$epad] size=$size (have $done_n) -> job $jid"
    fi
    submitted=$((submitted + 1))
    start=$((start + CHUNK))
done

echo "------------------------------------------------------------"
echo "submitted: $submitted  skipped(complete): $skipped"
