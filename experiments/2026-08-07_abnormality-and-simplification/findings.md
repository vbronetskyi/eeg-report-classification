# Findings — abnormality & simplification

Pooled n=1994. Both variants grammar-enforced (0 inconsistencies). Compared to the
prior best **v5g (1746, 87.6%)**. See also `validation.md` (vs SG).

| Variant | full vs LD | % | Abn | FocEpi | GenEpi | FocNon | GenNon |
|---|---|---|---|---|---|---|---|
| **v5g Q2/Q4** | **1746** | **87.6** | 95–96 | 86–88 | 89–90 | 89 | 87–89 |
| v7g Q4 | 1736 | 87.1 | 96 | 86 | 88 | 87 | 90 |
| v7g Q2 | 1717 | 86.1 | 94 | 85 | 90 | 88 | 85 |
| v8g Q4 | 1667 | 83.6 | 94 | 77 | 85 | 86 | 88 |
| v8g Q2 | 1582 | 79.3 | 94 | **59** | 76 | 84 | 85 |

(vs SG: same ordering — v5g ahead, v7g slightly below, v8g well below.)

## Conclusions — both directions rejected; v5g stands
- **v7g (body-aware abnormality) did NOT help.** Abnormality F1 stayed at 94–96% (did
  not reach the human 98%) and slight collateral appeared. The remaining Abnormality gap
  is **not a prompt problem** — the ~43 truly-missed cases are genuinely hard/ambiguous
  (annotators themselves disagree there); "read the body harder" does not recover them.
- **v8g (simplified prompt) regressed, hardest on Focal Epi (59% Q2).** Dropping the
  detailed focal-epi exclusions brought back the over-calling that v3 fixed. Useful
  negative result: **the long exclusion blocks are load-bearing** — over-simplifying hurts.
- **v5g remains the final best (87.6% vs LD, 86.2% vs SG).** Both remaining ideas were
  tested and neither beats it. We are at the practical ceiling: v5g agrees with each
  annotator about as well (86–88%) as the two annotators agree with each other (89.8%).
  The residual ~2–4 points is human-disagreement territory, not prompt headroom.

## Recommendation
Ship **v5g** (prompt v5 + `ENFORCE_CONSISTENCY=1`), Q2_K for size / Q4_K_S if Gen Non-epi
is prioritized. Further prompt tuning against LD past ~90% would be fitting LD, not
improving the model.
