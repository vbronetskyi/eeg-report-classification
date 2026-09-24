#!/usr/bin/env bash
# Regenerate the report PDFs from the markdown (figures embedded).
# Requires pandoc + xelatex (both available on the Fir login nodes).
set -euo pipefail
cd "$(dirname "$0")"          # -> reports/
for f in medgemma_vs_mistral medgemma_vs_biomedllama medgemma_vs_biomedllama_abnormality triphasic_waves triphasic_harvard harvard_llm_labeling eeg_labeling_summary slowing_vs_harvard background_patterns discontinuous_background burst_suppression suppressed_background summary all_prompts prompt_variants baseline; do
  [ -f "$f.md" ] || continue
  pandoc "$f.md" -o "$f.pdf" --pdf-engine=xelatex \
    -V geometry:margin=1.7cm -V fontsize=10pt \
    -V mainfont="DejaVu Sans" -V monofont="DejaVu Sans Mono" \
    -V colorlinks=true -V linkcolor=blue -V urlcolor=blue \
    --resource-path=.
  echo "wrote reports/$f.pdf"
done
