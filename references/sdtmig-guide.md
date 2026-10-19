---
doc: sdtmig-guide
version: 2.1.0
status: current
updated: 2026-10-19
source: CDISC SDTMIG v3.4 (DM, LB, SUPPLB, domain index) · Troponin_I_SDTM.xlsx Definitions sheet (BM)
---

# SDTM guide for the biomarker record set

## Contents

1. How to use this guide
2. Domain index: which domain holds which data (with PDF pages)
3. DM: Demographics
4. LB: Laboratory Test Results
5. SUPPLB: Supplemental Qualifiers for LB
6. BM: Biomarker Context (proposed)
7. Reverse mapping: SDTM → record set

## 1. How to use this guide

- **Sources of truth.** For every standard domain (DM, LB, SUPPLB and all of §2), the source is
  `references/sdtmig-v3.4.pdf`; this guide distils it. For the proposed BM domain the source is the
  Definitions sheet of `examples/troponin_I/Troponin_I_SDTM.xlsx`; §6 reproduces it.
- **Reading order.** Read §1 and §2 first to decide which domains the study needs, then only the
  section for each domain you need. To check one variable, search for it rather than reading on:
  `grep -n "LBLLOD" references/sdtmig-guide.md`.
- **The PDF.** Open `references/sdtmig-v3.4.pdf` only when this guide cannot answer the question,
  and read only the pages §2 lists (the Read tool takes a page range, e.g. pages 241-247 for LB).
  Never read the whole file (461 pages).
- **Provenance letters** used below: **T** tBCO · **R** rBCO / run · **K** BiomarkerKB record ·
  **N** new, proposed here · **S** study, CRF or derived.

## 2. Domain index

The converter writes DM, a specimen-based findings domain (LB by default; IS, GF, CP, BS or PC with
`--domain`), its SUPP dataset, and BM. Use this index to choose the findings domain, and to list the
context domains the biomarker's role needs (`best-definitions.md` §3); the converter does not write
those, so name them in the hand-over report. PDF page = printed page.

### Where the measurement itself belongs

| Measurement | Domain | PDF page |
|---|---|---|
| Clinical chemistry, haematology, immunoassay of a protein or metabolite in blood or urine | **LB** Laboratory Test Results | 241 |
| Nucleic-acid characteristics: variants, expression, copy number, methylation | **GF** Genomics Findings | 220 |
| Cell populations by flow or mass cytometry, cell phenotype | **CP** Cell Phenotype Findings | 199 |
| Anti-drug antibodies, immunogenicity | **IS** Immunogenicity Specimen Assessments | 228 |
| Organisms and their drug susceptibility | **MB** / **MS** Microbiology | 248 |
| Histopathology findings on tissue | **MI** Microscopic Findings | 263 |
| Drug or metabolite concentrations and PK parameters | **PC** / **PP** Pharmacokinetics | 267 |
| Specimen characteristics (volume, quality), not analyte results | **BS** Biospecimen Findings | 196 |
| ECG | **EG** | 185 |
| Imaging or physiology by body system | **CV** 286 · **MK** 290 · **NV** 294 · **OE** 298 · **RP** 305 · **RE** 308 · **UR** 312 | — |
| Tumour measurements and response | **TU** 344 · **TR** 350 · **RS** 329 | — |
| Vital signs | **VS** | 358 |
| Findings about an event or intervention | **FA** Findings About | 361 |
| Generic specimen-based variables (incl. --LLOQ, --ULOQ) | 6.3.5.1 | 194 |

### Context some BEST roles need

| Context | Domain | PDF page |
|---|---|---|
| Medical product given (predictive, safety, pharmacodynamic, monitoring of treatment) | **EX** Exposure / **EC** Exposure as Collected | 104 / 107 |
| Adverse events (safety) | **AE** | 133 |
| Condition events, e.g. the adjudicated diagnosis (diagnostic, prognostic outcomes) | **CE** Clinical Events | 148 |
| Pre-existing conditions (prognostic, susceptibility) | **MH** Medical History | 171 |
| Disposition and death (prognostic outcomes) | **DS** 155 · **DD** 183 | — |
| Specimen collection and handling events | **BE** Biospecimen Events | 143 |
| Visits actually attended | **SV** Subject Visits | 86 |
| Planned arms, elements, visits, trial summary | **TA** 384 · **TE** 402 · **TV** 407 · **TS** 417 | — |

