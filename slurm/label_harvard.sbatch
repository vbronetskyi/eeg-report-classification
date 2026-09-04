#!/bin/bash
#SBATCH --job-name=eeg-harvard
#SBATCH --account=rrg-rmcintos_cpu
#SBATCH --cpus-per-task=64
#SBATCH --mem=128G
#SBATCH --time=02:00:00
#SBATCH --output=logs/eeg_harvard_%j.out
#SBATCH --error=logs/eeg_harvard_%j.err
#SBATCH --requeue

set -euo pipefail

START_INDEX="${1:-0}"
CHUNK_SIZE="${2:-1}"

PROJECT="$HOME/test-fir"
LLAMA_SOURCE="$PROJECT/third_party/llama.cpp"

# Same validated pipeline as our runs — prompt v5g, chosen via PROMPT_VARIANT/ENFORCE_CONSISTENCY
# in the environment. Only the data source differs: Harvard report text read from the HEEDB
# zip dumps via a prebuilt cohort index (analysis/harvard_index.py).
QUANT="${GGUF_QUANT:-Q4_K_S}"
QTAG=$(echo "$QUANT" | tr 'A-Z' 'a-z')
PV="${PROMPT_VARIANT:-v1}"
CTX_SIZE="${CTX_SIZE:-8192}"
COHORT="${COHORT:-MGH}"
INDEX="${INDEX:-$PROJECT/results/harvard/${COHORT}_index.json}"

SOURCE_GGUF="/scratch/brovik/hf/medgemma-27b-text-it-GGUF/medgemma-27b-text-it.${QUANT}.gguf"

WORK_DIR="${SLURM_TMPDIR:-/tmp/${USER}/${SLURM_JOB_ID}}"
BUILD_DIR="$WORK_DIR/llama-build"
LOCAL_GGUF="$WORK_DIR/medgemma-27b-text-it.${QUANT}.gguf"

PORT=$((18000 + SLURM_JOB_ID % 1000))

END_INDEX=$((START_INDEX + CHUNK_SIZE - 1))
START_PAD=$(printf "%05d" "$START_INDEX")
END_PAD=$(printf "%05d" "$END_INDEX")

OUTPUT="${3:-$PROJECT/results/harvard/labels/${COHORT}/labels_${QTAG}_${START_PAD}_${END_PAD}.json}"
EVAL_LOG="$PROJECT/logs/harvard_${COHORT}_${START_PAD}_${END_PAD}_job${SLURM_JOB_ID}.log"
SERVER_LOG="$PROJECT/logs/llamacpp_harvard_${QTAG}_job${SLURM_JOB_ID}.log"

mkdir -p \
  "$WORK_DIR" \
  "$BUILD_DIR" \
  "$(dirname "$OUTPUT")" \
  "$PROJECT/logs"

module --force purge
module load \
  StdEnv/2023 \
  gcc/12.3 \
  cmake/3.31.0 \
  python/3.12.4

cd "$PROJECT"
source .venv/bin/activate

export PYTHONUNBUFFERED=1

export OMP_NUM_THREADS="$SLURM_CPUS_PER_TASK"
export OMP_PROC_BIND=spread
export OMP_PLACES=cores
export OPENBLAS_NUM_THREADS="$SLURM_CPUS_PER_TASK"

echo "============================================================"
echo "Harvard HEEDB labeling ($QUANT)"
echo "Job:          $SLURM_JOB_ID"
echo "Node:         $SLURMD_NODENAME"
echo "Cohort:       $COHORT"
echo "Index:        $INDEX"
echo "Start index:  $START_INDEX"
echo "Chunk size:   $CHUNK_SIZE"
echo "Output:       $OUTPUT"
echo "============================================================"

echo
echo "CPU information:"
lscpu \
  | grep -E \
'^(Architecture|CPU\(s\)|Model name|Socket|Core|Thread|NUMA node)'

echo
echo "llama.cpp commit:"
git -C "$LLAMA_SOURCE" rev-parse HEAD

echo
echo "Building llama-server..."

BUILD_START=$(date +%s)

cmake \
  -S "$LLAMA_SOURCE" \
  -B "$BUILD_DIR" \
  -DCMAKE_BUILD_TYPE=Release \
  -DGGML_NATIVE=ON \
  -DGGML_OPENMP=ON \
  -DGGML_BLAS=OFF

cmake --build "$BUILD_DIR" \
  --target llama-server \
  -j "$SLURM_CPUS_PER_TASK"

BUILD_END=$(date +%s)

echo "Build seconds: $((BUILD_END - BUILD_START))"

if [[ ! -x "$BUILD_DIR/bin/llama-server" ]]; then
    echo "llama-server binary was not created." >&2
    exit 1
fi

echo
echo "Copying $QUANT model to local scratch..."

