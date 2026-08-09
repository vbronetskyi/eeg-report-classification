# All prompts — the full comparison

Every prompt we tried for MedGemma-27B, and how it did. All numbers are **pooled over
1994 reports** (Zoe n=1495 + Maria n=499), **Core F1** and whole-report accuracy vs the
reference annotator **LD**, with the second annotator **SG** held out. Baselines: the
paper's **Mistral-7B** (Tian et al.) and the **human** second annotator (SG vs LD).

## The prompts

| Prompt | One line | What it changes |
|---|---|---|
| **v1** | Baseline | Impression-first, short definitions — the starting point |
| **v2** | Professor's revision | Neurologist role, read the report *body* first, extended ACNS/ILAE definitions |
| **v3** | Focal-epi exclusions | v1 + an explicit list of what does **not** count as focal epileptiform (raises precision) |
| **v4** | Procedure | v1 + a step-by-step detect → localize → assign routine |
| **v5** | Slowing discriminator | v3 + a focal-vs-generalized rule for **non-epileptiform slowing** |
| **v6** | Ask for consistency | v3 + a prompt instruction to self-check the overall/subtype agreement |
| **v7** | Body-aware abnormality | v5 + "call it abnormal if the body describes an abnormality the Impression downplays" |
| **v8** | Simplified | A deliberately short prompt (~340 tokens) — only the two decision boundaries |
| **v9** | Reasoning-first | Concise expert frame + a free-text `reasoning` field, letting the model deliberate |
| **v10** | Evidence calibration | v5 + "tie confidence to how explicitly the report supports each subtype" |

A **`…g`** suffix (e.g. **v5g**) means the variant is run with **grammar-enforced
consistency** (`ENFORCE_CONSISTENCY=1`): a GBNF grammar emits `overall_abnormal` last and
only lets it be abnormal when a subtype is, so a self-contradictory answer is impossible
to produce. Full prompt texts are in [`../prompts/`](../prompts/).

## Where every prompt lands

![Whole-report accuracy by prompt](figures/all_prompts_whole.png)

**What you see:** whole-report accuracy (all five labels correct) for each configuration,
from Mistral-7B up to the human agreement line (89.8%, dotted). Our baseline **v1 already
clears Mistral by ~10 points.** Adding grammar-enforced consistency is the big step
(**v3g/v5g**), and **v5g (87.6%)** is the best — within ~2 points of the human ceiling.
The rejected ideas cluster below it: **v8 (simplified)** even falls *below* the v1
baseline, because dropping the detailed rules brings the over-calling straight back.

## Our top prompts vs Mistral and human, per category

![Per-category F1 — top prompts vs Mistral and human](figures/all_prompts_bycat.png)

**What you see:** Core F1 per category for our three strongest prompts (**v5g**, **v3g**,
**v7g**), Mistral-7B, and the human annotator. Our prompts (blue / orange / violet)
**cluster tightly together and sit far above Mistral (grey)** on the harder three classes
(Gen Epi, Focal Non-epi, Gen Non-epi) — the gap to Mistral is 10–15 points there. Against
the **human (green)** the cluster lands right at the human level: **matching or beating
it on the epileptiform categories** (Focal Epi, Gen Epi) and trailing only on Abnormality
and the slowing classes — exactly where the two humans disagree most. That the three
prompts land so close to each other is itself the point: the result is stable across our
top variants, not a fluke of one prompt.

## Full numbers (pooled n=1994)

| Prompt | Abnorm | Focal Epi | Gen Epi | Focal Non | Gen Non | Whole vs LD | Whole vs SG |
|---|---|---|---|---|---|---|---|
| Mistral-7B | 94.7 | 82.8 | 74.8 | 75.6 | 75.2 | 74.5 | — |
| v1 | 96.8 | 80.4 | 88.5 | 88.0 | 84.0 | 83.9 | 82.9 |
| v3 | 95.6 | 82.7 | 87.0 | 87.5 | 85.7 | 84.2 | 82.4 |
| v3g | 95.9 | 86.4 | 89.2 | 86.9 | 89.6 | 86.5 | 86.0 |
| **v5g Q2** | 95.4 | **87.6** | **89.9** | 88.8 | 86.7 | **87.6** | 85.6 |
| **v5g Q4** | 96.0 | 85.6 | 88.8 | 89.0 | 89.3 | **87.6** | **86.2** |
| v7g | 96.2 | 86.0 | 87.8 | 87.4 | 90.0 | 87.1 | 86.1 |
| v8g | 93.9 | 76.9 | 85.4 | 85.8 | 87.7 | 83.6 | 82.8 |
| v10g | 96.1 | 86.9 | 87.8 | 87.4 | 89.8 | 86.7 | 86.1 |
| Human SG | 98.0 | 85.7 | 87.5 | 90.8 | 90.0 | 89.8 | — |

(v9g omitted from the pooled table — it is much slower and did not finish the full run;
on a fair same-case comparison it was 3–6 points **below** v5g. Values shown use Q4 for
the grammar variants except where a quant is named.)

## What worked, what didn't

- **Won:** the combination **v5 prompt + grammar-enforced consistency (v5g)**. The grammar
  is the single biggest lever — it removes every overall/subtype contradiction *and*, by
  letting the model decide the parts before the whole, lifts the epileptiform F1.
- **Rejected — asking instead of enforcing (v6):** the model doesn't hold the consistency
  rule on its own.
- **Rejected — body-aware abnormality (v7):** the remaining missed-abnormal cases are
  genuinely ambiguous, not a prompt gap.
- **Rejected — simplification (v8):** the detailed focal-epileptiform exclusions are
  load-bearing; removing them re-introduces over-calling.
- **Rejected — reasoning-first (v9):** given latitude to deliberate, the model's unaided
  judgement still under-performs the explicit rules by 3–6 points.
- **Rejected — evidence calibration (v10):** ~1 point below v5g on both quants; the
  "prefer absent" rule slightly hurt the rare Focal Epi class on Q2.

The improvement **holds against the held-out annotator SG** (82.9% → 86.2%), so it is a
real gain, not fitting to LD; the residual gap to the human is close to the level of
human–human disagreement, which is a reason to validate carefully rather than a claim that
nothing more is possible.

## Reproduce

```bash
pip install -e .
python -m analysis.make_tables         # the numbers tables
python -m analysis.plot_all_prompts    # the two charts above -> reports/figures/
python -m analysis.validate_vs_sg      # cross-annotator validation
```
Per-run job IDs and hypotheses: [`../experiments/`](../experiments/). Model: MedGemma-27B
GGUF (Q2_K / Q4_K_S), llama.cpp grammar-constrained, temperature 0, 64-core CPU.
