Subject: EEG report classification — updated results and a refined prompt (v3)

Dear Professor,

I hope you're doing well. I've finished a full round of prompt experiments for the
EEG report classification work with MedGemma-27B and wanted to share where things
stand.

Short version: building on your revised prompt, I found a version (I'm calling it v3)
that closes the one remaining gap against the paper's Mistral-7B baseline without
giving up any of our existing strengths. It is now my recommended configuration.

**What I tested.** Four prompt variants, each on both datasets (Zoe, n=1495, and
Maria, n=499) and both quantizations (Q2_K ~10 GB, Q4_K_S ~15 GB) — 16 runs over
1994 reports in total, scored against annotator LD:

- **v1** — the original baseline prompt.
- **v2** — your revision (neurologist role, read the report body first, keep body
  findings when the Impression is conservative, extended ACNS/ILAE definitions).
- **v3** — v1 plus explicit "what does *not* count as focal epileptiform" exclusions.
- **v4** — v1 plus a step-by-step detect → localize → assign procedure.

**Main findings.**

- Your **v2** prompt helps exactly where you intended: on Maria it lifts the overall
  abnormal-vs-normal call to near-human (0.92 → 0.97). Its one cost is the rare
  **focal epileptiform** class, which it over-calls (F1 drops to 0.64) — reading the
  body more aggressively produces more false positives on that precision-limited class.
- The only category where we still trailed Mistral was focal epileptiform. **v3**
  targets exactly that: by spelling out what should *not* be counted (generalized
  discharges, benign variants, artifacts, focal slowing), it raises precision while
  keeping recall, and focal epileptiform goes **0.80 → 0.83** — matching Mistral, and
  on Maria beating it (0.90 vs 0.81).
- Net effect: **v3 is the best of all 16 runs — 1679 / 1994 reports fully correct**
  (all five labels), vs 1672 for v1 and 1485 for Mistral. We now beat Mistral on four
  of five categories and match it on the fifth. The smaller Q2_K quantization is
  enough; the larger Q4_K_S gives no whole-report benefit on the stronger prompts.

**Recommended setup:** prompt **v3 + Q2_K**.

Attached:

- `prompt_v3.txt` — the full v3 prompt (system + user message), exactly as sent to
  the model;
- `results_prompt_variants.pdf` — the four-variant comparison, with all the numbers
  (per category, per dataset, vs Mistral and vs the human second annotator) and charts;
- `results_baseline.pdf` — the earlier v1 vs v2 comparison (your prompt), including
  generalization to Maria and the over/under-calling analysis.

I'd be glad to walk through any of it, or to keep pushing the focal-epileptiform
handling further if you'd like to try to beat Mistral on that last class too.

Best regards,
Vladyslav
