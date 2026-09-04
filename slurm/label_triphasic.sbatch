#!/bin/bash
#SBATCH --job-name=eeg-triphasic
#SBATCH --account=rrg-rmcintos_cpu
#SBATCH --cpus-per-task=32
#SBATCH --mem=64G
#SBATCH --time=06:00:00
#SBATCH --output=logs/eeg_triphasic_%j.out
#SBATCH --error=logs/eeg_triphasic_%j.err
#SBATCH --requeue

set -euo pipefail

START_INDEX="${1:-0}"
CHUNK_SIZE="${2:-1}"

PROJECT="$HOME/test-fir"
LLAMA_SOURCE="$PROJECT/third_party/llama.cpp"

QUANT="${GGUF_QUANT:-Q4_K_S}"
QTAG=$(echo "$QUANT" | tr 'A-Z' 'a-z')
CTX_SIZE="${CTX_SIZE:-4096}"
VARIANT="${VARIANT:-short}"
IDS_FILE="${IDS_FILE:-}"
INDEX="${INDEX:-}"
LABEL_DB="${LABEL_DB:-/project/6019337/vvakorin/incoming/processed_reports_240325.db}"

SOURCE_GGUF="/scratch/brovik/hf/medgemma-27b-text-it-GGUF/medgemma-27b-text-it.${QUANT}.gguf"

WORK_DIR="${SLURM_TMPDIR:-/tmp/${USER}/${SLURM_JOB_ID}}"
BUILD_DIR="$WORK_DIR/llama-build"
LOCAL_GGUF="$WORK_DIR/medgemma-27b-text-it.${QUANT}.gguf"
PORT=$((18000 + SLURM_JOB_ID % 1000))

END_INDEX=$((START_INDEX + CHUNK_SIZE - 1))
START_PAD=$(printf "%05d" "$START_INDEX")
END_PAD=$(printf "%05d" "$END_INDEX")

OUTPUT="${3:-$PROJECT/results/triphasic/${VARIANT}/labels_${START_PAD}_${END_PAD}.json}"
EVAL_LOG="$PROJECT/logs/triphasic_${VARIANT}_${START_PAD}_${END_PAD}_job${SLURM_JOB_ID}.log"
SERVER_LOG="$PROJECT/logs/llamacpp_triphasic_${QTAG}_job${SLURM_JOB_ID}.log"

mkdir -p "$WORK_DIR" "$BUILD_DIR" "$(dirname "$OUTPUT")" "$PROJECT/logs"

module --force purge
module load StdEnv/2023 gcc/12.3 cmake/3.31.0 python/3.12.4
cd "$PROJECT"; source .venv/bin/activate
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS="$SLURM_CPUS_PER_TASK" OMP_PROC_BIND=spread OMP_PLACES=cores
export OPENBLAS_NUM_THREADS="$SLURM_CPUS_PER_TASK"

echo "============================================================"
echo "Triphasic annotation ($QUANT, variant=$VARIANT)"
echo "Job: $SLURM_JOB_ID  Node: $SLURMD_NODENAME  Cores: $SLURM_CPUS_PER_TASK"
echo "Slice: [$START_INDEX,$END_INDEX]  ids-file: ${IDS_FILE:-<none>}"
echo "Output: $OUTPUT"
echo "============================================================"

echo "Building llama-server..."
cmake -S "$LLAMA_SOURCE" -B "$BUILD_DIR" -DCMAKE_BUILD_TYPE=Release \
  -DGGML_NATIVE=ON -DGGML_OPENMP=ON -DGGML_BLAS=OFF
cmake --build "$BUILD_DIR" --target llama-server -j "$SLURM_CPUS_PER_TASK"
[[ -x "$BUILD_DIR/bin/llama-server" ]] || { echo "no llama-server binary" >&2; exit 1; }

echo "Copying $QUANT model to local scratch..."
SRC_BYTES=$(stat -c%s "$SOURCE_GGUF" 2>/dev/null || echo 0)
COPY_OK=0
for attempt in 1 2 3 4 5 6; do
    if cp "$SOURCE_GGUF" "$LOCAL_GGUF" 2>/dev/null; then
        sync
        DST_BYTES=$(stat -c%s "$LOCAL_GGUF" 2>/dev/null || echo 0)
        if [[ "$SRC_BYTES" -gt 0 && "$DST_BYTES" == "$SRC_BYTES" ]]; then COPY_OK=1; break; fi
    fi
    echo "copy attempt $attempt failed; retrying..." >&2
    rm -f "$LOCAL_GGUF" 2>/dev/null || true
    SRC_BYTES=$(stat -c%s "$SOURCE_GGUF" 2>/dev/null || echo "$SRC_BYTES")
    sleep $((attempt * 20))
done
if [[ "$COPY_OK" -ne 1 ]]; then
    echo "Model copy failed on ${SLURMD_NODENAME} — requeuing." >&2
    scontrol requeue "$SLURM_JOB_ID" 2>/dev/null || true; sleep 30; exit 1
fi
ls -lh "$LOCAL_GGUF"

echo "Starting llama-server..."
"$BUILD_DIR/bin/llama-server" --model "$LOCAL_GGUF" --alias medgemma-q2 \
  --ctx-size "$CTX_SIZE" --threads "$SLURM_CPUS_PER_TASK" \
  --threads-batch "$SLURM_CPUS_PER_TASK" --parallel 1 \
  --host 127.0.0.1 --port "$PORT" --offline --log-verbosity 2 \
  >"$SERVER_LOG" 2>&1 &
SERVER_PID=$!
cleanup() { kill "$SERVER_PID" 2>/dev/null || true; wait "$SERVER_PID" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

while true; do
    curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1 && break
    kill -0 "$SERVER_PID" 2>/dev/null || { echo "server died" >&2; tail -n 60 "$SERVER_LOG" >&2; exit 1; }
    sleep 5
done
echo "llama-server ready: $(date --iso-8601=seconds)"

python -m cpu.triphasic \
  --variant "$VARIANT" \
  ${IDS_FILE:+--ids-file "$IDS_FILE"} \
  ${INDEX:+--index "$INDEX"} \
  --start-index "$START_INDEX" --chunk-size "$CHUNK_SIZE" \
  --db "$LABEL_DB" --model medgemma-q2 \
  --base-url "http://127.0.0.1:${PORT}/v1" \
  --max-tokens "${MAX_TOKENS:-64}" --retries 2 \
  --output "$OUTPUT" 2>&1 | tee "$EVAL_LOG"

echo "Output: $OUTPUT"
