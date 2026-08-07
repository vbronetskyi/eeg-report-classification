# EEG Report Classification with MedGemma-27B

Classifying free-text clinical EEG reports into **five diagnostic labels** — overall
abnormality, focal/generalized epileptiform activity, and focal/generalized
non-epileptiform activity — with a small, CPU-runnable, quantized **MedGemma-27B**,
grammar-constrained via llama.cpp. Benchmarked against the paper's **Mistral-7B**
(Tian et al.) and a **human** second annotator, on two neurologists' datasets.

> **Headline (pooled n = 1994, whole-report accuracy = all five labels correct):**
> Mistral-7B 74.5% → our best prompt **v5g 87.6%** → human ceiling 89.8%.
> v5g **beats Mistral-7B on all five categories**, **matches or exceeds the human
> annotator on the epileptiform categories**, and sits 2.2 points below the human
> whole-report ceiling — from a ~10 GB Q2_K model on CPU.
>
> **Full results, the tested-and-rejected ideas, and cross-annotator validation:
> [reports/results.md](reports/results.md).**

## Repository structure

```
.
├── src/                  Importable library code (installed via `pip install -e .`)
│   ├── core/               Annotation schema, prompt variants, cohort building
│   │   ├── prompt.py         All prompt variants (v1–v8) + GBNF grammar (+ENFORCE_CONSISTENCY)
│   │   ├── cohort.py         Cohort construction (Zoe, Maria) from the annotation DBs
│   │   └── fields.py         Field definitions and helpers
│   ├── cpu/                llama.cpp CPU inference path (evaluator, chunk runner)
│   └── gpu/                GPU inference path
│
├── prompts/              Each prompt variant as a versioned .txt + export_prompts.py
├── slurm/                Cluster job scripts (run_benchmark, make_gguf, gpu_*)
├── analysis/             Analysis & figure-generation scripts (lib, tables, error analysis, plots)
├── experiments/          Dated experiment records: hypothesis, Slurm job IDs, findings
├── results/              Per-run model outputs as JSON — the reproducible source of every number
├── reports/              Human-readable write-ups (.md + .pdf) and their figures/
├── communications/       Emails to collaborators + the exact prompt attached
├── reference/            External: the Mistral paper's pipeline (Tian et al.) — gitignored
└── scripts/              Repo maintenance (e.g. the reorganization script)
```

**Folder rationale**
- **`src/` vs `analysis/`** — `src/` is the reusable library (schema, prompts, inference);
  `analysis/` is project-specific scripts that read `results/*.json`. Clean import boundary.
- **`prompts/`** — prompts are a first-class research artifact; each variant is a plain
  text file regenerated from `src/core/prompt.py` (single source of truth).
- **`experiments/`** — one dated folder per experiment batch (hypothesis, job IDs,
  outcome). The project's lab notebook.
- **`results/` is committed** — the JSONs hold only predictions, per-class probabilities,
  and reference labels (never report text or IDs), so every figure and table regenerates
  offline from the repo.

## The five labels

| Label | Meaning |
|---|---|
| Abnormality | Is the EEG abnormal at all |
| Focal epileptiform | Epileptiform discharges in one region |
| Generalized epileptiform | Epileptiform discharges across the whole brain |
| Focal non-epileptiform | Non-epileptic disturbance (slowing) in one region |
| Generalized non-epileptiform | Non-epileptic disturbance diffusely (e.g. encephalopathy) |

Per-label scale: 1 confident-no · 2 low-no · 3 low-yes · 4 confident-yes; "present" =
score ≥ 3. Primary metric: **Core F1** vs reference annotator LD.

## Prompt variants

| Variant | What it adds |
|---|---|
| v1 | Original baseline (Impression-first, short definitions) |
| v2 | Professor's revision (neurologist role, body-first, extended ACNS/ILAE definitions) |
| v3 | v1 + explicit focal-epileptiform exclusions (precision) |
| v4 | v1 + structured detect→localize procedure |
| v5 | v3 + focal-vs-generalized discriminator for non-epileptiform slowing |
| v6 | v3 + prompt-only consistency reconciliation (asking the model) |
| v7 | v5 + body-aware abnormality (targets missed body findings) |
| v8 | Deliberately simplified/lean prompt (relies on the grammar for consistency) |

`ENFORCE_CONSISTENCY=1` adds a GBNF grammar that makes a self-contradictory answer
undecodable (overall label emitted last, forced to agree with the subtypes). Variants
run this way are tagged `…g` in results (e.g. `v5g`). It is the single biggest lever and
also lifts the epileptiform-category F1.

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .                      # installs core/cpu/gpu from src/ + deps

python -m analysis.make_tables        # regenerate every metric table from results/
python -m analysis.plot_v34           # regenerate comparison charts -> reports/figures/
python prompts/export_prompts.py      # regenerate prompts/v*.txt from src/core/prompt.py
```

## Running a benchmark (Slurm / CPU)

Everything is env-selected; nothing is hard-coded per run:

```bash
DATASET=zoe GGUF_QUANT=Q2_K PROMPT_VARIANT=v5 CTX_SIZE=8192 \
  sbatch slurm/run_benchmark.sbatch 0 1495 results/zoe_v5_cpu_q2_k_full_n1495.json

# with grammar-enforced consistency (our best setup, v5g):
ENFORCE_CONSISTENCY=1 DATASET=zoe GGUF_QUANT=Q2_K PROMPT_VARIANT=v5 CTX_SIZE=8192 \
  sbatch slurm/run_benchmark.sbatch 0 1495 results/zoe_v5g_cpu_q2_k_full_n1495.json
```

| Variable | Values | Meaning |
|---|---|---|
| `DATASET` | `zoe` \| `maria` | which neurologist's dataset |
| `GGUF_QUANT` | `Q2_K` \| `Q4_K_S` | model quantization (~10 GB / ~15 GB) |
| `PROMPT_VARIANT` | `v1`…`v8` | prompt version (see `prompts/`) |
| `ENFORCE_CONSISTENCY` | `1` | hard-enforce schema consistency in the grammar |
| `CTX_SIZE` | int | context window (8192 for the longer prompts) |

## Reproducibility & privacy

Every figure and number regenerates from `results/*.json` via `analysis/`; prompts from
`src/core/prompt.py` via `prompts/export_prompts.py`; reports rebuild to PDF via
`reports/build_pdfs.sh`. Model: MedGemma-27B GGUF (Q2_K / Q4_K_S), llama.cpp
grammar-constrained, temperature 0, 64-core CPU. Raw annotation databases live outside
the repo (institutional storage); result JSONs store only model predictions,
probabilities, and the LD/SG reference labels — never report text or hashed identifiers.