### Cross-cutting rules

| Topic | Section | PDF page |
|---|---|---|
| Creating a new (custom) domain | 2.6 | 13 |
| Missing values | 4.2.5 | 29 |
| Original vs standardised results, tests not done | 4.5.1 | 51 |
| Baseline: --LOBXFL vs --BLFL | 4.5.9 | 59 |
| Time points (--TPT, --ELTM, --TPTREF) | 4.4.10 | 46 |
| --GRPID within a domain | 8.1 | 428 |
| RELREC (linking records, e.g. LB to AE) | 8.2 | 429 |
| Supplemental qualifiers, and when not to use them | 8.4, 8.4.4 | 432, 434 |
| Where data belong (choosing a class) | 8.6 | 435 |
| RELSPEC (related specimens) | 8.8 | 439 |

## 3. DM: Demographics (§5.2, p. 62)

One record per subject. Every value comes from the CRF or study data, never from a BCO.

| Variable | Core | Note |
|---|---|---|
| STUDYID, DOMAIN, USUBJID, SUBJID, SITEID | Req | DOMAIN = `DM` |
| AGE, AGEU | Exp | AGEU from CT (`YEARS`) |
| SEX | Req | `M`, `F`, `U`, `UNDIFFERENTIATED` |
| RACE / ETHNIC | Exp / Perm | Often absent from lab documents: leave empty and list it as unfilled |
| COUNTRY | Req | ISO 3166-1 alpha-3 |
| RFSTDTC | Exp | Reference start; anchors study day |
| RFXSTDTC | Exp | First exposure; needed to derive LBLOBXFL. Only applies when the study gives a product |
| ARM / ACTARM (and codes) | Exp | Needed for predictive biomarkers; leave out for observational studies |

## 4. LB: Laboratory Test Results (§6.3.5.6, p. 241)

One record per test per time point per visit per subject.

| Variable | Core | Prov. | Source / rule |
|---|---|---|---|
| STUDYID, DOMAIN, USUBJID | Req | S | DOMAIN = `LB` |
| LBSEQ | Req | S | Unique per subject; SUPPLB per-result rows point here |
| LBGRPID | Perm | T | Set to the assay so SUPPLB can carry assay-level facts once per subject |
| LBREFID | Perm | R | Specimen ID from the rBCO measurement |
| LBTESTCD | Req | T | ≤ 8 chars, letters/digits/underscore, not starting with a digit; from CDISC CT (LBTESTCD codelist) where a term exists. A gene symbol is not a test code |
| LBTEST | Req | T | ≤ 40 chars; CT (LBTEST) |
| LBTMTHSN | Perm | T | Test method sensitivity, e.g. `HIGH SENSITIVITY` for hs assays |
| LBCAT | Exp | S | e.g. `CHEMISTRY`, `HEMATOLOGY` |
| LBORRES, LBORRESU | Exp | R / T | Result as received; unit from the UNIT codelist |
| LBORNRLO, LBORNRHI | Exp | T | Reference range in original units |
| LBLLOD | Perm | T | **Lower limit of detection is a standard LB variable** |
| LBLLOQ, LBULOQ | Perm | T | Findings-class qualifiers (--LLOQ, --ULOQ, p. 194). LB assumption 5 allows any Findings-class qualifier to be added |
| LBSTRESC | Exp | S | Standardised character result (a censored value keeps its operator, e.g. `<0.006`) |
| LBSTRESN | Exp | S | Numeric standardised result; null when there is no number (`<0.006` below the LoD, `BLQ`). A value between the LoD and the LLOQ keeps its number |
| LBSTRESU | Exp | T | Standard unit |
| LBSTNRLO, LBSTNRHI, LBSTNRC | Exp / Perm | T | Reference range in standard units, from tBCO `reference_limits` |
| LBNRIND | Exp | S | `NORMAL`, `HIGH`, `LOW`, `ABNORMAL` against the reference range |
| LBSTAT, LBREASND | Perm | S | `NOT DONE` + reason when no result exists |
| LBNAM | Perm | T | Vendor or lab name |
| LBLOINC | Perm | T | tBCO `assay.loinc_code` |
| LBSPEC | Perm | T | CT (SPECTYPE), e.g. `SERUM`, `PLASMA` |
| LBMETHOD | Perm | T | The technique (`IMMUNOASSAY`), never the product name |
| LBLOBXFL | Exp | S | `Y` on the last non-missing value before RFXSTDTC, else null |
| LBBLFL | Perm | S | Sponsor-defined baseline, `Y` or **null** (never `N`); kept for backward compatibility |
| LBTOX, LBTOXGR | Perm | T | Toxicity grade, for safety biomarkers |
| VISITNUM | Exp | S | Numeric visit; from the rBCO measurement |
| VISIT | Perm | S | Visit label |
| LBDTC | Exp | R | Specimen collection date/time, ISO 8601 |
| LBDY | Perm | S | Study day from RFSTDTC |
| LBTPT, LBTPTNUM, LBELTM, LBTPTREF | Perm | S | Planned time points relative to a reference (dose, admission) |

