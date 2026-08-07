# Cross-annotator validation (are we overfitting to LD?)

We tune prompts against **LD** (reference annotator), so gains must be checked against
the **held-out second annotator SG**. Pooled n=1994; whole-report = all 5 labels match.
Reproduce: `python -m analysis.validate_vs_sg`.

| Variant | vs LD (tuned) | vs SG (held-out) |
|---|---|---|
| v1 | 83.9% | 82.9% |
| v3 | 84.2% | 82.4% |
| **v5g Q2** | 87.6% | 85.6% |
| **v5g Q4** | **87.6%** | **86.2%** |
| Human ceiling (SG vs LD) | — | **89.8%** |

## Conclusions
- **v5g generalizes.** It improves against **both** annotators (+~3 pts each), not only
  the one we tuned on — so the slowing discriminator + grammar are real improvements,
  not LD-specific fitting.
- **Near the human ceiling.** Two humans agree 89.8% (whole report). Our model agrees
  with LD 87.6% and with SG 86.2% — almost as close to each annotator as the annotators
  are to each other.
- **A caveat surfaced honestly:** v3 scores slightly *below* v1 vs SG despite beating it
  vs LD — a hint the v3 focal-epi exclusions were mildly LD-specific. v5g corrects this,
  improving vs both.
- **Implication:** beyond ~90% (the SG-vs-LD ceiling), chasing higher LD-scores would be
  fitting LD's idiosyncrasies, not improving the model. We are ~2–4 points from that
  ceiling; the remaining honest headroom is small.
