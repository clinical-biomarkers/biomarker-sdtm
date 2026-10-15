---
doc: pitfalls
version: 1.0.0
status: current
updated: 2026-10-15
source: project experience
---

# Pitfalls & Edge Cases — biomarker-sdtm Skill

> Common traps, gotchas, and edge cases the skill must avoid.
> Cross-referenced against the record set (tBCO + rBCO + BMKB) and SDTM output.

---

## 1. Censoring Confusion

### Mixing LOD vs LLOQ (most common error)

Four distinct censoring zones exist — the wrong zone produces an invalid SDTM record:

| Zone | LBORRES (example) | LBSTRESN | Condition | Source |
|------|-------------------|----------|-----------|--------|
| `below_lod` | `<0.006` | null | value < LoD | tBCO `analytical_performance.limit_of_detection` |
| `detected_below_lloq` | `<0.03` | null | LoD ≤ value < LLOQ | tBCO `analytical_performance.limit_of_quantitation` |
| `quantifiable` | `0.08` | `0.08` | LLOQ ≤ value ≤ ULOQ | — |
| `above_uloq` | `>0.30` | null | value > ULOQ | tBCO `analytical_performance.upper_limit_of_quantitation` |

**Rule:** Always query the tBCO's `analytical_performance` object for LoD/LLOQ/ULOQ before assigning a censor state. Never hard-code thresholds.

**Edge case:** If LoD = LLOQ (some assays), the `below_lod` and `detected_below_lloq` zones collapse — the skill should still use the correct named zone based on what the tBCO declares.

### Censor state not in controlled vocabulary

Valid values: `below_lod`, `detected_below_lloq`, `quantifiable`, `above_uloq`. Anything else (e.g. `BLQ`, `BLOQ`, `<LLOQ`) is non-standard, and `censor_state` rejects it rather than guessing at the zone.

### Numeric value assigned to censored LBSTRESN

When LBORRES is `<0.006`, LBSTRESN **must** be null. A common error is to assign 0 or 0.006. Only `quantifiable` values get a numeric LBSTRESN.

---

## 2. Unit Ambiguity

### Same biomarker, different units

Troponin I can be reported in ng/mL or μg/L (they are numerically identical for Troponin I, but not all assays). Other biomarkers may have assays that differ by a factor of 1000 (ng/mL vs μg/mL).

**Rule:** Always capture the tBCO's `reporting_convention.unit` and propagate it to:
- `LBORRESU`, `LBSTRESU` in LB
- `BMRULE` text (e.g. "Value > 0.04 ng/mL")

If two assays report the same biomarker in different units, they **must** be separate tBCOs (different `assay.name`) and separate BM domain rows.

### Unit abbreviation inconsistency

Same unit spelled differently: "ng/mL" vs "ng/ml" vs "ng per mL". SDTM requires a controlled unit (UCUM preferred, or CDISC codelist). The skill should normalise to the CDISC/UCUM standard form from the tBCO.

---

## 3. Assay Non-Harmonisation

### Different assays have different reference limits

Two Troponin I assays (e.g. Siemens TnI-Ultra vs Abbott Architect STAT) have:
- Different LoD, LLOQ, ULOQ
- Different 99th percentile upper reference limits (0.04 ng/mL vs 0.026 ng/mL)
- Possibly different units

**Rule:** Every LB row that shares the same `LBTESTCD` but comes from a **different assay** needs a distinct BM row with a different `BMASSAY` value. The BM domain row is the **assay-level** context.

### Mixing assays in the same BM row

Never assign measurements from two different assay platforms to the same BM `BMBCOID`. Each tBCO → one BM row.

### Plate-to-plate or lot-to-lot variation

If reference limits drift across manufacturing lots, the tBCO should carry the **current/latest** IFU values. Historical lots are not represented in the record set model (the skill should note this limitation).

---

## 4. BM Domain Pitfalls

### BM vs LB: what goes where

Domain rule: **BM is context — LB is data.** Never put:
- Subject-level values in BM (they belong in LB)
- Visit dates, subject IDs, or result flags in BM
- LB metadata belongs in the BM domain (which provides the assay-level context for multiple LB rows)

### BM proposed, not standard

The BM domain is **not yet in SDTMIG**. It's a PHUSE Omics working group proposal. Until CDISC standardises it, submission may require a custom domain prefix (X/Y/Z). The skill should note this in its output.

### Provenance code misassignment

26 BM columns each have a provenance code (T/R/K/N/S). Common errors:
- Assigning **K** (BiomarkerKB) to fields that should be **T** (tBCO) — e.g. `BMASSAY` (assay name) comes from the tBCO, not the KB
- Assigning **N** (new) when the value is actually derived from another source
- Leaving provenance off entirely

Correct map (from `sdtmig-guide.md` §BM):

| Prov. | Source | Example fields |
|-------|--------|----------------|
| **T** | tBCO | BMASSAY, BMNAM, BMPLAT, BMMETHOD, BMSPEC, BMBCOID, BMRULE |
| **K** | BiomarkerKB | BMENTNM, BMENTID, BMENTTP, BMCVTERM, BMROLE, BMCOND, BMCONDID, BMEVID |
| **N** | New/assigned | BMID, BMVER, BMSRCDOM, BMSRCVAR, BMSRCVAL, BMSRCVR2, BMSRCVL2 |
| **S** | Study/CRF | BMASSRT, BMASSDTC |
| **R** | rBCO/result | — |

