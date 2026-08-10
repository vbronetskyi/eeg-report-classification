Subject: EEG report classification — prompt results (short update)

Dear Professor Vakorin,

A short update on the EEG report classification work with MedGemma-27B. After a full
round of prompt experiments (10 variants, each on both datasets and both quantizations,
scored against annotator LD and validated against the held-out second annotator SG), the
best configuration — which I call **v5g** — reaches **87.6% whole-report accuracy** on the
pooled 1994 reports (Zoe + Maria). It **beats the paper's Mistral-7B on all five
categories**, matches or exceeds the human second annotator on the epileptiform
categories, and sits ~2 points below the human whole-report ceiling (89.8%). The gain also
holds against SG, so it reflects genuine generalization rather than fitting to LD.

**Why it works better than the earlier prompts — especially on focal epileptiform.**
The baseline *over-called* focal epileptiform: it caught almost every true case (recall
~98%) but produced too many false positives (precision ~68%), mostly by (a) mislabeling
*generalized* epileptiform discharges as focal, and (b) treating focal *slowing*
(non-epileptiform) as epileptiform. v5 adds two targeted things: an explicit list of what
does **not** count as focal epileptiform (exactly those two confusions), and a
focal-vs-generalized rule for slowing. This raises precision without losing recall,
lifting Focal-Epi F1 from **0.80 to 0.83–0.88** — from trailing Mistral to matching/beating
it. On top of that, grammar-enforced consistency (emitting the overall label last and
forbidding self-contradictory outputs, so the model commits the subtypes before the
overall call) removes inconsistent answers and further lifts the epileptiform scores. The
difference is sharpest at the exact confidence level: on focal epileptiform Mistral drops
to **0.41** certainty-F1 while v5g holds around **0.67–0.77**.

All prompt variants (browsable, one text file each):
https://github.com/vbronetskyi/eeg-report-classification/tree/main/prompts

The full comparison — tables, charts, and the tested-and-rejected ideas:
https://github.com/vbronetskyi/eeg-report-classification/blob/main/reports/all_prompts.md

Happy to walk through any of it.

Best regards,
Vladyslav
