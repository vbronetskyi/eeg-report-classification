#!/bin/bash
# Run the triphasic-wave annotation (same prompts as the FHA run) over the Harvard hospitals,
# reading report text from the HEEDB zips via the prebuilt cohort indexes. Resumable, chunked,
# per prompt variant. Output -> results/triphasic_harvard/<COHORT>/<VARIANT>/labels_<s>_<e>.json
#
#   bash slurm/submit_triphasic_harvard.sh                       # all cohorts, both variants
#   COHORTS="MGH" VARIANTS="short" bash slurm/submit_triphasic_harvard.sh
#   DRYRUN=1 bash slurm/submit_triphasic_harvard.sh
set -euo pipefail

PROJECT="$HOME/test-fir"; cd "$PROJECT"
COHORTS="${COHORTS:-MGH BWH BCH}"          # BIDMC excluded — its report text is unavailable
VARIANTS="${VARIANTS:-short long}"
QUANT="${QUANT:-Q4_K_S}"
CHUNK="${CHUNK:-6000}"
WALLTIME="${WALLTIME:-10:00:00}"
CTX_SIZE="${CTX_SIZE:-4096}"

mkdir -p logs
sub=0; skip=0
for COHORT in $COHORTS; do
    INDEX="$PROJECT/results/harvard/${COHORT}_index.json"
    [ -f "$INDEX" ] || { echo "!! no index for $COHORT ($INDEX) — run: python -m analysis.harvard_index $COHORT"; continue; }
    TOTAL=$(python3 -c "import json;print(len(json.load(open('$INDEX'))['reports']))")
    for VARIANT in $VARIANTS; do
        OUTDIR="$PROJECT/results/triphasic_harvard/$COHORT/$VARIANT"; mkdir -p "$OUTDIR"
        echo "=== $COHORT / $VARIANT | reports: $TOTAL | chunk: $CHUNK ==="
        start=0
        while [ "$start" -lt "$TOTAL" ]; do
            size=$CHUNK; [ $((start + size)) -gt "$TOTAL" ] && size=$((TOTAL - start))
            end=$((start + size - 1)); sp=$(printf "%06d" "$start"); ep=$(printf "%06d" "$end")
            out="$OUTDIR/labels_${sp}_${ep}.json"
            done_n=0
            [ -f "$out" ] && done_n=$(python3 -c "import json;print(len(json.load(open('$out')).get('cases',[])))" 2>/dev/null || echo 0)
            if [ "$done_n" -ge "$size" ]; then
                echo "skip  $COHORT/$VARIANT [$sp,$ep] done ($done_n/$size)"; skip=$((skip+1)); start=$((start+CHUNK)); continue
            fi
            if [ "${DRYRUN:-0}" = "1" ]; then
                echo "DRYRUN submit $COHORT/$VARIANT [$sp,$ep] size=$size (have $done_n)"
            else
                jid=$(sbatch --parsable --time="$WALLTIME" \
                    --export=ALL,GGUF_QUANT="$QUANT",CTX_SIZE="$CTX_SIZE",MAX_TOKENS=64,VARIANT="$VARIANT",INDEX="$INDEX" \
                    slurm/label_triphasic.sbatch "$start" "$size" "$out")
                echo "submit $COHORT/$VARIANT [$sp,$ep] size=$size (have $done_n) -> job $jid"
            fi
            sub=$((sub+1)); start=$((start+CHUNK))
        done
    done
done
echo "------------------------------------------------------------"
echo "submitted: $sub  skipped(complete): $skip"