### BMSRCDOM/BMSRCVAR pointing at wrong LB record

The source linkage must match exactly: e.g. `BMSRCDOM=LB, BMSRCVAR=LBTESTCD, BMSRCVAL=TNNI3`. If the LB test code in the data is `TROP` instead of `TNNI3`, the BM source pointer must match.

---

## 5. BiomarkerKB Record Pitfalls

### The condition must come from the study context

Use the condition the study is actually about (e.g. acute myocardial infarction,
`DOID:5844`) — never one inherited from a template or borrowed from the example record.
Check it before it reaches the BM domain rather than copying it through.

### Emitting fields BiomarkerKB assigns itself

The record is **provider-side**. It must not contain the fields BiomarkerKB mints on receipt:
`biomarker_id`, `biomarker_canonical_id`, `biomarker_id_md5`, `canon_id_md5`,
`biomarker_id_new`, `source_list`. Emitting your own copies asserts identifiers only the
receiving system is entitled to assign. `validate_bmkb.py` rejects them.

### `biomarker_component` is exactly five fields

`component_index`, `entity_index`, `assessed_biomarker_entity_id`, `assessed_entity_type`,
`biomarker`. Earlier API responses also carried a nested `biomarker_component_new[]` and
per-component `evidence_source`, `annotations`, `specimen`, `biomarker_orig` and
`assessed_biomarker_entity_url`. **None of those are in the submission schema** — do not emit
them. The entity *name* is not carried either: resolve it from the accession.

### The record carries no evidence

The submission record has **no** `evidence_source`. A biomarker assertion's evidence ids
(e.g. `PMID:19710485`) come from the **study documents** — context-of-use and protocol
citations — and are passed to the SDTM conversion with `--evidence`. Do not expect to read
them back out of the BMKB record.

### Normal ranges vs tBCO reference limits

BMKB `entity_normal_ranges` are age/sex-stratified population norms. tBCO `analytical_performance.reference_limits` are assay-specific cutoffs. **These are different things.** Never populate tBCO reference limits from BMKB normal ranges.

### BMCVTERM field

The `biomarker` field in BMKB (mapped to BM.BMCVTERM) is a descriptive statement like "Increased level of protein TNNI3/UPKB:P19429". This is **not** the same as the biomarker test code (LBTESTCD). Keep them separate.

---

## 6. tBCO / rBCO Pitfalls

### PLACEHOLDER fields

The Troponin I example has `PLACEHOLDER` in many fields (manufacturer, lot number, IFU version). These must be filled from the actual assay documentation. The skill should:
1. Flag unpopulated PLACEHOLDER fields
2. Prompt for the manufacturer's IFU or published literature values
3. Never output PLACEHOLDER in a production BCO

### Missing analytical_performance block

Every tBCO must have an `analytical_performance` object with at minimum: LoD, LLOQ, ULOQ, and reference limits. Without these, censoring logic cannot execute.

### rBCO derivation chain

Each rBCO records `derived_from` (the tBCO `object_id`) and `usability_domain[].xref` (the SDTM dataset). If the tBCO is updated (new version), existing rBCOs still reference the old version — the skill should handle this via BCO versioning, not in-place edits.

---

## 7. SDTM Output Pitfalls

### LBTESTCD length limit

`LBTESTCD` is limited to 8 characters (SDTM rule). Troponin I maps to `TNNI3` (5 chars) — safe. But if a biomarker test code exceeds 8 chars, it must be abbreviated and the full name recorded in `LBTEST`.

### Controlled terminology

`LBTESTCD`, `LBSPEC`, `LBMETHOD`, `LBSTRESU` are expected to use CDISC Controlled Terminology where available. Custom values (e.g. `SERUM` is fine, but `BLOOD_SERUM` may not be) should be flagged.

### Multiple timepoints per subject

A single subject may have multiple Troponin I measurements (t0, t3h, t6h). Each gets:
- A separate rBCO (one per collection timepoint)
- A separate LB row
- The same BM row (BM is assay-level, not timepoint-level)

### DM linkage

Every LB/SUPPLB/BM record must join to DM via `STUDYID + USUBJID`. The skill must ensure DM is always included in the SDTM output.

---

## 8. General / Workflow Pitfalls

### Schema version drift

The IEEE 2791 BCO schema may update. The skill's reference copy (`references/bco-schema.md`) must be periodically reconciled with the live version at `w3id.org/ieee/ieee-2791-schema/2791object.json`.

### Assumption of STANDARD assay_type

The Troponin I example uses `assay_type = "STANDARD"`. If a different type is encountered (e.g., "RNA_SEQ"), the record set model may need different fields. The skill should handle unrecognised assay types gracefully.

### Reversibility (SDTM → Record Set)

Not all information survives the forward transformation into SDTM (e.g., the censoring zone name lives in `SUPPLB.CENSOR` but the LoD/LLOQ/ULOQ thresholds themselves are not represented in SDTM). The reverse transform may produce a degraded record set. The skill should document which fields are lossy.

---

*See also: `sdtmig-guide.md` (censoring logic, BM domain, join paths), `bmkb-model.md` (BMKB caveats), `best-definitions.md` (prognostic vs predictive), `bco-schema.md` (field validation).*
