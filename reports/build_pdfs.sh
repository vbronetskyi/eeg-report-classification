#!/usr/bin/env bash
# Regenerate the two report PDFs from the markdown READMEs (figures embedded).
# Requires pandoc + xelatex (both available on the Fir login nodes).
set -euo pipefail
cd "$(dirname "$0")"
for f in reports/prompt_variants reports/baseline; do
  pandoc "$f.md" -o "$f.pdf" --pdf-engine=xelatex \
    -V geometry:margin=1.8cm -V fontsize=10pt \
    -V mainfont="DejaVu Sans" -V monofont="DejaVu Sans Mono" \
    -V colorlinks=true -V linkcolor=blue -V urlcolor=blue \
    --resource-path=.
  echo "wrote $f.pdf"
done