The censor zones (`below_lod`, `detected_below_lloq`, `quantifiable`, `above_uloq`) and their
LBORRES/LBSTRESN values come from `scripts/censor_state.py` (table: `pitfalls.md` §1). Do not derive
them by hand.

## 5. SUPPLB: Supplemental Qualifiers for LB (§8.4, p. 432)

One row per qualifier per parent record. IDVAR/IDVARVAL point at the parent: `LBSEQ` for a
per-result fact, `LBGRPID` for a fact shared by a block of records.

| Variable | Core | Rule |
|---|---|---|
| STUDYID, RDOMAIN, USUBJID | Req | RDOMAIN = `LB` |
| IDVAR, IDVARVAL | Exp | Parent variable and its value |
| QNAM | Req | ≤ 8 chars, same character rules as --TESTCD |
| QLABEL | Req | ≤ 40 chars |
| QVAL | Req | Text, ≤ 200 chars |
| QORIG | Req | `CRF`, `Assigned`, `Derived`, `Protocol`, ... |
| QEVAL | Exp | Only for subjective values (e.g. `INVESTIGATOR`, `SPONSOR`, `VENDOR`) |

**Rule (§8.4.4, p. 434): do not use SUPPLB for data that a standard LB variable can hold.**

The project proposes four qualifiers (source: xlsx Definitions sheet). The assay limits are not
among them: they are the LB variables LBLLOD, LBLLOQ and LBULOQ (§4).

| QNAM | Keyed on | Prov. | Content |
|---|---|---|---|
| ASSAYNAM | LBGRPID | T | Assay trade name (tBCO `assay.assay_name`); LB has no variable for it |
| ASSAYPLT | LBGRPID | T | Instrument / analyser (tBCO `assay.platform`) |
| RBCOID | LBGRPID | R | rBCO `object_id`: the only link from a result to its run |
| CENSOR | LBSEQ | R | Censor zone, derived, never entered by hand |

## 6. BM: Biomarker Context (proposed; source: xlsx Definitions sheet)

Not in SDTMIG v3.4. One record per biomarker claim. BM carries no subject, value or date: if the
claim is withdrawn, only BM rows are deleted and every LB result stays. Until CDISC adopts it, a
submission may need it as a custom domain (§2.6, p. 13).

Join: `BM --BMSRCDOM / BMSRCVAR / BMSRCVAL--> LB`; `BMBCOID` points at the tBCO outside SDTM.

