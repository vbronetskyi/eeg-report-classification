# Prompt variants

Every prompt variant tried for EEG report classification with MedGemma-27B, as plain text —
**exactly as sent to the model**. Each file contains the **system message** and the
**user prompt**.

| Variant | What it is | Text |
|---|---|---|
| **v1** | Baseline — Impression-first, short definitions | [v1.txt](v1.txt) |
| **v2** | Neurologist role, read the report *body* first, extended ACNS/ILAE definitions | [v2.txt](v2.txt) |
| **v3** | v1 + explicit **focal-epileptiform exclusions** (raises precision) | [v3.txt](v3.txt) |
| **v4** | v1 + a step-by-step **detect → localize → assign** procedure | [v4.txt](v4.txt) |
| **v5** | v3 + a **focal-vs-generalized** rule for non-epileptiform slowing | [v5.txt](v5.txt) |
| **v6** | v3 + a prompt instruction asking the model to self-check consistency | [v6.txt](v6.txt) |
| **v7** | v5 + **body-aware abnormality** (call it abnormal on a body finding the Impression downplays) | [v7.txt](v7.txt) |
| **v8** | Deliberately **simplified** (~340 tokens) — only the two decision boundaries | [v8.txt](v8.txt) |
| **v9** | **Reasoning-first** — a free-text `reasoning` field before the labels | [v9.txt](v9.txt) |
| **v10** | v5 + **evidence-calibration** rule | [v10.txt](v10.txt) |

## The `…g` (grammar) suffix

Any variant can be run with **`ENFORCE_CONSISTENCY=1`** (then tagged e.g. **v5g**): a GBNF
grammar emits `overall_abnormal` last and only permits it to be *abnormal* when at least one
subtype is present, so a self-contradictory answer is impossible to decode. This is a
**decoding constraint, not part of the prompt text** — so the `.txt` here is identical with
or without it.

## Best configuration

**v5g** = the [v5](v5.txt) prompt + grammar-enforced consistency. The full comparison,
results and charts: **[../reports/all_prompts.md](../reports/all_prompts.md)**.

## Reproducibility

These text files are generated from the single source of truth
([../src/core/prompt.py](../src/core/prompt.py)) — regenerate with:

```bash
python prompts/export_prompts.py
```
