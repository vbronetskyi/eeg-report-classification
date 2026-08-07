# Findings — reasoning-first & calibration

Both variants grammar-enforced; compared to the best, **v5g (87.6%)**. Pooled n=1994
unless noted.

## v9g — reasoning-first: REJECTED
The reasoning grammar worked (llama.cpp accepted the leading `"reasoning"` string; labels
parse; no report text is stored). But it is **slower** (reasoning tokens — the Maria jobs
did not finish in 3 h; the Zoe jobs were cancelled) and, on a fair same-case comparison,
**3–6 points worse than v5g**:

| subset | v9g | v5g | Δ |
|---|---|---|---|
| Maria Q4 (n=414) | 84.8 | 87.9 | −3.1 |
| Maria Q2 (n=210) | 84.3 | 84.8 | −0.5 |
| Zoe Q4 (n=517) | 81.0 | 85.7 | −4.6 |
| Zoe Q2 (n=426) | 80.0 | 86.4 | −6.3 |

**Conclusion:** giving the model reasoning latitude instead of explicit rules *loses*.
MedGemma's unaided judgement — even with room to deliberate — under-performs the hand-
written clinical exclusions. The rules encode real signal the model does not reproduce.

## v10g — v5 + evidence calibration: REJECTED
Complete pooled (n=1994):

| variant | vs LD | vs SG |
|---|---|---|
| v5g Q2 | **87.6** | 85.6 |
| v10g Q2 | 86.5 | 85.1 |
| v5g Q4 | **87.6** | 86.2 |
| v10g Q4 | 86.7 | 86.1 |

The general "tie confidence to explicit evidence; prefer absent when balanced" rule
slightly **over-tightened** Focal Epi (Q2 88→85) and did not help elsewhere — net ~1 point
below v5g on both annotators.

## Net
Neither "smart" direction beats **v5g**. Across the whole program (rules, grammar,
abnormality, simplification, reasoning, calibration), the winning combination remains
**v5 prompt + grammar-enforced consistency**; the residual gap to the human annotator is
small and near the level of human–human disagreement.
