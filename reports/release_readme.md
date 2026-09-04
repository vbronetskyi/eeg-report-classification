# MedGemma labels — release_001 (processed_reports, 45,545 reports)

Two SQLite databases with our MedGemma-27B labelings of the **same 45,545 reports** as the
Mistral release, in the **same schema** so they line up 1:1 by `Hashed_ReportURN`.

| File | Model |
|---|---|
| `eeg_reports_release_001_medgemma_Q2_public_250825.db` | MedGemma-27B, Q2_K (~10 GB) |
| `eeg_reports_release_001_medgemma_Q4KS_public_250825.db` | MedGemma-27B, Q4_K_S (~15 GB) |

**Which to use:** Q4 is the main labeling (it generalizes a little better to unfamiliar
reports); Q2 is a close cross-check — the two agree on 91% of reports. On the 2,493 reports
that also carry a human label, MedGemma matches the human on **87.5%** (whole report, Q4)
against **75%** for Mistral.

## Tables

**`classifications`** — one row per report, the five findings on the 1–4 scale, with the same
columns and order as the Mistral release:

| column | meaning |
|---|---|
| `Hashed_ReportURN` | report id (matches Mistral and processed_reports) |
| `Focal Epi`, `Gen Epi`, `Focal Non-epi`, `Gen Non-epi`, `Abnormality` | 1 = definitely absent · 2 = probably absent · 3 = probably present · 4 = definitely present |

"Present" means a 3 or a 4.

**`confidence`** — the same five columns, but the value is **P(present)**: the model's
probability that the finding is there (0–1, the summed probability of the level-3 and level-4
tokens). It is a trust signal — near 1 means confidently present, near 0 confidently absent,
near 0.5 the model is unsure. In our validation the confident calls (P near 0 or 1) are right
about **99%** of the time and the borderline ones (P near 0.5) only about **80%**, so P(present)
is a good filter for which labels to trust automatically and which to send for human review.

**`about`** — provenance (model, quantization, prompt, scale) as key/value rows.

## How they were made

MedGemma-27B (`google/medgemma-27b-text-it`), prompt v5 with a decoding grammar that forbids
self-contradictory outputs (v5g), temperature 0, run on CPU with llama.cpp — fully
deterministic. **Labels only; the report text is not included.**

Full method, per-category accuracy, and the Mistral vs Q2 vs Q4 comparison are in the
`medgemma_vs_mistral` report (see below).

## Reports (`docs/`)

Our analytics, results, and notes as PDFs:

| File | What it is |
|---|---|
| `medgemma_vs_mistral.pdf` | The main comparison — MedGemma Q4/Q2 vs Mistral vs the human annotator on the 45k set, plus the label-confidence analysis |
| `summary.pdf` | Short summary for colleagues — where each model lands, per category |
| `all_prompts.pdf` | Technical report — all ten prompt variants, the full prompt × quantization matrix, per-dataset tables |
| `prompt_variants.pdf` | Prompt-variant deep-dive — per-variant charts and the Focal-Epi precision/recall analysis behind the prompt choices |
| `baseline.pdf` | Full benchmark results — accuracy by category, generalization (Zoe vs Maria), and over- vs under-calling |

## Code

Pipeline, prompts, and the scripts that build everything here:
**https://github.com/vbronetskyi/eeg-report-classification**