| Variable | Label | Prov. | Content |
|---|---|---|---|
| STUDYID | Study Identifier | S | |
| DOMAIN | Domain Abbreviation | S | Always `BM` |
| BMID | Biomarker Context Identifier | K | Identifier for this claim, cited by other records and documents |
| BMVER | Biomarker Context Version | N | Increments when the rule, role or population changes |
| BMENTNM | Entity Name | K | Name resolved from the accession via `assets/entity_names.json` |
| BMENTID | Entity Identifier | K | Entity CURIE (`assessed_biomarker_entity_id`), e.g. `UPKB:P19429` |
| BMENTTP | Entity Type | K | `assessed_entity_type`, as written in the BMKB record |
| BMCVTERM | Controlled Vocabulary Term | K | The BMKB `biomarker` statement, e.g. `Increased level of protein TNNI3/UPKB:P19429` |
| BMROLE | BEST Biomarker Role | K | `best_biomarker_role[].role`, uppercase. Only interpretable with BMCOND |
| BMCOND | Target Condition or Exposure | K | `condition.name` |
| BMCONDID | Condition Identifier | K | `condition.id` (DOID, MONDO, ...) |
| BMASSAY | Assay Profile Reference | T | `assay.assay_name`; thresholds do not transfer between assays |
| BMNAM | Assay Manufacturer | T | `assay.manufacturer` |
| BMPLAT | Assay Platform | T | `assay.platform` |
| BMMETHOD | Measurement Method | T | `assay.method`: the technique, never the product |
| BMSPEC | Specimen Type | T | `specimen_requirements.specimen_type` |
| BMSRCDOM | Source Domain | N | Domain holding the measurements, e.g. `LB` |
| BMSRCVAR | Source Identifying Variable | N | e.g. `LBTESTCD` |
| BMSRCVAL | Source Identifying Value | N | Must equal the LBTESTCD actually emitted |
| BMSRCVR2 | Source Identifying Variable 2 | N | Narrows the selection when several assays share a test code, e.g. `ASSAYNAM` |
| BMSRCVL2 | Source Identifying Value 2 | N | e.g. `TnI-Ultra` |
| BMBCOID | BioCompute Object Identifier | T | tBCO `object_id`; authoritative for the rule |
| BMRULE | Interpretation or Decision Rule | T | Human-readable rendering of the tBCO rule, with resolved values (`Value > 0.04 ng/mL AND rise or fall >= 30% within 6 h`) |
| BMEVID | Evidence Reference | K | PMID / DOI. The BMKB submission record carries none, so pass it with `--evidence` from the study documents |
| BMASSRT | Asserting Party | N | Who asserted the claim (from the context-of-use document) |
| BMASSDTC | Assertion Date | N | ISO 8601 date the claim was asserted |

One BM row per (biomarker, assay, role, condition): a record with two BEST roles gives two rows
(BM-001, BM-002), each with the BMRULE of the tBCO rule tagged with that role. Two assays for the same
analyte need two sets of rows.

## 7. Reverse mapping: SDTM → record set

| SDTM | Record set field |
|---|---|
| LB.LBSTNRHI / LBSTNRLO | tBCO `reference_limits[]` |
| LB.LBSPEC | tBCO `specimen_requirements.specimen_type` |
| LB.LBMETHOD / LBNAM / LBLOINC | tBCO `assay.method` / `assay.manufacturer` / `assay.loinc_code` |
| SUPPLB.ASSAYNAM / ASSAYPLT | tBCO `assay.assay_name` / `assay.platform` |
| LB.LBLLOD / LBLLOQ / LBULOQ (older files: SUPPLB.LBLOD / LBLLOQ / LBULOQ) | tBCO `analytical_performance.limit_of_detection` / `limit_of_quantitation` / `upper_limit_of_quantitation` `.value` |
| BM.BMRULE | tBCO `interpretation_rules[].expression` |
| SUPPLB.RBCOID | rBCO `object_id` |
| LB.LBREFID / VISIT / LBDTC | rBCO `measurements[].specimen_id` / `visit` / `collection_dtc` |
| SUPPLB.CENSOR | rBCO `measurements[].censor_state` |
| BM.BMENTID / BMENTTP / BMCVTERM | BMKB `biomarker_component[].assessed_biomarker_entity_id` / `assessed_entity_type` / `biomarker` |
| BM.BMROLE | BMKB `best_biomarker_role[].role` (lowercase) |
| BM.BMCOND / BMCONDID | BMKB `condition.name` (lowercase) / `condition.id` |
| BM.BMASSDTC | BMKB `provenance.date` |

BCOs and BMKB records are public-facing and never hold individual results or demographics, so the
reverse direction does not rebuild them. Also not rebuilt: BMEVID and BMASSRT (the BMKB record has
no field for them), and run and IFU detail SDTM never carried. `sdtm_to_record_set.py` prints this
list; repeat it in the hand-over report.
