#!/bin/bash
#SBATCH --job-name=eeg-q2-cpu
#SBATCH --account=rrg-rmcintos_cpu
#SBATCH --cpus-per-task=64
#SBATCH --mem=128G
#SBATCH --time=02:00:00
#SBATCH --output=logs/eeg_q2_cpu_%j.out
#SBATCH --error=logs/eeg_q2_cpu_%j.err

set -euo pipefail

START_INDEX="${1:-0}"
CHUNK_SIZE="${2:-1}"

PROJECT="$HOME/test-fir"
LLAMA_SOURCE="$PROJECT/third_party/llama.cpp"

# Quantization is selectable via GGUF_QUANT (default Q2_K); dataset via DATASET
# (default zoe) — the evaluator reads DATASET from the environment (core.cohort).
QUANT="${GGUF_QUANT:-Q2_K}"
QTAG=$(echo "$QUANT" | tr 'A-Z' 'a-z')
DS="${DATASET:-zoe}"
PV="${PROMPT_VARIANT:-v1}"
CTX_SIZE="${CTX_SIZE:-4096}"

SOURCE_GGUF="/scratch/brovik/hf/medgemma-27b-text-it-GGUF/medgemma-27b-text-it.${QUANT}.gguf"

WORK_DIR="${SLURM_TMPDIR:-/tmp/${USER}/${SLURM_JOB_ID}}"
BUILD_DIR="$WORK_DIR/llama-build"
LOCAL_GGUF="$WORK_DIR/medgemma-27b-text-it.${QUANT}.gguf"

PORT=$((18000 + SLURM_JOB_ID % 1000))

END_INDEX=$((START_INDEX + CHUNK_SIZE - 1))
START_PAD=$(printf "%04d" "$START_INDEX")
END_PAD=$(printf "%04d" "$END_INDEX")

LABEL_DB="${LABEL_DB:-/project/6019337/vvakorin/incoming/processed_reports_240325.db}"
OUTPUT="${3:-$PROJECT/results/labels/labels_${START_PAD}_${END_PAD}.json}"
EVAL_LOG="$PROJECT/logs/label_${START_PAD}_${END_PAD}_job${SLURM_JOB_ID}.log"
SERVER_LOG="$PROJECT/logs/llamacpp_label_${QTAG}_job${SLURM_JOB_ID}.log"

mkdir -p \
  "$WORK_DIR" \
  "$BUILD_DIR" \
  "$PROJECT/results" \
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
echo "CPU Q2_K benchmark"
echo "Job:          $SLURM_JOB_ID"
echo "Node:         $SLURMD_NODENAME"
echo "CPU cores:    $SLURM_CPUS_PER_TASK"
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

cp "$SOURCE_GGUF" "$LOCAL_GGUF"
sync

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

mkdir -p "$PROJECT/results/labels"

python -m cpu.label_chunk \
  --start-index "$START_INDEX" \
  --chunk-size "$CHUNK_SIZE" \
  --db "$LABEL_DB" \
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
echo "CPU benchmark completed"
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
