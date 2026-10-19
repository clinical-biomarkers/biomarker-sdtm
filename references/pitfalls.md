---
doc: pitfalls
version: 2.1.0
status: current
updated: 2026-10-19
source: project experience · SDTMIG v3.4 (standard domains) · Troponin_I_SDTM.xlsx (BM)
---

# Pitfalls and troubleshooting

## Contents

1. Censoring (the one censor-zone table)
2. Units
3. Assay non-harmonisation
4. BM domain
5. BiomarkerKB record
6. tBCO / rBCO
7. SDTM output
8. Round trip (SDTM → record set)
9. Troubleshooting: error → cause → fix

---

## 1. Censoring

`scripts/censor_state.py` decides the zone and the SDTM fields. Never assign a zone by eye.

| Zone | Condition | LBORRES (LoD 0.006, LLOQ 0.03, ULOQ 50) | LBSTRESN |
|---|---|---|---|
| `below_lod` | value < LoD | `<0.006` | null |
| `detected_below_lloq` | LoD ≤ value < LLOQ | `0.021` (the value as reported) | `0.021` |
| `quantifiable` | LLOQ ≤ value ≤ ULOQ | `0.058` | `0.058` |
| `above_uloq` | value > ULOQ | `>50` | null |

- The thresholds come from tBCO `analytical_performance` (`limit_of_detection`,
  `limit_of_quantitation`, `upper_limit_of_quantitation`). Never hard-code them.
- Write only these four values. `measurable` is accepted on input as a synonym of
  `quantifiable`; `BLQ`, `BLOQ`, `<LLOQ` and `not_detected` are rejected.
- Below the LoD and above the ULOQ, LBSTRESN is null: never 0 and never the limit itself.
- Between the LoD and the LLOQ the result keeps its number (project policy); SUPPLB.CENSOR =
  `detected_below_lloq` tells readers it is not quantifiable.
- The converter checks each reported result against its rBCO `censor_state` and stops on a mismatch.
- If LoD = LLOQ, the `detected_below_lloq` zone is empty. Still use the zone names the tBCO
  thresholds produce.

## 2. Units

- Take the unit from tBCO `reporting_convention.unit` and use it in LBORRESU, LBSTRESU and in
  the BMRULE text (`Value > 0.04 ug/L`).
- LBORRESU/LBSTRESU use the CDISC UNIT codelist. Mathematically equal units map to the one CDISC
  submission value (SDTMIG LB assumption 7): `ng/mL` is written `ug/L` in both, and in the tBCO.
  `python scripts/cdisc_ct.py check UNIT <unit>` gives the submission value.
- Two assays that report the same analyte in different units are two tBCOs and two BM rows.

## 3. Assay non-harmonisation

- Different assays for one analyte have different LoD/LLOQ/ULOQ and reference limits (TnI-Ultra
  99th percentile 0.04 ug/L; Abbott Architect STAT 0.026 ug/L). Thresholds never transfer.
- One tBCO per assay; one BM row per tBCO (and per role/condition). Never point one BM row at two
  assays.
- If limits change between reagent lots, the tBCO carries the IFU values in force; say in the
  report that earlier lots are not represented.

## 4. BM domain

The variable list and provenance letters are in `sdtmig-guide.md` §6, the only copy.

- BM is context, LB is data. BM holds no subject IDs, results, visits or dates of measurement.
- BMSRCDOM / BMSRCVAR / BMSRCVAL must select the LB records exactly: BMSRCVAL equals the
  LBTESTCD actually emitted.
- BMMETHOD is the technique (`IMMUNOASSAY`); the product name goes in BMASSAY.
- BMRULE renders the tBCO rule with resolved values (`Value > 0.04 ug/L AND rise or fall >= 30%
  within 6 h`), not the template's generic expression.
- BM is not in SDTMIG v3.4. Say in the hand-over that it may need to be submitted as a custom
  domain.

## 5. BiomarkerKB record

- **Condition.** Use the condition the study is about (from the context-of-use document), never
  the one in the template or the example.
- **No BiomarkerKB-assigned fields.** Never emit `biomarker_id`, `biomarker_canonical_id`,
  `biomarker_id_md5`, `canon_id_md5`, `biomarker_id_new` or `source_list`. `validate_bmkb.py`
  rejects them.
- **`biomarker_component` has exactly five fields:** `component_index`, `entity_index`,
  `assessed_biomarker_entity_id`, `assessed_entity_type`, `biomarker`. Do not emit
  `biomarker_component_new`, `evidence_source`, `annotations`, `specimen`, `biomarker_orig`,
  `assessed_biomarker_entity_url` or an entity name.
- **No evidence in the record.** Evidence ids (`PMID:19710485`) come from the study documents and go
  to the converter with `--evidence`.
- **Normal ranges are not reference limits.** `entity_normal_ranges` are population norms; tBCO
  `reference_limits` are assay cut-offs. Never fill one from the other.
