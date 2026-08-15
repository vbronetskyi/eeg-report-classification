#!/usr/bin/env bash
# Regenerate the report PDFs from the markdown (figures embedded).
# Requires pandoc + xelatex (both available on the Fir login nodes).
set -euo pipefail
cd "$(dirname "$0")"          # -> reports/
for f in medgemma_vs_mistral summary all_prompts prompt_variants baseline; do
  [ -f "$f.md" ] || continue
  pandoc "$f.md" -o "$f.pdf" --pdf-engine=xelatex \
    -V geometry:margin=1.7cm -V fontsize=10pt \
    -V mainfont="DejaVu Sans" -V monofont="DejaVu Sans Mono" \
    -V colorlinks=true -V linkcolor=blue -V urlcolor=blue \
    --resource-path=.
  echo "wrote reports/$f.pdf"
done
