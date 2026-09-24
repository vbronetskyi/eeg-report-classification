# Background patterns — discontinuous, burst-suppression, suppressed

Three more fields the PI asked for, each labeled on its own: whether the report calls the EEG
background **discontinuous**, whether it describes **burst-suppression**, and whether it calls the
background **suppressed**. Same setup as the slowing work — MedGemma-27B (Q4_K_S), temperature 0,
Vasily's prompts, grammar-constrained so every answer is one of `present` / `explicitly_absent` /
`not_mentioned`. Run on Fraser Health (45,545 reports) and the three Harvard hospitals — MGH, BWH,
BCH (~101,600; BIDMC has no text).

Of the three, only burst-suppression has a matching column in the Harvard database (`bs`).
Discontinuous and suppressed background have no HEEDB variable, so there we only have our own
labels. For how we read Harvard's values, see the companion note `reports/harvard_llm_labeling.md`.

## How often each is called present

![Present rate across datasets](figures/background_prevalence.png)

All three are uncommon, as expected — these are ICU / anesthesia patterns, not routine findings.

| present rate | FHA | MGH | BWH | BCH |
|---|---|---|---|---|
| discontinuous | 0.1% | 2.6% | 3.4% | 7.5% |
| burst-suppression | 1.1% | 3.5% | 3.0% | 1.3% |
| suppressed | 1.0% | 1.4% | 2.9% | 0.9% |

The one that stands out is **discontinuous**. On Fraser Health almost no report addresses
continuity at all (0.1% present, 98% not mentioned), while the Harvard reports discuss it far more
often — and not just as present: they very often state the background *is* continuous. Explicit
"continuous / not discontinuous" statements run to 17% at MGH, 25% at BWH and 63% at BCH, versus
under 2% on Fraser Health. That's a reporting-style difference between the cohorts (Harvard's
ICU/EMU reports routinely comment on continuity), not a disagreement about any one recording.

## Burst-suppression vs Harvard's `bs`

![Burst-suppression: ours vs Harvard](figures/background_burst.png)

| | agreement | κ | κ (text only) | our recall on verified |
|---|---|---|---|---|
| MGH | 92% | 0.44 | 0.60 | 65% (231) |
| BWH | 89% | 0.32 | 0.50 | 61% (184) |
| BCH | 93% | 0.25 | 0.29 | — (0 verified) |

Two things to read here. Raw agreement looks high (89–93%), but that mostly reflects how rare the
finding is — both sides say "no" on almost every report, so they agree by default; κ (agreement
above chance) is the honest number, and it's fair-to-moderate.

The bigger point is the gap in the chart: **Harvard's `bs` is marked far more often than we mark
it** — 11% of MGH reports, 14% at BWH, against our 1–3.5%. At MGH and BWH that is not the report
narratives disagreeing with us; it's their annotation channel. When we compare only against the
labels Harvard took from the report *text* (`report` provenance), κ jumps to 0.60 at MGH and 0.50
at BWH. So most of the extra Harvard `bs` there comes from the recording's structured annotations,
which flag burst-suppression on many recordings whose written report doesn't describe it — and
which we, reading only the text, never see. BCH is the exception: its `bs` is mostly text-derived
already, so the text-only κ barely moves (0.25 → 0.29) and the gap there (8.5% vs our 1.3%) is a
real under-call on the reports themselves.

On the reports an expert had verified as burst-suppression, we catch about 61–65%. Part of the
miss is the same channel issue (some verified labels are annotation-derived and not in the text),
so this is a floor rather than a clean recall.

## Discontinuous and suppressed background

There's no Harvard column for either, so these are our labels only, no comparison:

| | present | explicitly_absent | not_mentioned |
|---|---|---|---|
| discontinuous — FHA | 0.1% | 1.8% | 98.1% |
| discontinuous — Harvard (MGH/BWH/BCH) | 2.6–7.5% | 17–63% | 30–80% |
| suppressed — FHA | 1.0% | 1.7% | 97.4% |
| suppressed — Harvard | 0.9–2.9% | 0.1–0.7% | 97–99% |

Suppressed background behaves like a normal rare finding across both datasets. Discontinuous, as
noted, is the one the Harvard reports actively comment on far more than Fraser Health's do.

## Caveats

- About 1.3% of Harvard reports are too long for the context window and returned no label; they're
  left out of the counts.
- Only burst-suppression can be compared against Harvard; discontinuous and suppressed have no
  HEEDB variable (nearest is `low voltage`, a different thing).
- The verified check is positives-only (no verified "absent") and has no BCH data.

## Reproduce

```bash
# labeling (on the cluster)
bash slurm/submit_background.sh                 # Fraser Health, all three fields
bash slurm/submit_background_harvard.sh         # MGH / BWH / BCH, all three fields
# distributions, comparison, charts
python -m analysis.background_dist              # results/background/dist_summary.json
python -m analysis.background_vs_harvard        # results/harvard/burst_vs_harvard.json
python -m analysis.background_chart             # the two figures
```
