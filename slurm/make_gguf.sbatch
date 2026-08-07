#!/bin/bash
#SBATCH --job-name=medgemma-quant
#SBATCH --account=rrg-rmcintos_cpu
#SBATCH --cpus-per-task=64
#SBATCH --mem=128G
#SBATCH --time=02:00:00
#SBATCH --output=logs/make_gguf_%j.out
#SBATCH --error=logs/make_gguf_%j.err

# Build a K-quant GGUF from the HF base model, reproducibly.
#   Usage: sbatch cpu/make_gguf.sbatch [QUANT]   (default Q4_K_S)
# Produces (cached, skipped if present):
#   <GGUF_DIR>/medgemma-27b-text-it.f16.gguf     (intermediate, ~54 GB)
#   <GGUF_DIR>/medgemma-27b-text-it.<QUANT>.gguf

set -euo pipefail

QUANT="${1:-Q4_K_S}"
PROJECT="$HOME/test-fir"
LLAMA_SOURCE="$PROJECT/third_party/llama.cpp"
BASE="/scratch/brovik/hf/medgemma-27b-text-it"
GGUF_DIR="/scratch/brovik/hf/medgemma-27b-text-it-GGUF"
F16="$GGUF_DIR/medgemma-27b-text-it.f16.gguf"
OUT="$GGUF_DIR/medgemma-27b-text-it.${QUANT}.gguf"

WORK_DIR="${SLURM_TMPDIR:-/tmp/${USER}/${SLURM_JOB_ID}}"
BUILD_DIR="$WORK_DIR/llama-build"
mkdir -p "$BUILD_DIR" "$GGUF_DIR" "$PROJECT/logs"

module --force purge
module load StdEnv/2023 gcc/12.3 cmake/3.31.0 python/3.12.4
cd "$PROJECT"
source .venv/bin/activate
export OMP_NUM_THREADS="$SLURM_CPUS_PER_TASK"

echo "============================================================"
echo "Quantization job $SLURM_JOB_ID on $SLURMD_NODENAME"
echo "Target quant: $QUANT   ->   $OUT"
echo "llama.cpp commit: $(git -C "$LLAMA_SOURCE" rev-parse --short HEAD)"
echo "============================================================"

if [[ -f "$OUT" ]]; then
    echo "$OUT already exists — nothing to do."
    ls -lh "$OUT"
    exit 0
fi

echo "Building llama-quantize..."
cmake -S "$LLAMA_SOURCE" -B "$BUILD_DIR" \
  -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=ON -DGGML_OPENMP=ON -DGGML_BLAS=OFF
cmake --build "$BUILD_DIR" --target llama-quantize -j "$SLURM_CPUS_PER_TASK"
QUANTIZE="$BUILD_DIR/bin/llama-quantize"
[[ -x "$QUANTIZE" ]] || { echo "llama-quantize not built" >&2; exit 1; }

# Step 1: HF -> f16 GGUF (reused across quants)
if [[ -f "$F16" ]]; then
    echo "f16 intermediate already present, reusing: $F16"
else
    echo "Converting HF base -> f16 GGUF ..."
    T0=$(date +%s)
    python "$LLAMA_SOURCE/convert_hf_to_gguf.py" "$BASE" \
      --outfile "$F16" --outtype f16
    echo "convert seconds: $(( $(date +%s) - T0 ))"
    ls -lh "$F16"
fi

# Step 2: f16 -> QUANT
echo "Quantizing f16 -> $QUANT ..."
T0=$(date +%s)
"$QUANTIZE" "$F16" "$OUT" "$QUANT"
echo "quantize seconds: $(( $(date +%s) - T0 ))"

echo "Done:"
ls -lh "$OUT"
