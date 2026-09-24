# Reproducing the EEG-report labeling

Everything here regenerates the labels, figures and tables from scratch. Each labeling group has a
submit script that fans the work into resumable Slurm chunks; re-running a submit script after a
timeout resubmits only the chunks that are not yet finished. Fields labeled jointly get one command;
fields labeled separately get one command each.

## Setup (once)

```bash
cd ~/test-fir
python -m venv .venv && source .venv/bin/activate
pip install -e .                     # installs the core / cpu / gpu packages from src/ + deps
```

- **Model:** MedGemma-27B GGUF at `Q4_K_S` (~15 GB; `Q2_K` ~10 GB also supported), run locally via a
  llama.cpp server that each Slurm job starts on its compute node — temperature 0,
  grammar-constrained decoding.
- **Cluster:** CPU jobs on the `rrg-rmcintos_cpu` account. The `slurm/label_*.sbatch` files hold the
  resource directives; the `slurm/submit_*.sh` wrappers do the chunking and resubmission.
- **Fraser Health source:** `/project/6019337/vvakorin/incoming/processed_reports_240325.db` (table
  `reports`, 45,545 rows).
- **Harvard source:** report text is read from the HEEDB zips through a per-cohort index. Build it
  once before any Harvard run:

  ```bash
  python -m analysis.harvard_index MGH
  python -m analysis.harvard_index BWH
  python -m analysis.harvard_index BCH        # -> results/harvard/<COHORT>_index.json
  ```

Common environment knobs accepted by the submit scripts: `QUANT` (default `Q4_K_S`), `CHUNK`,
`WALLTIME`, `CTX_SIZE`, and `DRYRUN=1` to print what would be submitted without submitting.

## Repository structure

```
.
├── README.md              Overview: all findings, present rates, links to every report
├── REPRODUCE.md           This file
├── src/                   Importable library (pip install -e .)
│   ├── core/                Schema, prompts, cohort building
│   │   ├── prompt.py          Abnormality prompt variants (v1–v10) + GBNF grammar
│   │   ├── cohort.py          Validation-cohort construction (Zoe, Maria)
│   │   └── fields.py          Field definitions
│   └── cpu/                 llama.cpp CPU inference + the per-topic labelers
│       ├── evaluator.py       Inference primitives (request, parse, grammar)
│       ├── label_chunk.py     Abnormality labeler (5 fields, joint) — FHA
│       ├── label_harvard.py   Abnormality labeler — Harvard
│       ├── triphasic.py       Triphasic-wave prompts + labeler
│       ├── slowing.py         Focal / generalized slowing prompts + labeler
│       └── background.py      Discontinuous / burst-suppression / suppressed prompts + labeler
├── prompts/               Each abnormality prompt variant as a versioned .txt (from prompt.py)
├── slurm/                 Cluster job scripts (submit_*.sh wrappers + label_*.sbatch)
├── analysis/              Analysis & figure/table scripts that read results/*.json
├── reports/               Human-readable write-ups (.md + .pdf) and their figures/
├── experiments/           Dated experiment records (hypothesis, job IDs, findings)
└── results/               Model outputs as JSON — the reproducible source of every number
```

Data outputs under `results/` that carry hashed report IDs are git-ignored and never published:
the FHA label sets (`results/labels/`, `results/triphasic/`, `results/slowing/`,
`results/background/`) and **all** Harvard outputs (`results/harvard/`, `results/*_harvard/`), which
are under a data-use agreement. Reports and figures hold only aggregate numbers, so they are
committed.

## The prompts

Each group's prompt is the single source of truth in code:

