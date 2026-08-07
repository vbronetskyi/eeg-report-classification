#!/bin/bash
#SBATCH --job-name=eeg-q2-chunk
#SBATCH --gres=gpu:nvidia_h100_80gb_hbm3_2g.20gb:1
#SBATCH --cpus-per-task=2
#SBATCH --mem=24G
#SBATCH --time=02:00:00
#SBATCH --output=results/slurm-%x-%j.out
#SBATCH --error=results/slurm-%x-%j.err

set -uo pipefail

START="${1:?Usage: sbatch run_q2_chunk.sbatch START SIZE}"
SIZE="${2:?Usage: sbatch run_q2_chunk.sbatch START SIZE}"
TOTAL=1495

END_EXCLUSIVE=$((START + SIZE))
if (( END_EXCLUSIVE > TOTAL )); then
    END_EXCLUSIVE=$TOTAL
fi

ACTUAL_SIZE=$((END_EXCLUSIVE - START))
END=$((END_EXCLUSIVE - 1))

printf -v START_PAD "%04d" "$START"
printf -v END_PAD "%04d" "$END"

PROJECT="$HOME/test-fir"
BASE="/scratch/brovik/hf/medgemma-27b-text-it"
SOURCE_GGUF="/scratch/brovik/hf/medgemma-27b-text-it-GGUF/medgemma-27b-text-it.Q2_K.gguf"
LOCAL_GGUF="$SLURM_TMPDIR/medgemma-27b-text-it.Q2_K.gguf"

OUTPUT="$PROJECT/results/q2_full_chunk_${START_PAD}_${END_PAD}.json"

module --force purge
module load StdEnv/2023 python/3.12.4 cuda/12.9 gcc/12.3 opencv/4.13.0

cd "$PROJECT"
source .venv/bin/activate

export HF_HOME=/scratch/brovik/hf
export TRANSFORMERS_CACHE=/scratch/brovik/hf
export TOKENIZERS_PARALLELISM=false
export PYTHONUNBUFFERED=1
export VLLM_LOGGING_LEVEL=INFO

mkdir -p results

echo "Node: $(hostname)"
echo "Job: $SLURM_JOB_ID"
echo "Chunk: [$START, $END_EXCLUSIVE)"
echo "Output: $OUTPUT"
echo "Allocation started: $(date --iso-8601=seconds)"
echo "Time limit: 02:00:00"

echo "Copying GGUF to $LOCAL_GGUF"
cp -f "$SOURCE_GGUF" "$LOCAL_GGUF"

SERVER_PID=""
SERVER_ATTEMPT=0

start_server_until_ready() {
    while true; do
        SERVER_ATTEMPT=$((SERVER_ATTEMPT + 1))

        SERVER_LOG="$PROJECT/results/vllm_chunk_${START_PAD}_${END_PAD}_${SLURM_JOB_ID}_attempt${SERVER_ATTEMPT}.log"

        echo "Starting vLLM attempt $SERVER_ATTEMPT"
        echo "vLLM log: $SERVER_LOG"

        vllm serve "$LOCAL_GGUF" \
            --load-format gguf \
            --tokenizer "$BASE" \
            --hf-config-path "$BASE" \
            --served-model-name medgemma-q2 \
            --host 127.0.0.1 \
            --port 8000 \
            --max-model-len 4096 \
            --max-num-seqs 1 \
            --gpu-memory-utilization 0.95 \
            --kv-cache-dtype fp8_e4m3 \
            --enforce-eager \
            --max-logprobs 20 \
            --no-enable-log-requests \
            --disable-uvicorn-access-log \
            >"$SERVER_LOG" 2>&1 &

        SERVER_PID=$!
        echo "vLLM PID: $SERVER_PID"

        while kill -0 "$SERVER_PID" 2>/dev/null; do
            if curl -fsS \
                http://127.0.0.1:8000/v1/models \
                >/dev/null 2>&1
            then
                echo "vLLM server ready: $(date --iso-8601=seconds)"
                return 0
            fi

            sleep 5
        done

        wait "$SERVER_PID" 2>/dev/null || true

        echo "vLLM attempt $SERVER_ATTEMPT exited."
        echo "Retrying within the same GPU allocation in 10 seconds."
        tail -n 80 "$SERVER_LOG" || true
        sleep 10
    done
}

start_server_until_ready

INFER_START_EPOCH=$(date +%s)
echo "Inference started: $(date --iso-8601=seconds)"

while true; do
    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
        echo "vLLM stopped during evaluation; restarting in the same allocation."
        start_server_until_ready
    fi

    python -m gpu.chunk \
        --start-index "$START" \
        --chunk-size "$ACTUAL_SIZE" \
        --model medgemma-q2 \
        --base-url http://127.0.0.1:8000/v1 \
        --max-tokens 768 \
        --retries 2 \
        --output "$OUTPUT"

    EVAL_RC=$?

    if (( EVAL_RC == 0 )); then
        break
    fi

    echo "Evaluator exited with code $EVAL_RC."
    echo "Checkpoint remains saved; retrying in the same allocation."
    sleep 10
done

INFER_END_EPOCH=$(date +%s)
INFER_SECONDS=$((INFER_END_EPOCH - INFER_START_EPOCH))

echo "Inference finished: $(date --iso-8601=seconds)"
echo "Inference seconds: $INFER_SECONDS"

awk \
    -v seconds="$INFER_SECONDS" \
    -v reports="$ACTUAL_SIZE" \
    'BEGIN {
        printf "Average seconds per report: %.2f\n", seconds / reports
    }'

echo "Chunk completed: [$START, $END_EXCLUSIVE)"
echo "Saved to: $OUTPUT"
echo "Benchmark complete."

# Звільняємо GPU одразу після завершення — не тримаємо слайс
# простоюючи до walltime. Глушимо vLLM-сервер і виходимо.
kill "$SERVER_PID" 2>/dev/null || true
echo "Released GPU allocation at $(date --iso-8601=seconds)."
