# Harvard (HEEDB) EEG labels — how we read the fields we compare against

Before trusting any comparison, we had to be precise about what Harvard's label columns actually
mean. This note is that: what the fields are, how each cell is coded, and — for the specific fields
we compare our MedGemma labels against — the exact definition, how it maps to our field, and how
common it is. It is verified from the data-descriptor paper's supplement (Sun et al., *Epilepsia*
2025, **Data S1**) and checked against the database itself.

## The tables

Each Harvard hospital has one table, `<COHORT>_EEG_with_reports`, with a row per recording session
and one column per finding (39 findings) alongside identifier/metadata columns. A report
(`DeidentifiedName(Reports)`) spans several session rows, so we work at the report level (present
if any of its rows carry the finding).

## How a cell is coded — the part that's easy to get wrong

A finding cell is **not** a yes/no. It is a short **provenance string** saying *how* the finding
was established, or it is empty. Harvard derived findings three ways (Data S1 §A; paper abstract):

- **annotation** — keyword / regular-expression matching over the recording's EEG annotations
  (Data S1 Table S5).
- **report** — a fine-tuned medical LLM reading the free-text report and answering a
  yes / no / not-mentioned question per finding. Naming: Data S1 §A.2 calls it *Medical LLaMA 3-8B*
  (the paper's own text is inconsistent on the size, also writing "Llama 3 7B"); the public tooling
  (`process_reports_by_medicalllama.py` and the repo README) calls it *Medical-LLaMA* and links it
  to the Hugging Face model `ContactDoctor/Bio-Medical-Llama-3-8B` — the three names are the same
  model. The production prompt template is given in Data S1: *"Based on the medical context of
  neurology and EEG analysis, does the following report indicate the presence of [finding] in the
  EEG? Please respond with yes, no, or not mentioned."* (The example script in the public repo uses
  a simpler seizure-specific "Answer Yes or No" phrasing — a demo, not the full 33-finding
  template.)
- **verified** — checked by a person (expert curation).

A cell holds whichever applied, combined: `report`, `annotation`, `verified`, `report annotation`,
`report verified`, `report annotation verified`, `annotation verified`, or empty. So the column is
a **merge of both extraction channels plus verification**, not a single channel. (An earlier
version of this note called the column "the report channel" — that was wrong; the report channel is
only the subset of cells whose tag contains `report`.)

Two consequences we rely on:

- **non-null = present; empty = not recorded.** There is no value meaning "absent", so empty
  bundles three different things — the report said absent, it wasn't mentioned, or nobody annotated
  it. Harvard can't separate them; we keep `explicitly_absent` vs `not_mentioned` on our side but
  collapse to present-vs-not to compare. Data S1 §A.4 is explicit about this: *"'not mentioned' and
  'not available' are common, but they do not necessarily indicate a negative finding. Therefore …
  we can only assess the agreement between the two when the finding is marked as 'yes'."*
- **the tag tells you the source**, which matters because we read only the report text. Comparing
  against `report`-tagged cells is the fair like-for-like; `annotation`-only cells may describe
  something never written in the narrative.

### Exactly what we count as "present" in each comparison

A cell is a set of up to three tags — `report`, `annotation`, `verified` — or empty. Each of the
three comparisons in our reports reads the cell differently:

| cell value | meaning | "vs all" (κ_all) | "vs report-text" (κ_report) | in verified set (recall) |
|---|---|---|---|---|
| *(empty)* | not recorded (absent / not-mentioned / not-annotated) | not present | not present | no |
| `report` | LLM found it in the report text | present | present | no |
| `annotation` | regex found it in the recording annotations | present | not present | no |
| `verified` (alone) | expert-flagged, no channel tag (rare) | present | not present | yes |
| `report annotation` | both channels | present | present | no |
| `report verified` | in the text + expert-verified | present | present | yes |
| `annotation verified` | in annotations + expert-verified | present | not present | yes |
| `report annotation verified` | both channels + expert-verified | present | present | yes |

