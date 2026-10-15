# Inputs — Simulated Test Inputs (and outputs)

> ⚠️ **This file is for the human operator, NOT the agent.** During a test run the agent is
> pointed only at `troponin_I/`. Keep this file out of the agent's view — it names the source
> publication (PMID 19710485), which the agent could otherwise fetch to shortcut the test.

> **What this folder is.** `fixtures/` holds **test inputs and their outputs**, kept separate
> from the expert-validated reference set in `../examples/`, so test artifacts never mix with
> validated data.

> **What the test set is.** A synthetic set of the "source documents" a pharmaceutical
> sponsor would hand to the BCO skill. The skill's forward direction is
> *documents → record set (tBCO + rBCO + BMKB) → SDTM*; the self-test never exercised the
> document-reading step, so this set supplies it.

> **Provenance (reverse-engineered from):**
> - the real publication the example derives from — Keller T, Zeller T, Peetz D, et al.
>   *Sensitive Troponin I Assay in Early Diagnosis of Acute Myocardial Infarction.*
>   N Engl J Med 2009;361:868–877 (PMID 19710485); and
> - the reference Troponin I example (`../examples/troponin_I/`), whose values and
>   structure this set is designed to reproduce.
>
> All sponsors, sites, subjects, lot numbers and values are **fictitious**.

## Test set — `troponin_I/`

- `01_study_protocol_synopsis.md` — the trial in brief
- `02_biomarker_context_of_use.md` — what the biomarker is and the decision rule
- `03_assay_instructions_for_use.md` — the manufacturer's IFU (Troponin I Ultra)
- `04_method_validation_report.md` — the laboratory's validation of the assay
- `05_laboratory_manual_excerpt.md` — specimen collection, handling, schedule
- `06_data_transfer_specification.md` — the field spec for the lab data extract
- `07_lab_results.csv` — patient-level results (the data)
- `08_demographics.csv` — subject demographics

## How these map to the record set

- **tBCO** ← `03` (assay: name, platform, method, specimen, LOINC) + `04` (LoD/LLoQ/ULoQ, imprecision, reference limit)
- **rBCO** ← `05` (sampling schedule, handling) + `07` (per-patient measurements, censor states)
- **BMKB record** ← `02` (entity, BEST role, condition, evidence, assertion)
- **SDTM** ← all of the above + `06`, `07`, `08`

## Test outputs

Generated output from a test run should be written under `troponin_I/_output/` (or another
scratch dir), never into `../examples/`.
