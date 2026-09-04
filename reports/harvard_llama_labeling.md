# Harvard's report labeling — MGH & BWH results

This looks at the label files the Harvard team produced from their EEG reports, for the two
large adult academic hospitals: **MGH** (Massachusetts General) and **BWH** (Brigham &
Women's). The goal here is to understand *how they labeled* and *how much to trust each
label* before we compare anything to our own work.

The files:

```
harvard_llama_results/MGH_EEG_with_reports.csv    90,716 studies
harvard_llama_results/BWH_EEG_with_reports.csv    39,115 studies
```

Same data lives in `HarvardEEG.db` (tables `MGH_EEG_with_reports`, `BWH_EEG_with_reports`)
and in the public repo [bdsp-core/Harvard-EEG-Database-Tools](https://github.com/bdsp-core/Harvard-EEG-Database-Tools).
Our copy is at commit `78034f1` (24 Nov 2025), which is the latest upstream — it is current.

## How they labeled the reports

From the HEEDB paper and the repo, the labels come from **three sources combined**: expert
curation, regular expressions, and a medical language model. Concretely:

1. Each EDF recording is aligned to its clinical report by timestamp.
2. A **medical LLM (Bio-Medical-Llama-3-8B)** is asked a **yes/no question per finding**
   ("Does the patient have any seizure events noted? Answer Yes or No"), run locally so no
   PHI leaves the hospital. This is very close to our own yes/no, grammar-constrained setup.
3. Structured EEG annotations (XLTEK / Persyst markers) contribute labels too.
4. Some labels are additionally checked by a human.

So a finding label can come from the report text (the LLM), from the machine annotations, or
both, and may or may not be verified. **That source is recorded in the cell itself** — which
is the most useful thing in these files.

## How to read a label (this is the important part)

A finding column is empty when the finding is absent, or holds a short string saying **where
the label came from and whether it was checked**:

| Value | Meaning | MGH | BWH |
|---|---|---|---|
| `report` | from the report text (the LLM) only | 68.2% | 63.1% |
| `report annotation` | in **both** the report and the machine annotation | 21.0% | 19.2% |
| `annotation` | from the machine annotation only (not found in the report) | 7.4% | 14.4% |
| `report annotation verified` | both sources **and** human-verified | 1.6% | 1.4% |
| `report verified` | report + verified | 0.7% | 0.8% |
| `verified` | verified, other | 0.7% | 0.6% |
| `annotation verified` | annotation + verified | 0.5% | 0.5% |

*(Percent of all present labels: 616,974 for MGH, 283,415 for BWH.)*

Rolled up by source:

| | from report (LLM) | cross-confirmed (report + annotation) | annotation only | human-verified |
|---|---|---|---|---|
| **MGH** | 69% | 23% | 8% | 3.5% |
| **BWH** | 64% | 21% | 15% | 3.4% |

## What this says about their labeling

- **Most labels are the LLM reading the report** — about two thirds come from the report
  text alone. Their pipeline is, at its core, an LLM report-classifier like ours.
- **Roughly a fifth are cross-confirmed** — the LLM's reading of the report and the
  independent machine annotations agree. These are the high-confidence labels.
- **A meaningful slice is annotation-only** (8% at MGH, 15% at BWH): the finding was marked
  in the EEG software but the LLM did not pull it from the report narrative. This is the
  gap to watch — it is either findings the report never mentioned, or things the LLM missed.
  BWH has almost twice MGH's share here.
- **Human verification is small — about 3.4–3.5%.** The vast majority of labels are never
  checked by a person, so the `verified` tag is the exception, not the rule.
- **They do not publish a per-finding accuracy.** The paper reports linkage coverage (73% of
  EEGs linked to a report, 96% of those matched to a recording) but no inter-rater or LLM
  accuracy numbers. In practice, the provenance tag *is* their confidence signal — a
  `report annotation verified` label is worth far more than a bare `annotation`.

## What was actually found (prevalence)

Share of studies where each finding is marked present. This is a referral / epilepsy-monitoring /
ICU population, so it skews heavily abnormal — not a general-population rate.

| Finding | MGH | BWH |
|---|---|---|
| normal | 27.0% | 29.6% |
| abnormal | 72.8% | 69.9% |
| pdr (background rhythm) | 58.3% | 49.7% |
| foc slowing | 15.8% | 29.3% |
| gen slowing | 77.7% | 73.0% |
| spikes | 79.1% | 77.1% |
| seizure | 29.7% | 45.5% |
| status epilepticus | 8.7% | 8.7% |
| lpd | 7.4% | 16.6% |
| gpd | 7.3% | 14.5% |
| lrda | 2.7% | 10.5% |
| grda | 9.2% | 17.4% |
| low voltage | 4.8% | 2.4% |
| uninterpretable | 1.7% | 0.8% |

BWH runs noticeably more seizure, focal slowing and periodic/rhythmic patterns
(lpd/gpd/lrda/grda) than MGH — a heavier ICU/monitoring mix.

## Who is in these files

| | Studies | Patients | Population | Median age | Female / Male | Recording dates |
|---|---|---|---|---|---|---|
| MGH | 90,716 | 34,620 | adult | 52 | 48% / 52% | 2004–2024 |
| BWH | 39,115 | 14,923 | adult | 60 | 51% / 49% | 2008–2024 |

## Caveats

- **No free-text report** is included — only the extracted labels. We can't re-run our
  classifier on these reports.
- **Duplicate rows per report.** The same report file (`DeidentifiedName(Reports)`) can
  appear several times with tiny differences, so the study count is above the number of
  unique reports.
- **No published label accuracy**, so any trust comes from the provenance tag, not a reported
  metric.

## Sources

- Sun C. et al. *Harvard Electroencephalography Database: A comprehensive clinical
  electroencephalographic resource from four Boston hospitals.* Epilepsia, 2025.
  [doi:10.1111/epi.18487](https://doi.org/10.1111/epi.18487) — 280,000+ recordings, 108,000+
  patients, 4 hospitals; findings via expert curation, regex, and medical NLP; 73% of EEGs
  linked to reports, 96% of those matched to recordings.
- Repo and label files: [bdsp-core/Harvard-EEG-Database-Tools](https://github.com/bdsp-core/Harvard-EEG-Database-Tools).