- **The `biomarker` statement is not a test code.** `Increased level of protein TNNI3/UPKB:P19429`
  goes to BMCVTERM; LBTESTCD is a CDISC test code.

## 6. tBCO / rBCO

- **Missing values** follow the policy in `SKILL.md` ("Missing values"): strings `PLACEHOLDER`,
  numbers `null`, and converter-critical fields stop the run and are asked for.
- **`analytical_performance` is mandatory for conversion.** Without LoD, LLOQ and ULOQ no censor
  zone can be computed.
- **Versioning.** Each rBCO's `provenance_domain.derived_from` names the tBCO `object_id`. When the
  assay specification changes, issue a new tBCO version; never edit a released tBCO in place.

## 7. SDTM output

- **LBTESTCD** comes from CDISC Controlled Terminology (LBTESTCD codelist), ≤ 8 characters, no
  leading digit. A gene symbol (`TNNI3`) is not a lab test code; look up the CT term for the
  analyte and keep the full name in LBTEST (≤ 40 characters).
- **CT everywhere it exists:** LBTEST, LBSPEC (SPECTYPE), LBMETHOD, LBORRESU/LBSTRESU (UNIT).
  Flag any value that is not a CT term.
- **Baseline.** LBBLFL is `Y` or null, never `N`. LBLOBXFL (Expected) flags the last value before
  RFXSTDTC; with no exposure in the study, leave it null.
- **Limits belong in LB.** LoD, LLOQ and ULOQ are written to LBLLOD, LBLLOQ and LBULOQ, never to
  SUPPLB (SDTMIG §8.4.4).
- **Multiple timepoints per subject.** A subject measured at 0 h, 3 h and 6 h in one analytical run
  has one rBCO (one per subject per analytical run) holding three measurements, three LB rows, and
  shares the BM rows with every other subject (BM is assay-level).
- **Joins.** LB and SUPPLB join DM on STUDYID + USUBJID. BM has no USUBJID; it joins LB through
  BMSRCDOM/BMSRCVAR/BMSRCVAL. Always include DM.
- **Other domains.** If the biomarker is genomic, cellular, microbiological, histological or a drug
  concentration, its results do not belong in LB. Check the domain index in `sdtmig-guide.md` §2.

## 8. Round trip (SDTM → record set)

- The thresholds (LB limits) and the censor zones (SUPPLB.CENSOR) survive. One rBCO is rebuilt per
  subject per run.
- Result values and demographics are not rebuilt: BCOs and BMKB records are public-facing and never
  hold individual-level data. This loss is expected.
- Also lost: BMEVID and BMASSRT (no BMKB field), instrument, lot, calibration and QC detail. The
  reverse output marks them `PLACEHOLDER`; list them in the hand-over.
- The IEEE 2791 schema may change. Reconcile `references/schemas/` with
  `https://w3id.org/ieee/ieee-2791-schema/2791object.json` when you bump the spec version.

## 9. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `validate_bco.py` FAIL | Missing domain, missing required field, or malformed etag | Read the reported check. Required domains are listed in `SKILL.md` Step 2. Re-run `finalize_draft.py` after any hand edit |
| `finalize_draft.py --check` MISMATCH | Content changed after the etag was computed | `python scripts/finalize_draft.py --input <file>`, then `--check` again |
| Censor state rejected | A non-standard term (`BLQ`, `<LLOQ`, `not_detected`) | Use the four zones in §1; let `resolve_censor_state()` decide |
| Numeric LBSTRESN below the LoD or above the ULOQ | The zone was not applied | `make_sdtm_fields()` returns the pair; only those two zones get a null |
| Converter: "result ... is X against the tBCO limits, but the rBCO says Y" | The rBCO censor_state was set by eye or with other limits | Recompute it with `resolve_censor_state()` |
| Converter: "cannot convert; fill these first" | A converter-critical field is unfilled | See `required-fields.md`; ask the user for each item listed |
| `validate_bmkb.py`: "template guidance keys left in the record" | The `//_` keys were not stripped | `finalize_draft.py --input <draft> --output BMKB.json --no-etag` |
| `validate_bmkb.py` FAIL on entity type | Type outside the allowed set or wrong case | `python scripts/biomarker_accessions.py` prints the table |
| Wrong accession | Resource chosen by guess | `accession_resource_for(<type>)`; confirm the id resolves before using it |
| BM.BMEVID empty | No `--evidence` given (the record carries none by design) | Pass `--evidence PMID:...` from the context-of-use or protocol |
| BM.BMENTNM empty | The accession has no entry in `assets/entity_names.json` | Add `"<accession exactly as in the record>": "<name>"` and re-run |
| BM provenance letter disputed | Copies drifted | `sdtmig-guide.md` §6 is the only table |
| "jsonschema not available" | Package missing; `validate_bco.py` fails every file without it | `pip install jsonschema` |
| SCHEMA `Additional properties are not allowed` | A key the IEEE 2791 schema does not define (e.g. `mediatype` in io_domain, `unit` in parametric_domain) | Remove it or move it to `extension_domain`; never edit `references/schemas/` |
