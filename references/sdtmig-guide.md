---
doc: sdtmig-guide
version: 1.0.0
status: current
updated: 2026-10-15
source: CDISC SDTMIG v3.4
---

> **Full specification:** the complete SDTMIG v3.4 PDF ships beside this file as
> `sdtmig-v3.4.pdf` (7.2 MB, 2022-07-21). Consult it whenever this summary is not
> sufficient — this file is a distillation, not a substitute.

# SDTM for the Biomarker Record Set Model

> SDTMIG v3.4 rules for the domains the Troponin I example uses.
> Covers DM, LB, SUPPLB, and the proposed BM domain.
> Based on SDTMIG v3.4 (Final, 2022-07-21) and SDTM v2.1 (Final, 2024-06-07).

## Overview: Which Domains & Why

| Domain | Class | Purpose | In SDTMIG? |
|--------|-------|---------|------------|
| **DM** | Special-purpose | Demographics — one row per subject | ✅ Yes (§5.2) |
| **LB** | Findings (specimen-based) | Laboratory test results — one row per result | ✅ Yes (§6.3.5.6) |
| **SUPPLB** | Relationship | Supplemental LB qualifiers — one row per qualifier | ✅ Yes (§8.4) |
| **BM** | (Proposed) | Biomarker context — one row per biomarker-assay combo | ❌ Not yet proposed |

### How the Record Set maps to SDTM

```
tBCO ──────→ LB reference limits, method, specimen, LOINC
       ─────→ SUPPLB (LBGRPID): ASSAYNAM, ASSAYPLT, LBLOD, LBLLOQ, LBULOQ
       ─────→ BM: assay info, BMBCOID, BMRULE

rBCO ──────→ SUPPLB (LBSEQ): CENSOR (derived from measurement values)
       ─────→ SUPPLB (LBGRPID): RBCOID
       ─────→ DM: subject reference dates (none directly — DM is CRF-sourced)

BiomarkerKB ─→ BM: BMENTNM, BMENTID, BMENTTP, BMCVTERM, BMROLE,
                BMCOND, BMCONDID, BMEVID
```

### Join Path

```
DM ──USUBJID──→ LB ──LBSEQ──→ SUPPLB (per-result qualifiers like CENSOR)
                  ───────────→ SUPPLB (LBGRPID-level qualifiers: ASSAYNAM, RBCOID…)
BM ──BMSRCDOM/BMSRCVAR/BMSRCVAL──→ LB (context → result pointer)
BM ──BMBCOID──→ tBCO.object_id (links outside SDTM)
```

---

## DM — Demographics (§5.2 SDTMIG v3.4)

**Class:** Special-purpose. **Structure:** 1 record/subject.

### Core variables (from the Troponin I example)

| Variable | Core | Source | Notes |
|----------|------|--------|-------|
| STUDYID | Req | Study | BM-2026-01 in the example |
| DOMAIN | Req | Fixed | DM |
| USUBJID | Req | CRF | Unique across studies |
| SUBJID | Req | CRF | Site-local ID |
| SITEID | Req | CRF | — |
| AGE | Exp | CRF | — |
| AGEU | Exp | CRF | YEARS |
| SEX | Exp | CRF | M / F |
| COUNTRY | Exp | CRF | ISO 3166-1 alpha-3 |
| RFSTDTC | Exp | Derived | Reference start — study day 1 |

**Role in the record set model:** Demographics come from the CRF/study data, NOT from the BCOs. The record set model does not add new fields to DM. The rBCO identifies the patient (USUBJID, SUBJID, SITEID) but does NOT duplicate DM fields.

---

## LB — Laboratory Test Results (§6.3.5.6 SDTMIG v3.4)

**Class:** Findings (specimen-based). **Structure:** 1 record/result/value/timepoint/subject.

### Core variables

| Variable | Core | Prov. | Source in record set model |
|----------|------|-------|--------------------------|
| STUDYID | Req | S | Study |
| DOMAIN | Req | S | LB |
| USUBJID | Req | S | CRF → DM |
| LBSEQ | Req | S | Sequence (surrogate key) |
| LBTESTCD | Req | S | TNNI3 from CT |
| LBTEST | Exp | S | Troponin I cardiac muscle |
| LBCAT | Perm | S | e.g. BIOMARKER |
| LBMETHOD | Perm | S | **tBCO** `assay.method` → IMMUNOASSAY |
| LBSPEC | Perm | S | **tBCO** specimen → SERUM |
| LBBLFL | Perm | S | Baseline flag |
| **LBORRES** | **Exp** | **R** | Original result (censored: `<0.006`) |
| **LBORRESU** | **Exp** | **R** | **tBCO** reporting_convention.unit → ng/mL |
| **LBSTRESC** | **Exp** | **R** | Standardized char result |
| **LBSTRESN** | **Exp** | **R** | Numeric result (null if censored) |
| **LBSTRESU** | **Exp** | **R** | **tBCO** → ng/mL |
| LBSTNRHI | Perm | **T** | **tBCO** `reference_limits.upper` → 0.04 |
| LBSTNRC | Perm | **T** | Reference qualifier |
| LBLOINC | Perm | **T** | **tBCO** `assay.loinc_code` → 10839-9 |
| VISITNUM | Exp | S | Visit number |
| VISIT | Perm | S | Visit label |
| LBDTC | Exp | S | **rBCO** measurement collection date |
| LBDY | Perm | S | Study day |

