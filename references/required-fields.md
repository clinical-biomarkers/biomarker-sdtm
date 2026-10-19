---
doc: required-fields
version: 1.0.0
status: current
updated: 2026-10-19
source: IEEE 2791 schemas, scripts/validate_bco.py, scripts/validate_bmkb.py, scripts/record_set_to_sdtm.py preflight, SDTMIG v3.4 core designations
---

# What is required where, and what to do when it is missing

## Contents

1. How to read this table
2. tBCO
3. rBCO
4. BMKB record
5. Study data (intermediate)
6. SDTM variables that stay empty

## 1. How to read this table

**Required by** says what breaks without the field:

- **IEEE**: `validate_bco.py` fails the file (IEEE 2791 schema)
- **skill**: `validate_bco.py` / `validate_bmkb.py` fails the file (this skill's rules)
- **convert**: `record_set_to_sdtm.py` stops before writing anything and lists the gap
- **SDTM Req / Exp**: the SDTM variable is Required or Expected; an empty Expected value must be
  reported
- **optional**: nothing breaks; list it as unfilled

**If missing** applies the missing-value policy in `SKILL.md`: `ask` = ask the user before
converting; `report` = leave `PLACEHOLDER` (text) or `null` (number) and list it in the hand-over
report.

## 2. tBCO

| Field | Required by | If missing |
|---|---|---|
| `object_id`, `spec_version`, provenance `name` / `version` / `license` / `created` / `modified` / `contributors` | IEEE | report (PLACEHOLDER is allowed in a draft) |
| `parametric_domain`, `error_domain`, `extension_domain.assay_protocol_extension` | skill | write the domain; content may be PLACEHOLDER |
| `target.lbtestcd`, `target.lbtest` (CDISC CT) | convert, SDTM Req | look the term up in CDISC CT; ask if no term fits |
| `assay.assay_name` | convert (LBGRPID, ASSAYNAM, BMASSAY) | ask |
| `analytical_performance` LoD, LLOQ, ULOQ `.value` | convert (censor zones, LBLLOD/LBLLOQ/LBULOQ) | ask |
| `reporting_convention.unit` | convert, SDTM Exp (LBORRESU/LBSTRESU) | ask |
| `specimen_requirements.specimen_type` (CDISC SPECTYPE) | convert, SDTM Perm (LBSPEC, BMSPEC) | ask |
| `reference_limits[]` (direction, value) | SDTM Exp (LBSTNRHI/LBSTNRLO, LBNRIND) | report; LBNRIND stays empty |
| `interpretation_rules[]` with `role` and `display` | BM.BMRULE for each role | report; BMRULE stays empty |
| `assay.method`, `assay.manufacturer`, `assay.platform`, `assay.loinc_code` | SDTM Perm | report |
| `target.analyte_identifiers[].curie` | optional (BM uses the BMKB id) | report if OLS has no entry |
| everything else (lots, handling, stability, interferences, imprecision) | optional | report |

## 3. rBCO (one per subject per analytical run)

| Field | Required by | If missing |
|---|---|---|
| IEEE domains and provenance (as for the tBCO), `provenance_domain.derived_from` | IEEE / skill | report |
| `assay_run_extension.usubjid`, `studyid` | convert | ask |
| `measurements[].specimen_id` | convert (joins the study-data result) | ask |
| `measurements[].censor_state` | convert (from `resolve_censor_state()`) | compute it; never leave it empty |
| `measurements[].collection_dtc` | SDTM Exp (LBDTC) | report |
| `measurements[].visit`, `visitnum` | SDTM Perm / Exp | report |
| instrument, lots, calibration, QC, `analysis_dtc` | optional | report |

No demographics and no result values, ever.

## 4. BMKB record

| Field | Required by | If missing |
|---|---|---|
| `condition.id` / `name` / `resource` | skill, convert | ask (the condition comes from the context of use) |
| `best_biomarker_role[]` (BEST, one per role) | skill, convert | ask |
| `biomarker_component[]` (five fields) | skill | entity id: report if OLS has no entry; the statement must still be written |
| `provenance` provider / author / date / description | skill | report (PLACEHOLDER passes with a warning) |
| `entity_normal_ranges` | optional | omit |

## 5. Study data (`assets/study_data_template.json`)

| Field | Required by | If missing |
|---|---|---|
| `dm[]` row for every subject with an rBCO | convert | ask |
| `results[]` row for every rBCO measurement (`usubjid`, `specimen_id`, `result`) | convert | ask |
| `results[].unit` equal to the tBCO unit | convert | convert units first, or ask |
| `claim.evidence` (at least one id) | convert, BM.BMEVID | ask |
| `claim.bmid`, `bmver`, `asserted_by`, `assertion_date` | BM | report |
| `dm[]` AGE, AGEU, SEX, COUNTRY, RFSTDTC | SDTM Req / Exp | report |
| `dm[]` RACE, ETHNIC, RFXSTDTC | SDTM Exp / Perm | report; RFXSTDTC only exists when a product is given |
| `study.category` | SDTM Exp (LBCAT) | report |

## 6. SDTM variables that stay empty

Expected variables the converter leaves empty, and why, so the hand-over report can say so:

- **LBLOBXFL**: no RFXSTDTC (the study gives no product)
- **LBSTNRLO**: the tBCO has only an upper reference limit
- **LBNRIND**: the tBCO has no reference limits
- **RACE / ETHNIC**: absent from the demographics file
