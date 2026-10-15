# Data Transfer Specification — Laboratory Results Extract

- **Study:** BM-2026-01
- **Document:** Lab Data Transfer Specification, v1.1
- **Format:** comma-separated values (CSV), UTF-8
- **Deliverable:** `07_lab_results.csv`, `08_demographics.csv`

## 1. Lab results extract (`07_lab_results.csv`)

One row per result (per subject, per timepoint). Fields are as produced by the laboratory
information system.

- `samp_id` — specimen barcode
- `subject` — subject number within the study
- `study` — protocol number
- `site` — site number
- `visit` — visit / timepoint label as recorded at collection
- `collect_dt` — local collection date and time, `YYYY-MM-DD HH:MM`
- `specimen` — specimen matrix
- `analyte_code` — laboratory analyte code
- `analyte` — analyte name as reported
- `result` — result **as reported**, including any censoring operator
- `unit` — result unit
- `instrument` — analyser the result was produced on

## 2. Demographics extract (`08_demographics.csv`)

One row per subject, from the study EDC.

- `subject`, `study`, `site`
- `age`, `age_unit`
- `gender`
- `country` — country name as recorded
- `first_visit_dt` — date of first study visit

## 3. Conventions

- Results are reported to 3 decimal places.
- Values below the limit of quantitation are reported with a leading `<`.
- Missing values are left empty.
- Timestamps are local time.
