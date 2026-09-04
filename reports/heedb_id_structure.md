# Harvard EEG Database — ID structure of the label tables

The HEEDB label tables (`*_EEG_with_reports`, one per hospital) are organized as a simple
hierarchy of identifiers. From the top:

```
SiteID            hospital            S0001 = MGH, S0002 = BWH, I0002 = BIDMC, I0003 = BCH
  └─ BDSPPatientID   patient          de-identified; the master key
        └─ report      NeuroReport_<a>_<b>_<date>.txt   ( = DeidentifiedName(Reports) )
              └─ SessionID   recording segment under that report
```

**SiteID** — the hospital. There is one label table per site; SiteID is constant within a table.

**BDSPPatientID** — the de-identified patient, and the key that ties everything together. One
patient has many EEG reports over time. Patient-level facts (diagnoses in ICD-10, medications in
ATC) are attached here, at the patient level — not per report.

**Report** — `DeidentifiedName(Reports)`, a filename of the form `NeuroReport_<a>_<b>_<date>.txt`.
This is one complete EEG report document (Impression / Clinical indication / Method / Description).
The free-text of the report is **not stored in the database** — it lives in the HEEDB zip dumps and
is joined back by this exact filename.

**SessionID** — a small segment counter *within* a report. A continuous / long-term monitoring
study (EMU or ICU cEEG) is split into many recording segments, so one report covers many
SessionIDs. SessionID is not unique and carries no separate text — every session of a report shares
the same report document.

Because of this, the table has more rows than reports, and more reports than patients. For MGH:

| Level | Count (MGH) |
|---|---|
| rows (session segments) | 90,716 |
| unique reports (`DeidentifiedName(Reports)`) | 55,557 |
| unique patients (`BDSPPatientID`) | 34,620 |

So the ordering is: **one patient → several reports over time → each report → several recording
sessions**; diagnoses and medications hang off the patient, and the report text is fetched from the
zip dumps by the report filename.
