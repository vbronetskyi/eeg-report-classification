# 2026-08-07 — reasoning-first & calibration ("smart" variants)

## Motivation
v8 showed that *blindly* shortening the prompt hurts (Focal Epi collapses) — removing
guidance just lets the model's default over-calling return. Two "smart" directions
instead:

- **v9g — reasoning-first ("let the model decide").** A concise expert frame + the two
  decision *questions* (epileptiform vs non-epileptiform? focal vs generalized?) with no
  exclusion lists. The grammar adds a leading free-text `"reasoning"` JSON string, so the
  model deliberates (names each finding, its nature and distribution) and the label tokens
  are generated conditioned on that reasoning. Consistency is still grammar-enforced.
  Tests whether MedGemma's own clinical judgement, given room to think, matches our
  hand-written rules. Run with `REASONING=1 ENFORCE_CONSISTENCY=1 MAX_TOKENS=768`.
- **v10g — improve the best (v5) via evidence calibration.** v5's residual weakness is
  precision (systematic over-call). v10 = v5 + a general rule tying each score to how
  explicitly the report supports that specific subtype, and requiring explicit textual
  support before marking present ("prefer absent when balanced"). A judgement principle,
  not an annotator-specific exclusion. Run with `ENFORCE_CONSISTENCY=1`.

Both are annotator-agnostic and will be validated cross-annotator (vs SG) like v5g.

## Slurm jobs (MedGemma-27B, CPU, temp 0, ctx 8192, grammar-enforced)
| Variant | Zoe Q2 | Maria Q2 | Zoe Q4 | Maria Q4 |
|---|---|---|---|---|
| v9g  (REASONING, max_tokens 768) | 53661546 | 53661547 | 53661548 | 53661549 |
| v10g (calibration) | 53661550 | 53661551 | 53661552 | 53661553 |

## Reproduce
```bash
REASONING=1 MAX_TOKENS=768 ENFORCE_CONSISTENCY=1 DATASET=zoe GGUF_QUANT=Q2_K \
  PROMPT_VARIANT=v9 CTX_SIZE=8192 \
  sbatch slurm/run_benchmark.sbatch 0 1495 results/zoe_v9g_cpu_q2_k_full_n1495.json

ENFORCE_CONSISTENCY=1 DATASET=zoe GGUF_QUANT=Q2_K PROMPT_VARIANT=v10 CTX_SIZE=8192 \
  sbatch slurm/run_benchmark.sbatch 0 1495 results/zoe_v10g_cpu_q2_k_full_n1495.json
```

## Note / risk
v9's reasoning grammar (a leading JSON string field before the constrained labels) is
new; the first v9 job should be checked once running to confirm llama.cpp accepts it and
labels still parse. v9 is also slower (reasoning tokens). Baseline to beat: **v5g 87.6%**.
Benchmark comparison uses `analysis.make_tables` + `analysis.validate_vs_sg`.
