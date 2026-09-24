# Focal and generalized slowing — MedGemma labels, and a look against Harvard's

We labeled each report for two things, separately: focal slowing and generalized slowing. Each
gets one of three calls — present, explicitly absent, or not mentioned. This ran on Fraser Health
(45,545 reports) and on three Harvard hospitals, MGH, BWH and BCH (about 101,600 reports; BIDMC
has no text we can read). The model is MedGemma-27B (Q4_K_S) at temperature 0, reading each report
with the definitions Vasily wrote; the output is grammar-constrained, so every answer comes back
as one clean status.

## Fraser Health

There's nothing to compare against here — Fraser Health has no slowing labels of its own — so this
is just what the model found:

| | present | explicitly_absent | not_mentioned |
|---|---|---|---|
| focal slowing | 25.6% | 24.5% | 50.0% |
| generalized slowing | 23.0% | 40.2% | 36.8% |

All three answers get used, which is what we want to see.

## Harvard

Harvard has its own `foc slowing` and `gen slowing` for every report, so here we can line the two
up. Their column is a single mark, present or blank, and blank covers both "the report says no" and
"nobody wrote anything" — so we fold our side down to present-or-not to match. Their mark also
records where it came from: the report text, a separate annotation, or an expert check. That last
part lets us do a bit more than compare two models to each other.

Taking everything they marked:

![Present rate, our labels vs Harvard's](figures/slowing_vs_harvard.png)

| | agreement | κ | we call present | they call present |
|---|---|---|---|---|
| focal — MGH | 77% | 0.40 | 34.5% | 14.1% |
| focal — BWH | 70% | 0.41 | 50.6% | 23.3% |
| focal — BCH | 87% | 0.43 | 17.7% | 7.4% |
| generalized — MGH | 74% | 0.40 | 60.6% | 77.2% |
| generalized — BWH | 65% | 0.30 | 50.5% | 72.2% |
| generalized — BCH | 84% | 0.60 | 30.6% | 27.4% |

Agreement is how often the two give the same present/not call; κ is the same thing after taking
out what you'd get by chance (0 is chance, 1 is perfect). It lands around 0.4–0.5. The gap runs
the same way every time: we call focal slowing about twice as often as they do, and
they call generalized more often than we do, most of all at MGH and BWH. BCH matches best.

We only read the report text, so the cleaner comparison is against the labels they also took from
the text, setting aside the ones that came only from annotations. Most of their labels (roughly
80–94%) are from the text anyway, so this barely moves focal — but for generalized it closes a
good part of the gap:

| | κ vs everything | κ vs text only |
|---|---|---|
| focal — MGH / BWH / BCH | 0.40 / 0.41 / 0.43 | 0.37 / 0.39 / 0.42 |
| generalized — MGH / BWH / BCH | 0.40 / 0.30 / 0.60 | 0.47 / 0.37 / 0.66 |

So some of what looked like us missing generalized slowing was really their annotations for things
the report never actually says.

The expert-checked labels are the closest thing to a right answer we have. They only exist for
present cases (there's no verified "absent"), and none at BCH, so they answer one question: when an
expert confirmed slowing, did we catch it?

![Recall on expert-verified reports](figures/slowing_recall_verified.png)

| | our recall | verified reports |
|---|---|---|
| focal — MGH | 87% | 1,480 |
| focal — BWH | 92% | 413 |
| generalized — MGH | 71% | 3,743 |
| generalized — BWH | 78% | 1,243 |

For focal we catch about nine in ten. For generalized we miss roughly a quarter, so our lower
generalized numbers aren't only a labeling difference — we do miss some real ones. This only tells
us about reports that truly have slowing; it can't say how often we call slowing that isn't there.

The verified set can't score Harvard's own model, since those labels are theirs to begin with.
Checking both models properly would need a small set hand-labeled from scratch, negatives included
— easy to set up if it's worth doing.

## Caveats

- About 1.4% of Harvard reports are too long for the context window and returned no label; they're
  left out of the counts.
- We compare our "present" against their "marked". Our side also separates "the report says absent"
  from "not mentioned", which their column can't.

## Reproduce

```bash
# labeling (on the cluster)
bash slurm/submit_slowing.sh                 # Fraser Health, both fields
bash slurm/submit_slowing_harvard.sh         # MGH / BWH / BCH, both fields
# comparison + charts
python -m analysis.slowing_vs_harvard        # writes results/harvard/slowing_gold.json
python -m analysis.slowing_chart             # writes the two figures
```