| group | prompt(s) | file |
|---|---|---|
| Abnormality | prompt v5 + consistency grammar (v5g) | [src/core/prompt.py:333](src/core/prompt.py#L333); human-readable [prompts/v5.txt](prompts/v5.txt) |
| Triphasic | `SHORT`, `LONG` | [src/cpu/triphasic.py:45](src/cpu/triphasic.py#L45), [:71](src/cpu/triphasic.py#L71) |
| Slowing | `FOCAL`, `GENERALIZED` | [src/cpu/slowing.py:34](src/cpu/slowing.py#L34), [:83](src/cpu/slowing.py#L83) |
| Background | `DISCONTINUOUS`, `BURST_SUPPRESSION`, `SUPPRESSED` | [src/cpu/background.py:34](src/cpu/background.py#L34), [:77](src/cpu/background.py#L77), [:115](src/cpu/background.py#L115) |

The three-way labelers (triphasic, slowing, background) constrain the answer to `present`,
`explicitly_absent` or `not_mentioned` with a GBNF grammar; the abnormality labeler uses the 1–4
scale with `ENFORCE_CONSISTENCY=1` (grammar makes a self-contradictory answer undecodable).

---

## Group 1 — Abnormality (5 fields, jointly)

Five findings in one pass: `abnormality`, `focal_epileptiform_activity`,
`generalized_epileptiform_activity`, `focal_non_epileptiform_activity`,
`generalized_non_epileptiform_activity`. Prompt v5 + consistency grammar.

```bash
# Fraser Health  -> results/labels/<qtag>/
QUANT=Q4_K_S CHUNK=1000 WALLTIME=11:59:00 bash slurm/submit_labels.sh

# Harvard, one cohort at a time  -> results/harvard/labels/<COHORT>/
COHORT=MGH CHUNK=500 bash slurm/submit_harvard.sh
COHORT=BWH CHUNK=500 bash slurm/submit_harvard.sh
COHORT=BCH CHUNK=500 bash slurm/submit_harvard.sh
```

Labeler: [src/cpu/label_chunk.py](src/cpu/label_chunk.py) (FHA), [slurm/label_harvard.sbatch](slurm/label_harvard.sbatch) (Harvard). Analysis:

```bash
python -m analysis.harvard_abnormality     # Harvard abnormal-call figures + table
python -m analysis.mapping_check           # why only abnormal maps cleanly to Harvard
```

## Group 2 — Triphasic waves (one field, two prompt variants)

Run twice — a short prompt and a long one with the full definitions — to check the result does not
depend on wording.

```bash
# Fraser Health  -> results/triphasic/<VARIANT>/
VARIANT=short CHUNK=2000 bash slurm/submit_triphasic.sh
VARIANT=long  CHUNK=2000 bash slurm/submit_triphasic.sh

# Harvard, all cohorts + both variants  -> results/triphasic_harvard/<COHORT>/<VARIANT>/
bash slurm/submit_triphasic_harvard.sh
```

Labeler: [src/cpu/triphasic.py](src/cpu/triphasic.py). Analysis (includes the text-guard that turns
an unsupported present/absent call into not-mentioned):

```bash
python -m analysis.triphasic_analysis          # FHA: guard + figures + numbers
python -m analysis.triphasic_harvard_analysis  # Harvard: tables + figures
```

## Group 3 — Slowing (2 fields, separately)

```bash
# Fraser Health  -> results/slowing/<FIELD>/
FIELDS="focal"       bash slurm/submit_slowing.sh
FIELDS="generalized" bash slurm/submit_slowing.sh

# Harvard  -> results/slowing_harvard/<COHORT>/<FIELD>/
FIELDS="focal"       bash slurm/submit_slowing_harvard.sh
FIELDS="generalized" bash slurm/submit_slowing_harvard.sh
# (narrow to one hospital with e.g. COHORTS="MGH")
```

Labeler: [src/cpu/slowing.py](src/cpu/slowing.py) (`--field focal|generalized`). Analysis:

```bash
python -m analysis.slowing_vs_harvard    # comparison -> results/harvard/slowing_gold.json
python -m analysis.slowing_chart         # figures
```

## Group 4 — Background patterns (3 fields, separately)

```bash
# Fraser Health  -> results/background/<FIELD>/
FIELDS="discontinuous"     bash slurm/submit_background.sh
FIELDS="burst_suppression" bash slurm/submit_background.sh
FIELDS="suppressed"        bash slurm/submit_background.sh

# Harvard  -> results/background_harvard/<COHORT>/<FIELD>/
FIELDS="discontinuous"     bash slurm/submit_background_harvard.sh
FIELDS="burst_suppression" bash slurm/submit_background_harvard.sh
FIELDS="suppressed"        bash slurm/submit_background_harvard.sh
```

Labeler: [src/cpu/background.py](src/cpu/background.py) (`--field discontinuous|burst_suppression|suppressed`).
Only `burst_suppression` has a Harvard column (`bs`) to compare against. Analysis:

```bash
python -m analysis.background_dist          # distributions -> results/background/dist_summary.json
python -m analysis.background_vs_harvard    # burst-suppression vs Harvard `bs`
python -m analysis.background_chart         # prevalence + burst figures
python -m analysis.background_field_charts  # per-field distribution figures
```

---

## Abnormality prompt variants (for the validation work)

The abnormality group was tuned on two hand-labeled validation sets (Zoe n=1495, Maria n=499)
before the full run. The variants and the benchmark harness:

| Variant | What it adds |
|---|---|
| v1 | Baseline (Impression-first, short definitions) |
| v2 | Neurologist role, body-first, extended ACNS/ILAE definitions |
| v3 | v1 + explicit focal-epileptiform exclusions (precision) |
| v4 | v1 + structured detect→localize procedure |
| v5 | v3 + focal-vs-generalized discriminator for non-epileptiform slowing (**production**) |
| v6–v10 | consistency / body-aware / lean variants |

```bash
# a validation benchmark run (env-selected; nothing hard-coded)
ENFORCE_CONSISTENCY=1 DATASET=zoe GGUF_QUANT=Q4_K_S PROMPT_VARIANT=v5 CTX_SIZE=8192 \
  sbatch slurm/run_benchmark.sbatch 0 1495 results/zoe_v5g_cpu_q4_k_s_full_n1495.json

python prompts/export_prompts.py            # regenerate prompts/v*.txt from src/core/prompt.py
```

| Variable | Values | Meaning |
|---|---|---|
| `DATASET` | `zoe` \| `maria` | which validation set |
| `GGUF_QUANT` | `Q2_K` \| `Q4_K_S` | model quantization |
| `PROMPT_VARIANT` | `v1`…`v10` | prompt version |
| `ENFORCE_CONSISTENCY` | `1` | hard-enforce schema consistency in the grammar |
| `CTX_SIZE` | int | context window (8192 for the longer prompts) |

## Overview figure, consolidated tables, and PDFs

```bash
python -m analysis.overview_prevalence   # reports/figures/overview_fha_prevalence.png
python -m analysis.master_table          # the Harvard comparison + FHA present-rate tables
bash reports/build_pdfs.sh               # rebuild every report PDF (pandoc + xelatex)
```

## Notes for unattended runs

- **Long Harvard chunks** can exceed the walltime; re-run the same submit script and it resubmits
  only the unfinished chunks. For fully unattended completion there are self-rescheduling
  "babysitter" jobs: [slurm/babysit_slowing.sbatch](slurm/babysit_slowing.sbatch),
  [slurm/babysit_background.sbatch](slurm/babysit_background.sbatch).
- **Flaky login-node filesystem:** run any matplotlib / heavy-read module on a compute node with
  `sbatch slurm/run_module.sbatch <module.path>` instead of on the login node.
- **~1–2% of Harvard reports** are longer than the 4096-token context and return no label; they are
  excluded from the counts. A larger `CTX_SIZE` re-pass would pick most of them up.
- **Never commit the Harvard data.** `results/harvard/`, `results/slowing_harvard/`,
  `results/background_harvard/`, `results/triphasic_harvard/` carry report identifiers under the
  data-use agreement and are git-ignored, together with the FHA label outputs.
```
