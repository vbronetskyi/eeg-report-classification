#!/usr/bin/env bash
# One-shot reorganization into a clean, shareable, reproducible layout + fresh git
# history (the old .git had transient corruption and no remote; decision: clean init).
# Safe to run ONLY when no Slurm jobs are active (they read code / write results/).
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"

# ---- guards -----------------------------------------------------------------
if command -v squeue >/dev/null 2>&1 && [[ "$(squeue -u "$USER" -h 2>/dev/null | wc -l)" -ne 0 ]]; then
  echo "ABORT: Slurm jobs still active." >&2; exit 1
fi
[[ -d core && -d analysis ]] || { echo "ABORT: run from repo root." >&2; exit 1; }

echo "==> new folders"
mkdir -p src prompts slurm reports/figures experiments communications scripts

echo "==> library code -> src/"
mv core src/core; mv cpu src/cpu; mv gpu src/gpu

echo "==> job scripts -> slurm/"
mv src/cpu/run_benchmark.sbatch slurm/ 2>/dev/null || true
mv src/cpu/make_gguf.sbatch     slurm/ 2>/dev/null || true
mv src/gpu/run_flat_benchmark.sbatch slurm/ 2>/dev/null || true
mv src/gpu/run_chunk.sbatch          slurm/ 2>/dev/null || true

echo "==> reports + figures -> reports/"
mv results_baseline.md         reports/baseline.md
mv results_prompt_variants.md  reports/prompt_variants.md
mv results_baseline.pdf        reports/baseline.pdf        2>/dev/null || true
mv results_prompt_variants.pdf reports/prompt_variants.pdf 2>/dev/null || true
mv make_pdfs.sh                reports/build_pdfs.sh       2>/dev/null || true
for f in figures/*; do [ -e "$f" ] && mv "$f" "reports/figures/$(basename "$f")"; done
rmdir figures 2>/dev/null || true

echo "==> emails -> communications/, reference pipeline -> reference/"
if [ -d emails ]; then for f in emails/*; do mv "$f" "communications/$(basename "$f")"; done; rmdir emails 2>/dev/null || true; fi
[ -d reference_mistral_pipeline ] && mv reference_mistral_pipeline reference || true

echo "==> point figure generators + PDF build at reports/figures"
sed -i 's#Path("figures")#Path("reports/figures")#g; s#"figures/#"reports/figures/#g' analysis/*.py 2>/dev/null || true
[ -f reports/build_pdfs.sh ] && sed -i 's#results_prompt_variants#reports/prompt_variants#g; s#results_baseline#reports/baseline#g' reports/build_pdfs.sh || true

echo "==> pyproject (editable install keeps 'import core/cpu/gpu' working from src/)"
cat > pyproject.toml <<'PYPROJECT'
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "eeg-report-classification"
version = "0.1.0"
description = "Classifying free-text clinical EEG reports into five diagnostic categories with MedGemma-27B."
requires-python = ">=3.12"
dynamic = ["dependencies"]

[tool.setuptools]
package-dir = {"" = "src"}
packages = ["core", "cpu", "gpu"]

[tool.setuptools.dynamic]
dependencies = {file = ["requirements.txt"]}
PYPROJECT

echo "==> requirements.txt"
source .venv/bin/activate 2>/dev/null || true
python -m pip freeze 2>/dev/null | grep -ivE "^-e |pkg-resources|eeg-report-classification" > requirements.txt || true

echo "==> prompts/export_prompts.py + export the variants"
cat > prompts/export_prompts.py <<'EXPORT'
#!/usr/bin/env python3
"""Regenerate prompts/v*.txt from src/core/prompt.py — the single source of truth."""
import os, importlib
from pathlib import Path
OUT = Path(__file__).resolve().parent
for v in ["v1", "v2", "v3", "v4", "v5", "v6", "v7", "v8"]:
    os.environ["PROMPT_VARIANT"] = v
    import core.prompt as p; importlib.reload(p)
    txt = f"#### SYSTEM ####\n\n{p.SYSTEM}\n\n#### USER PROMPT ({v}) ####\n\n"
    txt += p.build_prompt("<EEG report text is appended here>")
    (OUT / f"{v}.txt").write_text(txt); print("wrote", f"prompts/{v}.txt")
EXPORT

echo "==> .gitignore"
cat > .gitignore <<'GITIGNORE'
.venv/
__pycache__/
*.pyc
third_party/
/scratch/
reference/
archive/
results/*.log
logs/
*.egg-info/
build/
GITIGNORE

echo "==> DONE (moves complete). Run: pip install -e . ; python prompts/export_prompts.py ; then git init."
