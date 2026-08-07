# 2026-08-06 — consistency & slowing

## Motivation
Error analysis of the previous best (v3, Q2, pooled n=1994) showed:
- Detection is solved (recall high everywhere); residual errors are **boundary**
  confusions on the distribution×nature grid.
- Dominant error: **focal↔generalized mis-bucketing of slowing** — 51/73 focal-non
  false positives are truly generalized-non; 60/70 generalized-non FPs are truly
  focal-non.
- ~34 outputs violate the schema's own consistency rule (a subtype marked present
  while the EEG is called normal).

## Variants (all built on v3 to isolate one change each)
- **v5**  = v3 + explicit focal-vs-generalized discriminator for non-epileptiform slowing.
- **v6**  = v3 + prompt-only consistency reconciliation (ask the model to self-correct).
- **v3g** = v3 prompt + GBNF-**enforced** consistency (overall label emitted last;
  grammar permits "abnormal" iff ≥1 subtype present — contradiction is undecodable).
- **v5g** = v5 + the same grammar enforcement (combine both fixes).

## Slurm jobs (MedGemma-27B, CPU rrg-rmcintos_cpu, temp 0, ctx 8192)
| Variant | Zoe Q2 | Maria Q2 | Zoe Q4 | Maria Q4 |
|---|---|---|---|---|
| v5   | 53446846 | 53446847 | 53449039 | 53449040 |
| v6   | 53449042 | 53449043 | 53449044 | 53449045 |
| v3g  | 53450965 | 53450966 | 53450967 | 53450968 |
| v5g  | 53502402 | 53502403 | 53502404 | 53502405 |

## Reproduce
```bash
ENFORCE_CONSISTENCY=1 DATASET=zoe GGUF_QUANT=Q2_K PROMPT_VARIANT=v5 CTX_SIZE=8192 \
  sbatch slurm/run_benchmark.sbatch 0 1495 results/zoe_v5g_cpu_q2_k_full_n1495.json
```
(drop `ENFORCE_CONSISTENCY` for v5/v6; use `PROMPT_VARIANT=v3` + `ENFORCE_CONSISTENCY` for v3g.)

See `findings.md` for results and conclusions.