So: **"vs all"** counts any non-empty cell as present; **"vs report-text"** counts a cell as
present only if its tag contains `report` (the fair like-for-like, since we read only the text);
the **verified set** is every cell whose tag contains `verified` (recall = how many of those we
also called present). Our own side is always collapsed to present vs not-present
(`explicitly_absent` and `not_mentioned` both count as not-present). A report spans several session
rows, so it is present-in-text if any of its rows carries a `report` tag.

**The present-set at each level, written out.** Against Harvard, "present" is exactly:

- **vs all** — `report`, `annotation`, `verified`, `report annotation`, `report verified`,
  `annotation verified`, `report annotation verified` (every non-empty cell); only empty is
  not-present.
- **vs report-text** — the cells whose tag contains `report`: `report`, `report annotation`,
  `report verified`, `report annotation verified`. Here `annotation`-only, `verified`-only and
  `annotation verified` count as not-present, alongside empty.
- **verified set** — the cells whose tag contains `verified`: `verified`, `report verified`,
  `annotation verified`, `report annotation verified`. Positives only (there is no "verified
  absent"), so we report recall on this set, not κ.

**What `verified` actually confirmed.** It is a separate, stronger step than the report itself.
Every `report` label already comes from a clinical report a clinician wrote and signed (Data S1
§A.4: "reviewed and confirmed by at least two clinicians, including a senior clinician"). The
`verified` tag sits on top of that — Harvard's *multi-expert* labels, which Data S1 §A.4 calls
"event-level ground truth", the strongest of the three tiers. An expert confirmed that the specific
finding is genuinely present in that recording, independent of what the report LLM or the
annotation regex said. It is positives-only (no expert "absent") and per-finding, not per-report.
It can even stand alone — e.g. MGH `foc slowing` carries 1,262 cells tagged `verified` with no
`report` or `annotation`: present by expert review although neither automated channel flagged it.

We confirmed this on the data rather than assuming it:

| check | result |
|---|---|
| `report`-tagged cells whose report text contains the finding word | 100% |
| `annotation`-only cells whose report text contains it | 72% (often not in the narrative) |
| `foc slowing` and `gen slowing` verified in the *same* MGH report | 49 — so verification is per-field, not per-report |

### Cross-check against the public GitHub label tables

The same label tables are published in `bdsp-core/Harvard-EEG-Database-Tools`
(`MGH/BWH/BCH/BIDMC_EEG_with_reports.csv.zip`). We downloaded them and compared them column by
column against the `HarvardEEG.db` we query: the row counts and the full value vocabulary match
**exactly**, cell for cell. For MGH `bs`, both sides give 75,994 empty / 10,930 `report` / 2,162
`annotation` / 1,199 `report annotation` / 201 `report annotation verified` / 159 `report verified`
/ 50 `annotation verified` / 21 `verified`. So the database we compare against is the same public
source, and the eight values above are the complete cell vocabulary — there is no ninth code we
might have missed.

## The fields we actually compare against

These are the Harvard columns we line our labels up with, with report-level present rate per
hospital and their Table S5 annotation keyword. The present rate here is over **all** of that
hospital's reports; the comparison reports instead report it over the reports we and Harvard both
labeled (the intersection), so the same figure comes out a point or two lower there — e.g. `bs` is
12% of all MGH reports but 11% of the intersection:

| Harvard column | our field | present — MGH / BWH / BCH | Table S5 keyword | notes |
|---|---|---|---|---|
| `abnormal` | abnormality | 66% / 67% / 58% | `abnormal` | clean 1:1; **100% report-derived** (LLM only, no annotation/verified cells) |
| `foc slowing` | focal_slowing | 14% / 24% / 7% | `foc* slow*, r* slow*, l* slow*` | just the word "slowing" with laterality — narrower than our old focal *non-epileptiform* bucket |
| `gen slowing` | generalized_slowing | 77% / 72% / 27% | `gen* slow*` | just "generalized slowing" |
| `bs` | burst_suppression | 12% / 15% / 9% | `burst, suppression, supp, bsr` | keyword also matches plain **"suppression"**, so the annotation channel is broad — a big reason Harvard's `bs` is marked 3–6× more than our text-only reading (at MGH/BWH; at BCH their `bs` is mostly text-derived) |

Two of these were also touched by earlier work: `abnormal` is the one clean field in the
abnormality comparison, and `foc/gen slowing` were the approximate targets in the older
focal/generalized *non-epileptiform* mapping (our non-epi bucket lumps slowing together with
attenuation, asymmetry, disorganization and excessive beta, so it is broader than Harvard's
slowing-only column — their own Table S5 keyword confirms the mismatch, not just our
`analysis/mapping_check.py`).

Triphasic waves, discontinuous background and suppressed background have **no** Harvard column at
all (nearest to suppressed is `low voltage`, a different thing), so those stay labels-only.

## All 39 finding fields

Meaning is the standard-EEG reading of the column name; the keyword column is Harvard's actual
Table S5 regex for the **annotation** channel (the report channel used the LLM question above, not
these keywords), shown because it is their published definition and reveals how narrow some fields
are.

| # | Field | What it means (standard EEG terminology) | Annotation keyword (Data S1 Table S5) |
|---|---|---|---|
| 1 | normal | EEG reported normal / within normal limits | `normal` |
| 2 | abnormal | EEG reported abnormal (any abnormal finding) | `abnormal` |
| 3 | awake | Awake state captured | `eo, awake` |
| 4 | n1 | Sleep stage N1 | `drowsiness, drowsy, n1` |
| 5 | n2 | Sleep stage N2 | `spindle, spindles, ss, kss, n2, ii` |
| 6 | bets | Benign epileptiform transients of sleep (small sharp spikes) | `bets, sss` |
| 7 | wicket | Wicket spikes (benign variant) | `wicket[s]` |
| 8 | spindles | Sleep spindles | `spindle, spindles, ss, kss` |
| 9 | vertex wave | Vertex sharp transients | `v, vw, vert, vertw, vertwave, vertex, vertexwave` |
| 10 | posts | Positive occipital sharp transients of sleep | `posts` |
| 11 | breach | Breach rhythm (activity over a skull defect) | `bre[ea]ch` |
| 12 | spikes | Epileptiform spikes / sharp waves | `spike[s], discharge[s], sharp` |
| 13 | seizure | Electrographic / clinical seizure | `sz, serizure[s]` |
| 14 | lpd | Lateralized periodic discharges | `lp[e]d[s], pled` |
| 15 | gpd | Generalized periodic discharges | `gpd[s]` |
| 16 | lrda | Lateralized rhythmic delta activity | `lrda, tirda` |
| 17 | grda | Generalized rhythmic delta activity | `grda, [of]irda` |
| 18 | bs | Burst-suppression | `burst, suppression, supp, bsr` |
| 19 | foc slowing | Focal slowing | `foc* slow*, r* slow*, l* slow*, l* temporal slow*` |
| 20 | gen slowing | Generalized / diffuse slowing | `gen* slow*` |
| 21 | pdr | Posterior dominant rhythm (normal background) | `pdr` |
| 22 | dravet | Dravet syndrome pattern | *(not in Data S1 — undocumented)* |
| 23 | eses | Electrical status epilepticus in sleep | `eses` |
| 24 | fold | Unclear — appears in Data S1 figures but has no keyword or definition | *(none)* |
| 25 | jae | Juvenile absence epilepsy | `jea` |
| 26 | jeavons | Jeavons syndrome | *(not in Data S1 — undocumented)* |
| 27 | jme | Juvenile myoclonic epilepsy | `hme` |
| 28 | k_complexes | K-complexes | `k-complexes, k` |
| 29 | bects | Benign epilepsy with centrotemporal spikes | `bects` |
| 30 | bipd | Bilateral independent periodic discharges | `bipd` |
| 31 | cjd | Creutzfeldt-Jakob periodic pattern | `cjd` |
| 32 | diffuse Beta | Diffuse / excessive beta | `diffuse beta` |
| 33 | low voltage | Low-voltage background | `low voltage` |
| 34 | ppr | Photoparoxysmal response | `ppr` |
| 35 | status | Status epilepticus | *(listed as a finding, no keyword given)* |
| 36 | sunflower | Sunflower syndrome | *(not in Data S1 — undocumented)* |
| 37 | uninterpretable | Recording uninterpretable | *(in figures, no keyword)* |
| 38 | wham | Unclear — not standard EEG terminology, absent from Data S1 | *(none)* |
| 39 | angelman | Angelman syndrome pattern | `angelman` |

The keyword lists carry small typos (seizure `serizure`, JAE `jea`, JME `hme`) — those affect only
the annotation channel, not the report labels. Six columns (dravet, fold, jeavons, sunflower,
uninterpretable, wham) fall outside the paper's 33 documented findings, so they are effectively
undocumented.

The identifier / metadata columns: `SiteID`, `BDSPPatientID`, `SessionID`, `AgeAtVisit`, `SexDSC`,
`ServiceName(EEG)`, `CreationTime(EEG)`, `StartTime(EEG)`, `EndTime(EEG)`, `ProcedureDSC(Reports)`,
`EncounterDTS(Reports)`, `BeginDTS(Reports)`, `ExamEndDTS(Reports)`, `DeidentifiedName(Reports)`.

## Reliability (Data S1 §A.4)

There is no gold standard, so Harvard reports an "ambiguity" rate — the share of true-yes cases
the report LLM missed (called no): **2.25%** on average against annotations, and **0%** against
multi-expert labels (the LLM never said no where experts said yes). So the report channel is
high-recall and rarely denies a finding that is present. The report labels were also "reviewed and
confirmed by at least two clinicians, including a senior clinician."

## Who read each report

There is no author column. The reading physician appears only inside the report text, as a
signature — e.g. *"I (…, MD) have reviewed the study and edited this report."* Reports are
de-identified with **PHILter** (rule-based + statistical PHI removal, HIPAA Safe Harbor, with date
shifting), which is why most signatures collapse to `*****` while a few readers' initials slip
through:

| Hospital | Reports | Has "I (…)" signature | Any attestation phrase | Distinguishable reader |
|---|---|---|---|---|
| MGH | 55,557 | 35,652 (64%) | 54,233 (98%) | 8,182 |
| BWH | 21,035 | 2 (0%) | 11,619 (55%) | 2 |
| BCH | 25,022 | 0 (0%) | 7,297 (29%) | 0 |
| **Total** | **101,614** | **35,654 (35%)** | **73,149 (72%)** | **8,184 (8%)** |

The distinguishable readers (≈14, almost all MGH: ADL, ESR, LM, DBH, JS, CMM, LTG, KCS, …) are in
`results/harvard/report_authors.csv`.

## Sources

- Sun et al., **Harvard Electroencephalography Database: A comprehensive clinical
  electroencephalographic resource from four Boston hospitals**, *Epilepsia* 2025 —
  doi:10.1111/epi.18487 — <https://onlinelibrary.wiley.com/doi/10.1111/epi.18487>
  (§A extraction method + LLM prompt, Table S5 keywords, Table S2 finding counts, §A.4 reliability,
  §D de-identification — all in the **Data S1** supplement).
- Dataset (credentialed), Harvard EEG Database v4.1 — <https://bdsp.io/content/harvard-eeg-db/4.1/>
- Extraction tooling and shared files — bdsp-core/Harvard-EEG-Database-Tools —
  <https://github.com/bdsp-core/Harvard-EEG-Database-Tools>. The public repo holds the label tables
  themselves (`MGH/BWH/BCH/BIDMC_EEG_with_reports.csv.zip`), the LLM extraction example
  (`process_reports_by_medicalllama.py`, `format_reports.py` — seizure only), the ICD-10 and ATC
  medication dictionaries, `HEEDB_patients.csv`, and the statistics notebooks (`read_data.ipynb`,
  `HEEDB_statistics.ipynb`). It does **not** publish the full per-finding prompts or the keyword
  definitions beyond the seizure example — those are only in Data S1.
- Our own checks: `analysis/slowing_vs_harvard.py` and `analysis/background_vs_harvard.py`
  (provenance handling), `analysis/mapping_check.py` (the slowing-vs-non-epi mismatch); label
  schema in `HarvardEEG.db`; reader signatures in `results/harvard/report_authors.csv`.
