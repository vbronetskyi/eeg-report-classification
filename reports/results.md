# Results — EEG report classification with MedGemma-27B

Classifying free-text clinical EEG reports into five diagnostic labels (overall
abnormality; focal/generalized epileptiform; focal/generalized non-epileptiform) with a
quantized, CPU-run, grammar-constrained **MedGemma-27B**. All numbers are **pooled over
1994 reports** (Zoe n=1495 in-distribution + Maria n=499 out-of-distribution), scored as
**Core F1** and whole-report accuracy against reference annotator **LD**, with the second
annotator **SG** held out for validation. External baseline: the paper's **Mistral-7B**
(Tian et al., Table III).

## Headline

Our best configuration — **v5g** (prompt v5 + grammar-enforced consistency) — reaches
**1746/1994 = 87.6%** whole-report accuracy. It **beats Mistral-7B on all five
categories**, **matches or exceeds the human second annotator on the epileptiform
categories**, and the improvement **holds against the held-out annotator SG**, so it is a
genuine gain rather than fitting to LD.

| Model | Abnorm | Focal Epi | Gen Epi | Focal Non | Gen Non | **Whole vs LD** | Whole vs SG |
|---|---|---|---|---|---|---|---|
| Mistral-7B (paper) | 94.7 | 82.8 | 74.8 | 75.6 | 75.2 | 74.5 | — |
| v1 (our start) | 96.8 | 80.4 | 88.5 | 88.0 | 84.0 | 83.9 | 82.9 |
| v3 (focal-epi exclusions) | 95.6 | 82.7 | 87.0 | 87.5 | 85.7 | 84.2 | 82.4 |
| **v5g Q2 — best** | 95.4 | **87.6** | **89.9** | 88.8 | 86.7 | **87.6** | 85.6 |
| **v5g Q4 — best** | 96.0 | 85.6 | 88.8 | 89.0 | 89.3 | **87.6** | **86.2** |
| v7g Q4 | 96.2 | 86.0 | 87.8 | 87.4 | 90.0 | 87.1 | 86.1 |
| v8g Q4 | 93.9 | 76.9 | 85.4 | 85.8 | 87.7 | 83.6 | 82.8 |
| Human SG (annotator agreement) | 98.0 | 85.7 | 87.5 | 90.8 | 90.0 | **89.8** | — |

Per-category values are Core F1 (%). "Whole" = % of reports with all five labels correct.

## What each idea tested, and how it turned out

We explored the prompt space systematically — each variant isolates one idea, so its
effect is attributable. The single biggest lever was **grammar-enforced consistency**;
several plausible ideas were tested and rejected.

| Variant | Idea | Outcome |
|---|---|---|
| v1 | Baseline (Impression-first) | 83.9% — already beats Mistral on 4/5 |
| v2 | Professor's revision (body-first, extended defs) | Helps Maria abnormality, but over-calls Focal Epi → weaker overall |
| v3 | + explicit focal-epileptiform exclusions | Fixes Focal Epi precision (kept) |
| v4 | + detect→localize procedure | ≈ v3, marginally worse (superseded) |
| v5 | v3 + focal-vs-generalized *slowing* discriminator | Helps the slowing classes — but on its own introduces inconsistency |
| v6 | Ask the model (in the prompt) to self-check consistency | **Rejected** — asking does not hold; even hurt other fields |
| **v3g** | v3 + **grammar-enforced** consistency | +2 pts and 0 contradictions; also lifts epileptiform F1 |
| **v5g** | v5 + grammar-enforced consistency | **Best: 87.6%** — the slowing gains without the inconsistency |
| v7g | v5g + body-aware abnormality | **Rejected** — did not close the Abnormality gap |
| v8g | Deliberately simplified prompt | **Rejected** — regresses on Focal Epi (the exclusions are load-bearing) |
| v9g | Reasoning-first ("let the model decide") | **Rejected** — 3–6 pts *worse* than v5g, and much slower |
| v10g | v5 + evidence-calibration rule | Neutral / slightly worse than v5g (preliminary) |

### The decisive lever: grammar-enforced consistency
The schema requires that the overall label agrees with the subtypes (abnormal iff at
least one subtype is present). The model violated this in ~34–114 reports. **Asking** it
to self-correct (v6) did not reliably work. Emitting the labels under a GBNF grammar that
places `overall_abnormal` **last** and only permits it to be abnormal when a subtype is —
so a contradiction is *undecodable* — fixed every violation for free, and, by letting the
model commit the subtypes before the whole, also **raised the epileptiform-category F1**.

### What did *not* help
- **Asking for consistency (v6)** instead of enforcing it — the model doesn't hold the
  rule on its own.
- **Reading the body harder for abnormality (v7)** — the remaining missed-abnormal cases
  are genuinely ambiguous (annotators disagree there too), not a prompt gap.
- **Simplifying the prompt (v8)** — dropping the detailed focal-epileptiform exclusions
  brings the over-calling straight back.
- **Giving the model reasoning latitude (v9)** — with room to deliberate, its unaided
  judgement still under-performs the explicit clinical rules by 3–6 points.

## Cross-annotator validation

We tune against LD, so a real improvement must also raise agreement with the held-out
second annotator SG. It does: whole-report agreement vs SG rises **82.9% (v1) → 86.2%
(v5g)**, tracking the vs-LD gain — the improvement generalizes across annotators, not just
to LD. For reference, the two human annotators agree with each other **89.8%** (SG vs LD);
our model agrees with each of them almost as well (LD 87.6%, SG 86.2%). The remaining
2–4-point gap is close to the level of human–human disagreement, so further prompt-only
gains measured against LD should be treated with caution — beyond that band, higher
LD-scores may reflect LD's idiosyncrasies rather than better classification. That is a
reason for careful validation, not a claim that no improvement is possible.

## Recommendation

Ship **v5g** — prompt v5 + `ENFORCE_CONSISTENCY=1`. Use **Q2_K** for size (half the
footprint, best epileptiform F1) or **Q4_K_S** if diffuse (Gen Non-epi) findings are
prioritized. Both give the same 87.6% whole-report accuracy.

## Reproduce

```bash
pip install -e .
python -m analysis.make_tables         # the metric tables
python -m analysis.validate_vs_sg      # cross-annotator (vs SG) validation
python -m analysis.plot_v34            # comparison charts -> reports/figures/
```
Full per-run detail, job IDs, and hypotheses are in [`../experiments/`](../experiments/).
Model: MedGemma-27B GGUF (Q2_K / Q4_K_S), llama.cpp grammar-constrained, temperature 0,
64-core CPU.
