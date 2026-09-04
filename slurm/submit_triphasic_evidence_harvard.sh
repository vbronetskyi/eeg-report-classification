#!/bin/bash
# Evidence/verification pass over the Harvard reports flagged present/explicitly_absent for
# triphasic — re-run each and make the model quote the exact supporting text. Resumable,
# chunked, per cohort. Output -> results/triphasic_harvard/<COHORT>/evidence/labels_<s>_<e>.json
#
#   bash slurm/submit_triphasic_evidence_harvard.sh
#   COHORTS="MGH" DRYRUN=1 bash slurm/submit_triphasic_evidence_harvard.sh
set -euo pipefail

PROJECT="$HOME/test-fir"; cd "$PROJECT"
COHORTS="${COHORTS:-MGH BWH BCH}"
QUANT="${QUANT:-Q4_K_S}"
CHUNK="${CHUNK:-1200}"
WALLTIME="${WALLTIME:-10:00:00}"
CTX_SIZE="${CTX_SIZE:-4096}"

mkdir -p logs
sub=0; skip=0
for COHORT in $COHORTS; do
    INDEX="$PROJECT/results/harvard/${COHORT}_index.json"
    IDS="$PROJECT/results/triphasic_harvard/$COHORT/flagged_ids.txt"
    [ -f "$IDS" ] || { echo "!! no flagged_ids for $COHORT ($IDS)"; continue; }
    TOTAL=$(grep -c . "$IDS")
    OUTDIR="$PROJECT/results/triphasic_harvard/$COHORT/evidence"; mkdir -p "$OUTDIR"
    echo "=== $COHORT | flagged: $TOTAL | chunk: $CHUNK ==="
    start=0
    while [ "$start" -lt "$TOTAL" ]; do
        size=$CHUNK; [ $((start + size)) -gt "$TOTAL" ] && size=$((TOTAL - start))
        end=$((start + size - 1)); sp=$(printf "%05d" "$start"); ep=$(printf "%05d" "$end")
        out="$OUTDIR/labels_${sp}_${ep}.json"
        done_n=0
        [ -f "$out" ] && done_n=$(python3 -c "import json;print(len(json.load(open('$out')).get('cases',[])))" 2>/dev/null || echo 0)
        if [ "$done_n" -ge "$size" ]; then
            echo "skip  $COHORT [$sp,$ep] done ($done_n/$size)"; skip=$((skip+1)); start=$((start+CHUNK)); continue
        fi
        if [ "${DRYRUN:-0}" = "1" ]; then
            echo "DRYRUN submit $COHORT [$sp,$ep] size=$size (have $done_n)"
        else
            jid=$(sbatch --parsable --time="$WALLTIME" \
                --export=ALL,GGUF_QUANT="$QUANT",CTX_SIZE="$CTX_SIZE",MAX_TOKENS=200,INDEX="$INDEX" \
                slurm/label_triphasic_evidence.sbatch "$start" "$size" "$IDS" "$out")
            echo "submit $COHORT [$sp,$ep] size=$size (have $done_n) -> job $jid"
        fi
        sub=$((sub+1)); start=$((start+CHUNK))
    done
done
echo "------------------------------------------------------------"
echo "submitted: $sub  skipped(complete): $skip"
