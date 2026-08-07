# 2026-08-07 — abnormality & simplification

## Motivation
After v5g (87.6%, best), the remaining 2.2-point gap to the human ceiling is **not** in
the epileptiform categories (there we already match/exceed the human) but in
**Abnormality** (95–96% vs human 98%) and **slowing**. Two principled, annotator-agnostic
directions — both grammar-enforced (`ENFORCE_CONSISTENCY=1`), tagged `…g`:

- **v7g** = v5 + a *body-aware abnormality* instruction: if the report body clearly
  describes an abnormality, call the EEG abnormal even when the Impression is conservative.
  Targets the ~77 missed-abnormal EEGs (mostly body-described slowing). This is the
  professor's v2 principle, now safe because the focal-epi exclusions + grammar prevent
  the over-calling collateral v2 caused. A general clinical rule, not annotator-tuned.
- **v8g** = a *deliberately simplified* prompt (~340 tokens vs ~1500): spends words only on
  the two real boundaries (epileptiform vs non-epileptiform; focal vs generalized) and
  delegates consistency to the grammar. Tests whether a short, principled prompt
  generalizes as well as the long ones (less over-fit).

## Validation (guards against fitting to one annotator)
- Score every variant not only vs **LD** (reference) but also vs **SG** (second
  annotator, held out): a real improvement should hold against both.
- Report **SG-vs-LD** human agreement per category as the signal ceiling — beyond it,
  higher LD-F1 is fitting LD's idiosyncrasies, not improvement.
- Require gains to hold on **both** Zoe (in-distribution) and Maria (out-of-distribution).

## Slurm jobs (MedGemma-27B, CPU, temp 0, ctx 8192, ENFORCE_CONSISTENCY=1)
| Variant | Zoe Q2 | Maria Q2 | Zoe Q4 | Maria Q4 |
|---|---|---|---|---|
| v7g | TBD | TBD | TBD | TBD |
| v8g | TBD | TBD | TBD | TBD |

## Reproduce
```bash
ENFORCE_CONSISTENCY=1 DATASET=zoe GGUF_QUANT=Q2_K PROMPT_VARIANT=v7 CTX_SIZE=8192 \
  sbatch slurm/run_benchmark.sbatch 0 1495 results/zoe_v7g_cpu_q2_k_full_n1495.json
ENFORCE_CONSISTENCY=1 DATASET=zoe GGUF_QUANT=Q2_K PROMPT_VARIANT=v8 CTX_SIZE=8192 \
  sbatch slurm/run_benchmark.sbatch 0 1495 results/zoe_v8g_cpu_q2_k_full_n1495.json
```
