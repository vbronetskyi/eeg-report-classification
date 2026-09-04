#!/bin/bash
# Submit Q4 labeling of a Harvard (HEEDB) cohort as resumable chunks. Reads the report
# count from the cohort index (analysis/harvard_index.py) and fans out over label_harvard.sbatch.
# Outputs go to results/harvard/labels/<COHORT>/; a chunk already fully labelled is skipped,
# so re-running after timeouts resubmits only the unfinished chunks.
#
#   COHORT=MGH CHUNK=500 WALLTIME=10:00:00 bash slurm/submit_harvard.sh
#   DRYRUN=1 COHORT=MGH bash slurm/submit_harvard.sh
#
# Fixed pipeline (unchanged from our runs): prompt v5 + ENFORCE_CONSISTENCY (v5g),
# Q4_K_S, CTX_SIZE=8192, MAX_TOKENS=128.
set -euo pipefail

PROJECT="$HOME/test-fir"
cd "$PROJECT"

COHORT="${COHORT:-MGH}"
QUANT="${QUANT:-Q4_K_S}"
CHUNK="${CHUNK:-500}"
WALLTIME="${WALLTIME:-10:00:00}"
CTX_SIZE="${CTX_SIZE:-8192}"
MAX_TOKENS="${MAX_TOKENS:-128}"
INDEX="${INDEX:-$PROJECT/results/harvard/${COHORT}_index.json}"

QTAG=$(echo "$QUANT" | tr 'A-Z' 'a-z')
OUTDIR="$PROJECT/results/harvard/labels/$COHORT"
mkdir -p "$OUTDIR" logs

TOTAL=$(python3 -c "import json;print(len(json.load(open('$INDEX'))['reports']))")
START="${START:-0}"   # skip a leading range already handled elsewhere (e.g. a pilot chunk)
echo "cohort: $COHORT | index: $INDEX"
echo "reports: $TOTAL | quant: $QUANT | chunk: $CHUNK | walltime: $WALLTIME | ctx: $CTX_SIZE | start: $START"
echo "outputs: $OUTDIR/labels_${QTAG}_<start>_<end>.json"
echo "------------------------------------------------------------"

submitted=0; skipped=0
start=$START
while [ "$start" -lt "$TOTAL" ]; do
    size=$CHUNK
    [ $((start + size)) -gt "$TOTAL" ] && size=$((TOTAL - start))
    end=$((start + size - 1))
    spad=$(printf "%05d" "$start"); epad=$(printf "%05d" "$end")
    out="$OUTDIR/labels_${QTAG}_${spad}_${epad}.json"

    done_n=0
    if [ -f "$out" ]; then
        # count ALL processed reports (ok + recorded errors); a chunk that finished its
        # slice is done even if a few over-long reports 400'd on context — re-running at the
        # same ctx would only re-fail them. Only genuinely unfinished chunks are resubmitted.
        done_n=$(python3 -c "import json,sys;d=json.load(open('$out'));print(len(d.get('cases',[])))" 2>/dev/null || echo 0)
    fi
    if [ "$done_n" -ge "$size" ]; then
        echo "skip  [$spad,$epad] already processed ($done_n/$size)"
        skipped=$((skipped + 1)); start=$((start + CHUNK)); continue
    fi

    if [ "${DRYRUN:-0}" = "1" ]; then
        echo "DRYRUN submit $COHORT [$spad,$epad] size=$size (have $done_n)"
    else
        jid=$(sbatch --parsable \
            --time="$WALLTIME" \
            --export=ALL,GGUF_QUANT="$QUANT",PROMPT_VARIANT=v5,ENFORCE_CONSISTENCY=1,CTX_SIZE="$CTX_SIZE",MAX_TOKENS="$MAX_TOKENS",COHORT="$COHORT",INDEX="$INDEX" \
            slurm/label_harvard.sbatch "$start" "$size" "$out")
        echo "submit $COHORT [$spad,$epad] size=$size (have $done_n) -> job $jid"
    fi
    submitted=$((submitted + 1))
    start=$((start + CHUNK))
done

echo "------------------------------------------------------------"
echo "submitted: $submitted  skipped(complete): $skipped"
