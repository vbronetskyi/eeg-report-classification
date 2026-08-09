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

**What you see:** Core F1 for **each label scored on its own**, for our three strongest
prompts (**v5g**, **v3g**, **v7g**), Mistral-7B, and the human annotator. Note these are a
*different metric* from the first chart: the first chart's 87.6% is the share of reports
with **all five** labels correct at once; here each number is the F1 of **one** label —
so the two are not meant to match. Our prompts (blue / orange / violet)
**cluster tightly together and sit far above Mistral (grey)** on the harder three classes
(Gen Epi, Focal Non-epi, Gen Non-epi) — the gap to Mistral is 10–15 points there. Against
the **human (green)** the cluster lands right at the human level: **matching or beating
it on the epileptiform categories** (Focal Epi, Gen Epi) and trailing only on Abnormality
and the slowing classes — exactly where the two humans disagree most. That the three
prompts land so close to each other is itself the point: the result is stable across our
top variants, not a fluke of one prompt.

## Why we win — confidence, not just direction

![v5g vs Mistral — core vs certainty](figures/all_prompts_v5g_vs_mistral.png)

**What you see:** each line runs from **Core F1** (● — did we get present/absent right?)
to **Certainty F1** (○ — did we get the *exact* 1–4 confidence level?); the line length
is how much is lost when the exact level is required. Our **v5g (blue)** beats Mistral on
core almost everywhere, but the real separation is the **exact level**: Mistral's open
circles collapse (Focal Epi 83 → **41**, Focal Non-epi 76 → 45, Gen Non-epi 75 → 52) — it
points in the right direction but badly misjudges *how sure* to be — while v5g holds far
better (Focal Epi 86 → 67, Focal Non-epi 89 → 63). Getting the confidence level right, not
just the yes/no, is where our prompt+grammar approach pulls ahead.

## Which quantization, and does it generalize?

![Q2 vs Q4 per category](figures/all_prompts_q2_vs_q4.png)

**What you see:** v5g on the two model sizes. They tie on whole-report accuracy (87.6%
each); per category **Q2_K** is stronger on the epileptiform classes (Focal Epi 88 vs 86)
while **Q4_K_S** is stronger on the diffuse/slowing classes (Gen Non-epi 89 vs 87). Pick
Q2_K for half the footprint, Q4_K_S if encephalopathy/diffuse findings matter most.

![Generalization — Zoe vs Maria](figures/all_prompts_generalization.png)

**What you see:** the same model on the **seen** neurologist (Zoe) and an **unseen** one
(Maria). Performance holds across reporting styles — the epileptiform and focal classes are
as strong or stronger on the unseen data — so the model generalizes rather than fitting one
annotator's phrasing.

## How the metrics work (read before the tables)

Every label is scored on the **1–4 scale** (1 confident-no · 2 low-no · 3 low-yes ·
4 confident-yes). Two independent choices define each number.

**1. Strictness — Core vs Exact**
- **Core** — collapse to yes/no (1–2 = absent, 3–4 = present) and check the *side* only.
  "3 vs 4" counts as correct (both mean present).
- **Exact** — the exact 1–4 must match. "3 vs 4" is wrong (right direction, wrong
  confidence). Always the harder test.

