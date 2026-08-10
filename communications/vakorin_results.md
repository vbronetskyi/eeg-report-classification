Subject: EEG report classification with MedGemma-27B — results update

Dear Professor Vakorin,

A short, structured update on the EEG report classification work.

## Bottom line

Across a full round of prompt experiments (10 variants, each on both datasets and both
quantizations, scored against annotator LD and validated against the held-out second
annotator SG), the best configuration — **v5g** — reaches **87.6% whole-report accuracy**
on the pooled 1994 reports (Zoe + Maria). It **beats the paper's Mistral-7B on all five
categories**, matches or exceeds the human second annotator on the epileptiform
categories, and sits ~2 points below the human whole-report ceiling (89.8%). The gain also
holds against SG, so it reflects genuine generalization rather than fitting to LD.

## What we changed to get there

Three targeted, annotator-agnostic changes — each aimed at a specific weakness we found by
error analysis:

1. **Focal-epileptiform exclusions (fixes Focal Epi).** The baseline *over-called* focal
   epileptiform: near-perfect recall (~98%) but low precision (~68%), because it (a)
   mislabeled *generalized* epileptiform discharges as focal, and (b) treated focal
   *slowing* as epileptiform. We added an explicit list of what does **not** count as focal
   epileptiform (exactly those two confusions, plus benign variants and artifacts). This
   raised precision without losing recall → **Focal-Epi F1 0.80 → 0.83–0.88**.

2. **Focal-vs-generalized rule for slowing (fixes the non-epileptiform classes).** The
   biggest overall error was confusing *focal* vs *diffuse* slowing (focal-non ↔
   generalized-non). We added a rule that assigns the distribution strictly from the report
   wording and forbids double-flagging one finding → **Focal-Non and Gen-Non both up several
   points**.

3. **Grammar-enforced consistency (fixes contradictions + lifts epileptiform).** We emit the
   overall label *last* and constrain the decoder so it can only be "abnormal" when a
   subtype is present — a self-contradictory answer becomes impossible. This removed every
   overall/subtype contradiction and, because the model now commits the subtypes before the
   overall call, **further lifted the epileptiform F1** as a side effect.

## Results (pooled n=1994, Core F1 vs LD)

| Category | Mistral-7B | **v5g (ours)** | Human (SG) |
|---|---|---|---|
| Abnormality | 0.95 | 0.95–0.96 | 0.98 |
| Focal Epi | 0.83 | **0.86–0.88** | 0.86 |
| Gen Epi | 0.75 | **0.89–0.90** | 0.88 |
| Focal Non-epi | 0.76 | **0.88–0.89** | 0.91 |
| Gen Non-epi | 0.75 | **0.87–0.89** | 0.90 |

The gap is largest at the **exact confidence level**: on focal epileptiform Mistral drops to
**0.41** certainty-F1 while v5g holds **0.67–0.77** — i.e. it captures not just the finding
but how sure to be about it.

## Also tested and rejected (for completeness)

Reading the report body harder for abnormality, a deliberately simplified prompt, a
reasoning-first prompt, and an evidence-calibration rule — none of these beat v5g, which is
itself a useful result.

## Links

- All prompt variants (browsable, one text file each):
  https://github.com/vbronetskyi/eeg-report-classification/tree/main/prompts
- Full comparison — tables, charts, and the tested-and-rejected ideas:
  https://github.com/vbronetskyi/eeg-report-classification/blob/main/reports/all_prompts.md

Happy to walk through any of it.

Best regards,
Vladyslav
