---
doc: best-definitions
version: 1.0.0
status: current
updated: 2026-10-15
source: FDA-NIH BEST glossary
---

# BEST Biomarker Definitions

> FDA-NIH Biomarker Working Group. *BEST (Biomarkers, EndpointS, and other Tools) Resource* [Internet]. 2016–.
> URL: https://www.ncbi.nlm.nih.gov/books/NBK326791/

## Core Definition

> A **biomarker** is a defined characteristic that is measured as an indicator of normal biological processes, pathogenic processes, or biological responses to an exposure or intervention, including therapeutic interventions.
>
> Biomarkers may include molecular, histologic, radiographic, or physiologic characteristics.
> A biomarker is **not** a measure of how an individual feels, functions, or survives.

## Seven Biomarker Categories (BEST)

| # | Category | Definition | Relevance to BCO skill |
|---|----------|-----------|----------------------|
| 1 | **Susceptibility/Risk** | Indicates the potential for developing a disease or medical condition in an individual who does not currently have clinically apparent disease. | Distinguish from diagnostic — risk biomarkers apply pre-disease |
| 2 | **Diagnostic** | Detects or confirms presence of a disease or condition of interest, or identifies individuals with a subtype of the disease. | Most common use case (e.g., Troponin I for AMI diagnosis) |
| 3 | **Prognostic** | Identifies likelihood of a clinical event, disease recurrence, or progression in patients who have the disease or condition of interest. | Clarifies relationship to condition in BM.BMCOND |
| 4 | **Predictive** | Identifies individuals more likely than similar individuals without the biomarker to experience a favorable or unfavorable effect from exposure to a medical product or environmental agent. | Requires treatment comparison to establish; not interchangeable with prognostic |
| 5 | **Monitoring** | Measured repeatedly for assessing status of a disease or medical condition, or for evidence of exposure to (or effect of) a medical product or environmental agent. | Troponin I in the worked example is MONITORING — measured serially (0h, 3h, 6h) |
| 6 | **Safety** | Measured before or after an exposure to a medical product or environmental agent to indicate the likelihood, presence, or extent of toxicity as an adverse effect. | Populated in BM.BMROLE when biomarker tracks toxicity |
| 7 | **Pharmacodynamic/Response** | A biomarker that shows a biological response has occurred in an individual who has been exposed to a medical product or environmental agent. | Indicates engagement of a therapeutic target |

### Provenance: where each role comes from

The biomarker role enters the record set model at two points:

- **BiomarkerKB record** → `best_biomarker_role` (string, lowercase, e.g. `monitoring`)
- **BM domain** → `BMROLE` (string, uppercase, e.g. `MONITORING`)

The BMKB record establishes the canonical role from literature/evidence; the BM row repeats it in SDTM casing.

### Distinguishing prognostic vs predictive (common pitfall)

From BEST § Understanding Prognostic versus Predictive Biomarkers:

- **Prognostic** biomarkers are identified from observational data — they predict outcome *regardless of treatment*.
- **Predictive** biomarkers require a treatment-by-biomarker interaction in a randomized trial — they identify who benefits from a *specific* intervention.
- A biomarker can be both prognostic and predictive.
- Without a comparator arm, you cannot distinguish them.

## Biomarker Description Framework

BEST defines a biomarker description as a succinct summary with these elements:

| Record Set | What it captures | Maps to |
|-----------|-----------------|---------|
| **Biomarker Identity** | Name, unique ID (UniProt/LOINC), acronym, source/matrix, type (molecular, histologic, radiographic, physiologic) | BMKB `assessed_biomarker_entity` / `assessed_biomarker_entity_id`; tBCO `target` |
| **Biologic Plausibility** | Brief summary of the biological pathway linking the biomarker to the condition | Study documents (context of use, protocol) → BM.BMEVID via `--evidence`; the BMKB record carries no evidence |
| **Measurement Method** | Platform, assay method, units of quantification | tBCO `assay`; BM.BMASSAY/BMNAM/BMPLAT/BMMETHOD |

### Application in the record set model

The record set implements the BEST description framework across its pieces:

```
BEST Element        → Record Set Part
─────────────────────────────────────────────
Biomarker Identity  → BMKB record (entity, ID, type)
Condition           → BMKB `condition` + BM.BMCOND/BMCONDID
Role                → BMKB `best_biomarker_role` + BM.BMROLE
Measurement Method  → tBCO (assay, platform, method, specimen, LOINC)
Performance         → tBCO (LoD, LLOQ, ULOQ, precision, reference limits)
Evidence            → study documents → BM.BMEVID (via --evidence)
Censoring           → rBCO `measurements[].censor_state`
```

## Relationship to the BCO Skill

The skill must:

1. **Assign the correct BEST role** to each biomarker based on the study protocol (how the biomarker is used in the trial, not just its biology)
2. **Populate BM.BMROLE** in SDTM output with the uppercase role code
3. **Derive "monitoring" and "diagnostic" roles** from study design:
   - Serial timepoints → likely *monitoring*
   - Single-threshold decision → likely *diagnostic* or *prognostic*
4. **Document the basis** for role assignment (trial design, published evidence)

## References

- BEST Resource homepage: https://www.ncbi.nlm.nih.gov/books/NBK326791/
- Glossary: https://www.ncbi.nlm.nih.gov/books/NBK338448/
- Contents of a Biomarker Description: https://www.ncbi.nlm.nih.gov/books/NBK566059/
- FDA overview: https://www.fda.gov/drugs/biomarker-qualification-program/about-biomarkers-and-qualification