**2. Scoring — Accuracy vs F1.** For one label, every report falls into four outcomes:
TP (said present, is present), FP (said present, isn't), FN (said absent, is present),
TN (said absent, isn't). The two scores use these differently:

- **Accuracy** = (TP + TN) / all — counts everything, *including the easy true-negatives*.
- **F1** = 2·TP / (2·TP + FP + FN) — *ignores TN*; measures only how well the positive
  ("present") class is caught, balancing precision and recall.

The gap between them comes entirely from TN. On a **rare** class (Focal/Gen Epi ~5%
present) there are ~1900 easy TN, so accuracy is inflated (~98%) while F1 stays honest
(~80%). On a **balanced** class (Abnormality ~50/50) TN doesn't dominate, so the two
nearly coincide (~95%). **This is why the charts use F1** — it doesn't reward the trivial
"say absent" on rare findings.

**Whole-report (All-5)** = the share of reports where *all five* labels are correct — one
intuitive number (this is what the first chart and the "All-5" column show).

*The charts use Core F1 (and Certainty F1 for the exact level); the whole-report chart
uses All-5 accuracy. The tables below give both F1 and the plain "% correct" (accuracy).*

## Full numbers (pooled n=1994)

Per-category values are **Core F1**; "Whole" is **All-5 accuracy** (share of reports with
all five labels correct), vs LD and vs the held-out annotator SG.

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

## Accuracy view — % guessed correctly (core & exact)

The charts above use **F1** (the paper's metric, best for imbalanced classes). If you
prefer plain **accuracy** (correct ÷ all), here it is, in the two levels from the dumbbell
charts. The **All-5** column of the *core* table is exactly the whole-report % from the
first chart (e.g. v5g = 87.6%).

> Caveat: per-category accuracy looks very high on the **rare** classes (Focal Epi ~98%)
> simply because "absent" is the right answer most of the time — that inflation is why the
> charts use F1, which exposes the over-calling. Accuracy is most meaningful on the common
> classes (Abnormality, Focal/Gen Non-epi) and on the **All-5** column.

**Core accuracy — % present/absent correct (1–2 vs 3–4):**

| Model | Abnorm | Focal Epi | Gen Epi | Focal Non | Gen Non | All-5 |
|---|---|---|---|---|---|---|
| Mistral-7B | 95.0 | 98.3 | 97.3 | 86.2 | 89.7 | 74.5 |
| v1 | 97.0 | 97.8 | 98.9 | 93.1 | 92.3 | 83.9 |
| v3 | 95.9 | 98.2 | 98.7 | 93.1 | 93.2 | 84.2 |
| v3g (Q4) | 96.0 | 98.6 | 98.9 | 92.2 | 94.9 | 86.5 |
| **v5g (Q2)** | 95.6 | 98.8 | 99.0 | 93.7 | 94.0 | **87.6** |
| **v5g (Q4)** | 96.1 | 98.5 | 98.9 | 93.5 | 94.8 | **87.6** |
| v7g (Q4) | 96.3 | 98.6 | 98.8 | 92.5 | 95.2 | 87.1 |
| v8g (Q4) | 93.8 | 97.3 | 98.5 | 91.2 | 93.8 | 83.6 |
| v10g (Q4) | 96.2 | 98.7 | 98.8 | 92.5 | 95.0 | 86.7 |
| Human (SG) | 98.0 | 98.6 | 98.9 | 94.7 | 95.3 | 89.8 |

**Exact accuracy — % exact 1–4 level correct:**

| Model | Abnorm | Focal Epi | Gen Epi | Focal Non | Gen Non | All-5 |
|---|---|---|---|---|---|---|
| Mistral-7B | 76.2 | 71.9 | 94.9 | 64.9 | 80.5 | 40.7 |
| v1 | 72.6 | 96.9 | 98.1 | 77.8 | 82.4 | 56.8 |
| v3 | 74.1 | 97.3 | 97.9 | 79.6 | 83.2 | 59.1 |
| v3g (Q4) | 82.3 | 96.8 | 98.0 | 80.9 | 85.9 | 66.8 |
| **v5g (Q2)** | 75.6 | 97.3 | 98.2 | 82.2 | 84.7 | 66.5 |
| **v5g (Q4)** | 81.6 | 96.9 | 97.8 | 82.6 | 86.4 | 67.9 |
| v7g (Q4) | 83.2 | 96.5 | 97.9 | 82.4 | 87.1 | 69.9 |
| v8g (Q4) | 74.4 | 92.1 | 97.4 | 77.7 | 84.0 | 61.1 |
| v10g (Q4) | 81.6 | 96.7 | 98.0 | 81.4 | 86.9 | 67.5 |
| Human (SG) | 89.3 | 97.4 | 98.5 | 79.2 | 85.5 | 65.9 |

The **exact** table is where our approach separates from Mistral: on the exact confidence
level Mistral drops sharply (Focal Epi 72%, Focal Non-epi 65%) while our grammar prompts
hold in the 80–97% range — and on whole-report exact accuracy (All-5) v5g/v7g even edge
past the human annotator, whose SG-vs-LD exact agreement is 65.9%.

Regenerate: `python -m analysis.accuracy_tables`.

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

## Per-prompt detail — core vs certainty, Q2 vs Q4

One chart per prompt, each overlaying both quantizations. The **filled dot** is Core F1
(present/absent), the **open circle** is strict Certainty F1 (exact 1–4 level); the line
length is the drop when the exact level is required. All pooled over 1994 reports.

**v5g (best):**

![v5g core vs certainty](figures/dumbbell_v5g.png)

**v3g:**

![v3g core vs certainty](figures/dumbbell_v3g.png)

**v7g:**

![v7g core vs certainty](figures/dumbbell_v7g.png)

**v8g (simplified):**

![v8g core vs certainty](figures/dumbbell_v8g.png)

**v10g (calibrated):**

![v10g core vs certainty](figures/dumbbell_v10g.png)

**Mistral-7B (reference):**

![Mistral core vs certainty](figures/dumbbell_mistral.png)

## Reproduce

```bash
pip install -e .
python -m analysis.make_tables         # the numbers tables
python -m analysis.plot_all_prompts    # every chart in this report -> reports/figures/
python -m analysis.validate_vs_sg      # cross-annotator validation
```
Per-run job IDs and hypotheses: [`../experiments/`](../experiments/). Model: MedGemma-27B
GGUF (Q2_K / Q4_K_S), llama.cpp grammar-constrained, temperature 0, 64-core CPU.
