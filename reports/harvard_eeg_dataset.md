# Harvard EEG Database — the four report tables

This describes the four hospital tables in the Harvard EEG Database (HEEDB),
`/project/6019337/databases/eeg_harvard/HarvardEEG.db`:
`MGH_EEG_with_reports`, `BWH_EEG_with_reports`, `BCH_EEG_with_reports`,
`BIDMC_EEG_with_reports`. Each row is one EEG study with the findings that were pulled
out of its clinical report. The four tables come from four Boston hospitals in the
Mass General Brigham system.

## What's in it

**177,237 EEG studies** across the four sites, from roughly **67,500 patients**, recorded
**2004–2025**.

| Site | Full name | Rows (studies) | Patients | Population | Median age | Female / Male |
|---|---|---|---|---|---|---|
| MGH | Massachusetts General | 90,716 | 34,620 | adult | 52 | 48% / 52% |
| BWH | Brigham & Women's | 39,115 | 14,923 | adult | 60 | 51% / 49% |
| BCH | Boston Children's | 37,500 | 14,798 | **pediatric** | 5 | 44% / 56% |
| BIDMC | Beth Israel Deaconess | 9,906 | 3,172 | adult | 65 | 50% / 50% |

A few things to keep in mind: **BCH is a children's hospital** (median age 5, and it carries
an extra `AgeInDaysAtVisit` column), the other three are adult. Patients have on average
2.6 studies each (some epilepsy-monitoring patients have over 100). This is a
referral/monitoring population, so it skews heavily abnormal — not a general-population
sample.

## What a row looks like

Each row is a study, and the columns split into two groups.

**Metadata** (who/when): `BDSPPatientID`, `SessionID`, `AgeAtVisit`, `SexDSC`,
`ServiceName(EEG)`, the EEG times (`CreationTime`, `StartTime`, `EndTime`), and report
timestamps (`ProcedureDSC(Reports)`, `EncounterDTS(Reports)`, `DeidentifiedName(Reports)`).
There is **no free-text report body** in these tables — the reports have already been parsed
into the finding columns below (Harvard did this with a medical LLM).

**Findings** — about **40 columns**, one per clinical finding, e.g. `normal`, `abnormal`,
`foc slowing`, `gen slowing`, `spikes`, `seizure`, `bets`, `lpd`, `gpd`, `lrda`, `grda`,
`pdr`, `status`, plus a long tail of syndromes (`dravet`, `jme`, `eses`, `bects`, `angelman`,
…). 46 columns are shared by all four tables; MGH and BWH have 53, BCH 51, BIDMC 48.

## How the labels are encoded

A finding column is either **empty (the finding is absent / not noted)** or holds a short
string saying **where the label came from**:

| Value | Meaning |
|---|---|
| *(empty)* | not present |
| `report` | present — taken from the report text |
| `annotation` | present — taken from the EEG annotation |
| `report annotation` | present — in both the report and the annotation |
| `… verified` | as above, and additionally verified |

So **a non-empty cell means the finding is present**, and the text tells you the source and
whether it was checked. `normal` and `abnormal` are mutually exclusive — no study has both
(0 overlap), and only ~0.2% have neither — which confirms the "non-empty = present" reading.
Reports are detailed: a typical MGH study has 6–7 findings marked, and ~38% have eight or
more.

## Finding prevalence (share of studies where it is marked present)

| Finding | MGH | BWH | BCH | BIDMC |
|---|---|---|---|---|
| normal | 27.0% | 29.6% | 29.3% | 13.0% |
| abnormal | 72.8% | 69.9% | 62.6% | 83.4% |
| pdr (background rhythm) | 58.3% | 49.7% | 70.4% | 28.1% |
| foc slowing | 15.8% | 29.3% | 7.6% | 43.4% |
| gen slowing | 77.7% | 73.0% | 29.9% | 60.0% |
| spikes | 79.1% | 77.1% | 51.5% | 94.1% |
| seizure | 29.7% | 45.5% | 18.5% | 16.5% |
| status (epilepticus) | 8.7% | 8.7% | 3.3% | 4.8% |
| lpd | 7.4% | 16.6% | 0.9% | 6.5% |
| gpd | 7.3% | 14.5% | 0.4% | 5.3% |
| lrda | 2.7% | 10.5% | 0.2% | 1.3% |
| grda | 9.2% | 17.4% | 0.5% | 8.7% |
| low voltage | 4.8% | 2.4% | 0.8% | 4.8% |
| uninterpretable | 1.7% | 0.8% | 0.2% | 0.4% |

The pediatric site (BCH) looks different from the adults, as expected — much less slowing
and far fewer periodic/rhythmic patterns (lpd/gpd/lrda/grda), and a higher share of normal
background (pdr).

## How this maps to our five categories

Our task uses five labels; four of them line up directly, the epileptiform ones are a group
of columns here:

| Our category | Harvard column(s) |
|---|---|
| Abnormality | `abnormal` |
| Focal non-epileptiform | `foc slowing` |
| Generalized non-epileptiform | `gen slowing` |
| Focal / generalized epileptiform | `spikes`, `seizure`, `bets`, `lpd`, `lrda` (focal) · `gpd`, `grda` (generalized) |

So the Harvard labels are a **superset** of ours — the same core findings plus much finer
epileptiform and syndrome detail.

## Things to watch out for

- **No report text.** These tables are labels only; you can't run a text classifier on them
  directly. The raw reports were parsed away.
- **Sex is coded two ways.** MGH/BWH use `Female`/`Male`/`Unknown`; BCH/BIDMC use `M`/`F`/`U`.
- **Column-name inconsistencies** across tables: `n1` vs `N1` vs `n1_2`, `diffuse Beta`
  (capital B), spaces in names (`vertex wave`, `foc slowing`).
- **`SessionID` is not a unique key** — it is a per-patient counter (only ~100–260 distinct
  values per table). The study identity is the patient plus the report name
  (`DeidentifiedName(Reports)`, ~55k distinct in MGH).
- **Age is capped** near 121–122 (de-identification of the very elderly).

## How to read it

```python
import sqlite3
db = "/project/6019337/databases/eeg_harvard/HarvardEEG.db"
c = sqlite3.connect(f"file:{db}?immutable=1", uri=True)   # read-only, no locking
# prevalence of a finding at MGH
c.execute('SELECT COUNT(*) FROM MGH_EEG_with_reports WHERE abnormal IS NOT NULL').fetchone()
```

The table is owned by a labmate (`irynag`) and is a shared resource — coordinate before
using it in anything shared.