COPY_START=$(date +%s)

# /scratch (Lustre) occasionally throws a transient "transport endpoint shutdown"
# on stat/read, which killed whole jobs under `set -e`. Retry the copy with backoff
# and verify the copied size matches the source before trusting it.
SRC_BYTES=$(stat -c%s "$SOURCE_GGUF" 2>/dev/null || echo 0)
COPY_OK=0
for attempt in 1 2 3 4 5 6; do
    if cp "$SOURCE_GGUF" "$LOCAL_GGUF" 2>/dev/null; then
        sync
        DST_BYTES=$(stat -c%s "$LOCAL_GGUF" 2>/dev/null || echo 0)
        if [[ "$SRC_BYTES" -gt 0 && "$DST_BYTES" == "$SRC_BYTES" ]]; then
            COPY_OK=1
            echo "Copy ok on attempt $attempt ($DST_BYTES bytes)"
            break
        fi
        echo "Copy incomplete on attempt $attempt (src=$SRC_BYTES dst=$DST_BYTES); retrying..."
    else
        echo "Copy failed on attempt $attempt (transient FS error); retrying..."
    fi
    rm -f "$LOCAL_GGUF" 2>/dev/null || true
    SRC_BYTES=$(stat -c%s "$SOURCE_GGUF" 2>/dev/null || echo "$SRC_BYTES")
    sleep $((attempt * 20))
done

if [[ "$COPY_OK" -ne 1 ]]; then
    # 6 retries all failed -> this node's /scratch is persistently broken, not a transient
    # glitch. Requeue so Slurm reschedules the job (very likely onto a healthy node) instead
    # of marking it FAILED and needing a manual resubmit.
    echo "Model copy failed after 6 attempts on ${SLURMD_NODENAME} — requeuing onto another node." >&2
    scontrol requeue "$SLURM_JOB_ID" 2>/dev/null || true
    sleep 30
    exit 1
fi

COPY_END=$(date +%s)

echo "Copy seconds: $((COPY_END - COPY_START))"
ls -lh "$LOCAL_GGUF"

echo
echo "Starting llama-server..."

"$BUILD_DIR/bin/llama-server" \
  --model "$LOCAL_GGUF" \
  --alias medgemma-q2 \
  --ctx-size "$CTX_SIZE" \
  --threads "$SLURM_CPUS_PER_TASK" \
  --threads-batch "$SLURM_CPUS_PER_TASK" \
  --parallel 1 \
  --host 127.0.0.1 \
  --port "$PORT" \
  --offline \
  --log-verbosity 2 \
  >"$SERVER_LOG" 2>&1 &

SERVER_PID=$!

cleanup() {
    if kill -0 "$SERVER_PID" 2>/dev/null; then
        kill "$SERVER_PID" 2>/dev/null || true
        wait "$SERVER_PID" 2>/dev/null || true
    fi
}

trap cleanup EXIT INT TERM

echo "llama-server PID: $SERVER_PID"
echo "Waiting for server readiness without an internal timeout..."

while true; do
    if curl -fsS \
      "http://127.0.0.1:${PORT}/health" \
      >/dev/null 2>&1; then
        break
    fi

    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
        echo "llama-server exited before becoming ready." >&2
        tail -n 100 "$SERVER_LOG" >&2 || true
        exit 1
    fi

    sleep 5
done

echo "llama-server is ready: $(date --iso-8601=seconds)"

curl -fsS \
  "http://127.0.0.1:${PORT}/v1/models" \
  | python -c '
import json
import sys

payload = json.load(sys.stdin)
models = payload.get("data", [])

for model in models:
    print(
        "Loaded model:",
        model.get("id", "<unknown>"),
    )
'

INFERENCE_START=$(date +%s)

python -m cpu.label_harvard \
  --index "$INDEX" \
  --start-index "$START_INDEX" \
  --chunk-size "$CHUNK_SIZE" \
  --model medgemma-q2 \
  --base-url "http://127.0.0.1:${PORT}/v1" \
  --max-tokens "${MAX_TOKENS:-128}" \
  --retries 2 \
  --output "$OUTPUT" \
  2>&1 | tee "$EVAL_LOG"

INFERENCE_END=$(date +%s)
INFERENCE_SECONDS=$((INFERENCE_END - INFERENCE_START))

echo
echo "============================================================"
echo "Harvard labeling completed"
echo "Inference seconds: $INFERENCE_SECONDS"

awk \
  -v seconds="$INFERENCE_SECONDS" \
  -v count="$CHUNK_SIZE" \
  'BEGIN {
      printf "Average seconds per requested report: %.2f\n",
             seconds / count
  }'

echo "Output:     $OUTPUT"
echo "Evaluator:  $EVAL_LOG"
echo "Server log: $SERVER_LOG"
echo "============================================================"