**Provenance codes:** **T**=tBCO, **R**=rBCO / result, **K**=BiomarkerKB, **N**=new, **S**=study/CRF/derived

### Key rules from SDTMIG

- **LBTESTCD** must be ≤ 8 chars, from CDISC Controlled Terminology where available.
- **LBSTRESN** is null for censored results (LBORRES holds the censored value string).
- **LBSTNRHI/LBSTNRLO** are Qualifier variables — Permissible. Populated from tBCO `reference_limits`.
- **LBSPEC, LBMETHOD, LBLOINC** are populated from tBCO assay specification.
- Visit timing: VISITNUM, VISIT, LBDTC from the rBCO measurement records.

---

## SUPPLB — Supplemental Qualifiers for LB (§8.4 SDTMIG v3.4)

**Class:** Relationship. **Structure:** 1 row/qualifier/parent-record.

### Variables

| Variable | Core | Notes |
|----------|------|-------|
| STUDYID | Req | Study |
| RDOMAIN | Req | LB (the parent domain) |
| USUBJID | Req | Subject |
| IDVAR | Req | Parent variable to join on — `LBSEQ` (per-result) or `LBGRPID` (per-group) |
| IDVARVAL | Req | Value of IDVAR in parent |
| QNAM | Req | Qualifier name (≤8 chars, no special chars, same rules as --TESTCD) |
| QLABEL | Req | Qualifier label (≤40 chars) |
| QVAL | Req | Qualifier value (≤200 chars) |
| QORIG | Req | Origin — CRF, Derived, Assigned, or Protocol |
| QEVAL | Perm | Evaluator |

### Proposed qualifiers (from Troponin I Definitions sheet)

| QNAM | QLABEL | Keyed On | Provenance | Source |
|------|--------|----------|------------|--------|
| ASSAYNAM | Assay Name | LBGRPID | **T** | tBCO `assay.name` |
| ASSAYPLT | Assay Platform | LBGRPID | **T** | tBCO `assay.platform` |
| LBLOD | Limit of Detection | LBGRPID | **T** | tBCO `analytical_performance.limit_of_detection.value` |
| LBLLOQ | Lower Limit of Quantitation | LBGRPID | **T** | tBCO `analytical_performance.lower_limit_of_quantitation.value` |
| LBULOQ | Upper Limit of Quantitation | LBGRPID | **T** | tBCO `analytical_performance.upper_limit_of_quantitation.value` |
| RBCOID | Run BCO Object ID | LBGRPID | **R** | rBCO `object_id` |
| CENSOR | Censoring State | LBSEQ | **R** (derived) | Computed: `below_lod` / `detected_below_lloq` / `quantifiable` / `above_uloq` |

### Key SUPPLB rules from SDTMIG

- **IDVAR = LBGRPID** for assay-level qualifiers (same value for all timepoints of a subject).
- **IDVAR = LBSEQ** for per-result qualifiers (CENSOR).
- **QNAM** restrictions: 8 chars max, no starting digit, letters/numbers/underscore only. Same as --TESTCD.
- **QLABEL** max 40 chars.
- **QVAL** max 200 chars.
- **QORIG** for the proposed qualifiers: CRF (if entered), Derived (CENSOR), Assigned (RBCOID — from rBCO).
- **Do not use SUPPLB** when a standard LB variable exists for the data.

---

## BM — Biomarker Context (PROPOSED Domain)

**Not in SDTMIG v3.4.** Proposed by the PHUSE Omics working group. This is the *context layer* — if a biomarker claim is withdrawn, only BM rows vanish; every LB result remains.

### Proposed variables (26 columns)

