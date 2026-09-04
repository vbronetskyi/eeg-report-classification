# Harvard (HEEDB) EEG report labels — the fields and how they were extracted

The Harvard EEG Database ships a per-recording label table (`*_EEG_with_reports`) with 39
finding columns plus identifier/metadata columns. This note lists every field, what it means, and
how it was produced. As of now this is **verified**, not reconstructed: the data-descriptor
paper's supplement (Sun et al., Epilepsia 2025, **Data S1**) gives the extraction method, the
prompt, and the keyword lists.

## How the labels were made — two channels

Data S1 §A describes two separate extraction pipelines over two data sources:

- **From EEG annotations → keyword + regular-expression matching** (Data S1 Table S5). This is
  the plain keyword search.
- **From EEG reports → a fine-tuned LLM** (a Q&A fine-tuned Llama 3, "Bio-Medical-Llama-3-8B" on
  Hugging Face). Each finding is one templated question, with a **three-way** answer:

  > "Based on the medical context of neurology and EEG analysis, does the following report
  > indicate the presence of **[finding]** in the EEG? Please respond with **yes, no, or not
  > mentioned**."

The labels we compared against are the **report / LLM channel** (`*_EEG_with_reports`), not the
keyword channel — so our MedGemma-vs-Bio-Medical-Llama comparison is model-vs-model, as intended.
Two more points from Data S1 §A.4 that matter for reading the columns:

- An empty finding column means the model answered **not mentioned**, which is *not* the same as
  "absent"; the paper only measures agreement on the "yes" cells (so `present = column non-empty`
  is the right reading, as we used).
- The report labels are "reviewed and confirmed by at least two clinicians, including a senior
  clinician," so they are treated as relatively stronger than the annotation labels.

## The 39 finding fields

Meaning is the standard-EEG reading of the column name. The keyword column is Harvard's actual
Table S5 regex for the **annotation** channel (the report channel used the LLM prompt above, not
these keywords) — it is shown because it is their real, published definition and it reveals how
narrow some fields are.

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

Two nuances worth knowing: the keyword lists carry small typos (seizure `serizure`, JAE `jea`,
JME `hme`) — but those only affect the annotation channel, not our report labels. And six DB
columns (dravet, fold, jeavons, sunflower, uninterpretable, wham) fall outside the paper's 33
documented findings, so they are effectively undocumented.

## The identifier / metadata columns

`SiteID`, `BDSPPatientID`, `SessionID`, `AgeAtVisit`, `SexDSC`, `ServiceName(EEG)`,
`CreationTime(EEG)`, `StartTime(EEG)`, `EndTime(EEG)`, `ProcedureDSC(Reports)`,
`EncounterDTS(Reports)`, `BeginDTS(Reports)`, `ExamEndDTS(Reports)`, `DeidentifiedName(Reports)`.

## Who read each report

There is no author column. The reading physician appears only inside the report text, as a
signature — e.g. *"I (…, MD) have reviewed the study and edited this report"* (sometimes "…with
the fellow", meaning a fellow drafted and the attending signed off). Data S1 §D explains the
masking: reports are de-identified with **PHILter** (rule-based + statistical PHI removal, HIPAA
Safe Harbor, with date shifting), which is why most signatures collapse to `*****` while a few
readers' initials slip through. Coverage of that signature line, by hospital:

| Hospital | Reports | Has "I (…)" signature | Any attestation phrase* | Distinguishable reader** |
|---|---|---|---|---|
| MGH | 55,557 | 35,652 (64%) | 54,233 (98%) | 8,182 |
| BWH | 21,035 | 2 (0%) | 11,619 (55%) | 2 |
| BCH | 25,022 | 0 (0%) | 7,297 (29%) | 0 |
| **Total** | **101,614** | **35,654 (35%)** | **73,149 (72%)** | **8,184 (8%)** |

\* "edited this report / reviewed the study / personally reviewed / electronically signed" etc.
\*\* signature keeps initials, so individual readers can be told apart; the rest collapse to a
masked `*****`. The distinguishable readers (≈14, almost all MGH: ADL, ESR, LM, DBH, JS, CMM,
LTG, KCS, …) are listed in `results/harvard/report_authors.csv`.

## How this bears on our comparison

Only a few of these map 1:1 to one of our five categories. `abnormal` is the clean one, which is
why the comparison report keeps to it. Table S5 confirms why the slowing findings do not line up:
Harvard's `foc slowing` keyword is `foc* slow*, r* slow*, l* slow*` and `gen slowing` is
`gen* slow*` — i.e. **only the word "slowing"** (with laterality) — whereas our focal / generalized
non-epileptiform categories bundle slowing together with attenuation, asymmetry, disorganization,
and excessive beta. Their own definitions, not just our empirical check (`analysis/mapping_check.py`),
show the mismatch.

## Reliability, per Data S1 §A.4

There is no gold standard, so they report an "ambiguity" rate — the share of true-yes cases the
LLM missed (called no): **2.25%** on average against annotations, and **0%** against multi-expert
labels (the LLM never said no where experts said yes). So the report LLM is high-recall and rarely
denies a finding that is present.

Sources: Sun et al., *Harvard Electroencephalography Database*, Epilepsia 2025 (doi
10.1111/epi.18487), **Data S1** supplement (§A extraction method + prompt, Table S5 keywords,
Table S2 finding counts); label schema — `*_EEG_with_reports` in `HarvardEEG.db`; reader
signatures — `results/harvard/report_authors.csv`.
