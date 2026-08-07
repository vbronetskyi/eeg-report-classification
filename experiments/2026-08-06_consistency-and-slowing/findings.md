# Findings — consistency & slowing

Pooled over Zoe+Maria (n=1994), Core F1 vs LD, "full" = all 5 labels correct.

| variant | full (Q2) | full (Q4) | inconsistencies (Q2/Q4) | note |
|---|---|---|---|---|
| v3 (base) | 1679 | 1659 | 57 / 114 | previous best |
| v5  (slowing prompt) | 1652 | 1689 | 128 / 111 | GenNon/FocNon up, but inconsistency side-effect |
| v6  (ask for consistency) | 1636 | 1686 | 53 / 101 | prompt-only asking did NOT hold; hurt other fields |
| v3g (grammar-enforced) | 1717 | 1725 | **0 / 0** | consistency guaranteed; also lifted FocEpi/GenEpi F1 |
| **v5g (v5 + grammar)** | **1746** | **1746** | **0 / 0** | **best of all** |

## Conclusions
- **Grammar-enforced consistency is the decisive lever.** Asking the model in the prompt
  (v6) does not reliably work and can hurt; the GBNF guarantee (subtypes first, overall
  last) removes contradictions AND improves Focal/Gen epileptiform F1 (deciding the parts
  before the whole).
- **v5's slowing discriminator only pays off with the grammar** — on its own its
  side-effect is inconsistency, which the grammar removes — so **v5g** is the winning
  combination.
- **v5g = 1746/1994 (87.6%)** — beats Mistral-7B on all five categories, matches/exceeds
  the human second annotator on the epileptiform categories, and sits 2.2 points below
  the human whole-report ceiling (89.8%).

## Per-category Core F1 (%) — pooled n=1994
| Model | Abnorm | Focal Epi | Gen Epi | Focal Non | Gen Non | Whole report |
|---|---|---|---|---|---|---|
| Mistral-7B | 94.7 | 82.8 | 74.8 | 75.6 | 75.2 | 74.5 |
| v3 | 95.6 | 82.7 | 87.0 | 87.5 | 85.7 | 84.2 |
| v5g Q2 | 95 | 88 | 90 | 89 | 87 | 87.6 |
| v5g Q4 | 96 | 86 | 89 | 89 | 89 | 87.6 |
| Human SG | 98.0 | 85.7 | 87.5 | 90.8 | 90.0 | 89.8 |

## Follow-up (next batch)
The remaining gap to human is **Abnormality + slowing**, not epileptiform. Addressed in
`../2026-08-07_abnormality-and-simplification/` (v7 body-aware abnormality; v8 simplified
prompt), all grammar-enforced, validated cross-annotator against SG.