| Variable | Core | Prov. | Source in record set model | Example value |
|----------|------|-------|--------------------------|---------------|
| STUDYID | Req | S | Study | BM-2026-01 |
| DOMAIN | Req | S | BM | BM |
| BMID | Req | N | Unique ID | BM-001 |
| BMVER | Req | N | Version | 1.0 |
| BMENTNM | Req | **K** | BiomarkerKB `assessed_biomarker_entity` | Troponin I cardiac muscle |
| BMENTID | Req | **K** | BiomarkerKB `assessed_biomarker_entity_id` | UPKB:P19429 |
| BMENTTP | Req | **K** | BiomarkerKB `assessed_entity_type` | protein |
| BMCVTERM | Req | **K** | BiomarkerKB `biomarker` | Increased level of protein TNNI3/UPKB:P19429 |
| BMROLE | Req | **K** | BiomarkerKB `best_biomarker_role` | MONITORING |
| BMCOND | Req | **K** | BiomarkerKB `condition` | Acute myocardial infarction |
| BMCONDID | Req | **K** | BiomarkerKB `condition_id` | DOID:5844 |
| BMASSAY | Req | **T** | tBCO `assay.name` | TnI-Ultra |
| BMNAM | Perm | **T** | tBCO `assay.manufacturer` | Siemens |
| BMPLAT | Perm | **T** | tBCO `assay.platform` | ADVIA Centaur XP |
| BMMETHOD | Perm | **T** | tBCO `assay.method` | IMMUNOASSAY |
| BMSPEC | Perm | **T** | tBCO `specimen_requirements.type` | SERUM |
| BMSRCDOM | Req | N | Source domain | LB |
| BMSRCVAR | Req | N | Source variable | LBTESTCD |
| BMSRCVAL | Req | N | Source value | TNNI3 |
| BMSRCVR2 | Perm | N | Secondary source var | ASSAYNAM |
| BMSRCVL2 | Perm | N | Secondary source val | TnI-Ultra |
| BMBCOID | Req | **T** | tBCO `object_id` | (tBCO ID) |
| BMRULE | Perm | **T** | tBCO `interpretation_rules` | Value > 0.04 ng/mL AND rise or fall >= 30% within 6 h |
| BMEVID | Perm | **K** | BiomarkerKB `evidence_source` | PMID:19710485 |
| BMASSRT | Perm | **S** | Study assessment | Sponsor Biomarker Review Board |
| BMASSDTC | Perm | **S** | Study date | 2026-09-01 |

**Provenance codes:** **T**=tBCO, **R**=rBCO / result, **K**=BiomarkerKB, **N**=new, **S**=study/CRF/derived

### Design rationale (from the reference example + SDTM expert review)
- BM does **not** carry subject ID, values, or dates — it is the context layer.
- BMSRCDOM/BMSRCVAR/BMSRCVAL point at the LB records (e.g., LB where LBTESTCD = TNNI3).
- BMSRCVR2/BMSRCVL2 provide a secondary pointer (assay qualifier).
- BMBCOID bridges outside SDTM to the tBCO record.
- BM is a *proposed* new domain. Until CDISC standardises it, submission as a custom domain (prefix X/Y/Z) may be needed.

---

## Censoring Logic (derived, per measurement)

SDTM does not define biomarker censoring states natively. The Troponin I example defines four zones via the CENSOR qualifier in SUPPLB:

| Censor state | Condition | LBORRES | LBSTRESN |
|-------------|-----------|---------|----------|
| `below_lod` | value < LoD | `<0.006` | null |
| `detected_below_lloq` | LoD ≤ value < LLOQ | `<0.03` | null |
| `quantifiable` | LLOQ ≤ value ≤ ULOQ | actual value | actual value |
| `above_uloq` | value > ULOQ | `>50` | null |

**Always derived, never entered.** Uses LoD/LLOQ/ULOQ from tBCO `analytical_performance`.

---

## Reverse Direction: SDTM → Record Set

The skill must also reconstruct the record set given SDTM domains:

1. **tBCO** from LB reference fields + SUPPLB assay qualifiers + BM assay info:
   - LBSTNRHI → `reference_limits.upper`
   - LBSPEC → `specimen_requirements.type`
   - LBMETHOD → `assay.method`
   - SUPPLB.ASSAYNAM → `assay.name`
   - SUPPLB.ASSAYPLT → `assay.platform`
   - SUPPLB.LBLOD/LBLLOQ/LBULOQ → `analytical_performance.*`
   - BM.BMRULE → `interpretation_rules`

2. **rBCO** from SUPPLB run qualifiers + LB visit/timing:
   - SUPPLB.RBCOID → rBCO `object_id`
   - LBDTC, VISITNUM, visit → measurement collection data
   - SUPPLB.CENSOR → `measurements[].censor_state`

3. **BiomarkerKB record** from BM:
   - BMENTNM → `assessed_biomarker_entity`
   - BMENTID → `assessed_biomarker_entity_id`
   - BMENTTP → `assessed_entity_type`
   - BMCVTERM → `biomarker`
   - BMROLE → `best_biomarker_role`
   - BMCOND / BMCONDID → `condition` / `condition_id`
   - BMEVID → `evidence_source`

## References

- SDTMIG v3.4 Final (2022-07-21) — ships with the skill as `references/sdtmig-v3.4.pdf`
- SDTM v2.1 Final (2024-06-07) — the model document; not shipped, available from CDISC
- Troponin I worked example: `examples/troponin_I/Troponin_I_SDTM.xlsx` (the Definitions sheet is the field dictionary)
