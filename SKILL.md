---
name: biomarker-sdtm
description: >-
  Builds IEEE 2791 BioCompute Objects (tBCO + rBCO) and BiomarkerKB records
  for biomarker data, and converts between that record set and CDISC SDTM output
  (DM, LB, SUPPLB, BM). Use when the user asks to create, generate, or build a
  BioCompute Object, template or run BCO, BiomarkerKB record, or map biomarker
  data to or from an SDTM biomarker domain. Also use when asked to convert assay
  specification documents or patient lab results into structured BCO/BMKB JSON
  or SDTM tabular output.
license: MIT
metadata:
  author: GWU Mazumder Lab
  version: "0.3.0"
  repository: https://github.com/biocompute-objects/bco-rag
---

# Biomarker SDTM

Turns study documents (protocol, context of use, assay IFU, validation report, lab results,
demographics) into a **record set**: one template BCO (tBCO) per assay, one run BCO (rBCO) per
subject per analytical run, and one BiomarkerKB (BMKB) record. Converts the record set to SDTM (DM,
a findings domain such as LB, its SUPP dataset, BM) and back.

BCOs and BMKB records are public-facing: they never hold demographics or result values. Those live
only in the study-data intermediate (Step 6) and in the SDTM output.

**You author the JSON; the scripts do only the exact work** (strip annotations, etag, validation,
censor zones, accession table, SDTM conversion). The scripts never choose values. Run every command
from the skill root (`python scripts/<name>.py`). Needs Python 3.10+ and `pip install jsonschema`
(`validate_bco.py` fails without it). `README.md` and `CHANGELOG.md` are for human
maintainers; you do not need to read them.

## Route by task

Read only what the task needs. Read each reference in full the first time; every reference over
100 lines starts with a table of contents.

| Task | Read | Fill | Run | Gate |
|---|---|---|---|---|
| Write a tBCO | `references/bco-schema.md`, `examples/troponin_I/Troponin_I_tBCO.json` | `assets/tbco_template.json` | `finalize_draft.py`, `validate_bco.py` | Step 5 |
| Write rBCOs | `examples/troponin_I/Troponin_I_patient1_rBCO.json`, `references/pitfalls.md` §1 | `assets/rbco_template.json` | `censor_state.py`, `finalize_draft.py`, `validate_bco.py` | Step 5 |
| Write the BMKB record | `references/bmkb-model.md`, `references/best-definitions.md` (roles) | `assets/bmkb_template.json`, `assets/entity_names.json` | `biomarker_accessions.py`, OLS MCP server, `validate_bmkb.py` | Step 5 |
| Record set → SDTM | `references/sdtmig-guide.md` §1–2 first, then only the domain sections needed | `assets/study_data_template.json` | `record_set_to_sdtm.py` | Step 7 report |
| SDTM → record set | `references/sdtmig-guide.md` §7 | — | `sdtm_to_record_set.py`, then both validators | Reverse step 3 |
| Decide which SDTM domains apply | `references/sdtmig-guide.md` §2, `references/best-definitions.md` §3 | — | — | Report |
| Check whether a missing field blocks the run | `references/required-fields.md` | — | — | — |
| Diagnose an error | `references/pitfalls.md` §9 | — | — | — |

Open `references/sdtmig-v3.4.pdf` only when `sdtmig-guide.md` cannot answer the question, and read
only the pages its domain index (§2) lists, never the whole file. For the proposed BM domain the source of truth is
`sdtmig-guide.md` §6 (copied from the gold xlsx), not the PDF.

## Missing values

The source documents will not supply everything. Apply one rule everywhere:

- **Strings:** leave `"PLACEHOLDER"`. **Numbers:** `null`. Never invent a value, never copy a value
  from the example, and never use `0` as a stand-in.
- **Converter-critical fields stop the run.** If any of these is missing, ask the user before Step 6
  and do not convert until they answer: LoD, LLOQ and ULOQ; the reporting unit; the specimen type;
  the CDISC test code and name; the assay name; the condition; the BEST role; at least one evidence
  id; a result for every measurement. `record_set_to_sdtm.py` checks the same list and stops with
  every gap named. The full table is `references/required-fields.md`.
- **Everything else** is listed in the hand-over report (Step 7) as unfilled, grouped by file.
- Documents carry names, not identifiers. Deriving an accession (Step 4) is not inventing a value;
  guessing one is.

## Forward workflow: documents → record set → SDTM

### Step 1: Ingest

Collect, citing the document each value came from:

- **Assay specification:** analyte, assay name, manufacturer, platform, method, LoD/LLOQ/ULOQ,
  reference limits, specimen, LOINC, unit, sampling schedule, decision rule
- **Context of use:** condition, BEST role, asserting party and date, evidence citations
- **Lab results:** subject, visit, specimen id, collection time, result, unit
- **Demographics:** subject, site, age, sex, country, reference start date

Lab files rarely use SDTM names. Map their columns to the fields above yourself, and record the
mapping in the hand-over report.

### Step 2: Write the tBCO (one per assay)

Fill `assets/tbco_template.json`. Keys starting with `//_` are guidance for you; keep them while
drafting. Leave `etag` alone. Then:

```bash
python scripts/finalize_draft.py --input tBCO.draft.json --output tBCO.json
python scripts/validate_bco.py tBCO.json
```

Domains every BCO in this skill must carry:

- **Required by IEEE 2791** (a missing one fails `validate_bco.py`): `provenance_domain`,
  `usability_domain`, `description_domain`, `execution_domain`, `io_domain`, plus the root fields
  `object_id`, `spec_version`, `etag`
- **Optional in IEEE 2791 but required here** (a missing one also fails `validate_bco.py`):
  `error_domain`, `extension_domain` holding `assay_protocol_extension` (tBCO) or
  `assay_run_extension` (rBCO), and for a tBCO `parametric_domain`

Fill `target.lbtestcd` / `lbtest` with the CDISC Controlled Terminology test code and name for the
analyte (cardiac troponin I: `TROPONI3` / `Troponin I Type 3`), not a gene symbol. Give each
`interpretation_rules[]` entry the BEST `role` it supports and a `display` text with the values
filled in; that text becomes BM.BMRULE.

### Step 3: Write one rBCO per subject per analytical run

Fill `assets/rbco_template.json` for each subject and run; `provenance_domain.derived_from` is the
tBCO `object_id`. It records how the run went and each specimen's id, visit, collection time and
censor state; never the result value or any demographic. Set `censor_state` with the module, never
by eye:

```bash
PYTHONPATH=scripts python -c "from censor_state import resolve_censor_state as r; print(r(0.021, 0.006, 0.03, 50.0))"
# detected_below_lloq
```

`make_sdtm_fields(state, value, lod, lloq, uloq)` returns the matching LBORRES/LBSTRESN pair. The
zone table is in `references/pitfalls.md` §1. Finalize and validate each rBCO as in Step 2.

### Step 4: Write the BMKB record

Fill `assets/bmkb_template.json`. Replace every value in it from the study documents; the
pre-filled values are the troponin example, not defaults. It is a provider-side submission: never
emit the fields BiomarkerKB assigns (`biomarker_id`, `biomarker_canonical_id`, `*_md5`,
`biomarker_id_new`, `source_list`).

- **Condition:** the study's condition from the context-of-use document; `id` a DOID, MONDO or NCIT
  CURIE; `name` lowercase; `resource` the ontology name.
- **Roles:** follow `references/best-definitions.md` §2: take them from what the documents claim,
  list every supported role, and never infer one from the sampling pattern. Check each against the
  per-role requirements in §3.
- **Entity:** pick a lowercase `assessed_entity_type`, then the resource chain:

  ```bash
  python scripts/biomarker_accessions.py      # entity type → CURIE prefixes, * = on OLS
  ```

  Look identifiers up **only through the OLS MCP server**. Convert the term id to a CURIE (a
  Protein Ontology `PR_P19429` is `UPKB:P19429`); `curie_from_ols()` does it. If OLS has no entry,
  leave the id PLACEHOLDER and report it; never guess one. If the OLS server is not connected, tell
  the user. Rules: `references/bmkb-model.md` §6–7. Write the `biomarker` statement as
  `{change} {aspect} of {entity_type} {symbol}/{CURIE}`, e.g.
  `Increased level of protein TNNI3/UPKB:P19429`.
- **Name cache:** add `"<accession exactly as in assessed_biomarker_entity_id>": "<entity name>"` to
  `assets/entity_names.json`. Without it BM.BMENTNM comes out empty.

```bash
python scripts/validate_bmkb.py BMKB.json
```

There is no etag, so no finalize step.

### Step 5: Validation gate (before any conversion)

```bash
python scripts/finalize_draft.py --check --input tBCO.json      # repeat for each rBCO
python scripts/validate_bco.py tBCO.json rBCO_*.json
python scripts/validate_bmkb.py BMKB.json
```

Fix every FAIL and every missing required-here domain, then run the gate again. Continue only when
everything passes and every converter-critical field (see "Missing values") is filled.

### Step 6: Convert the record set to SDTM

1. **Choose the domains.** Use `references/sdtmig-guide.md` §2 to find where the measurement belongs
   (LB for chemistry and immunoassay; IS, GF, CP, BS or PC by `--domain`; anything else is out of
   the converter's reach). Use `references/best-definitions.md` §3 for the context domains each role
   needs (EX, AE, CE, ...). Tell the user about any domain the converter will not write before you
   convert.
2. **Build the study data.** Fill `assets/study_data_template.json` from the lab and demographics
   files: demographics, each result exactly as reported (matched on subject and specimen id), and
   the claim (ids, asserting party, date, evidence citations from the context of use or protocol).
3. **Convert:**

   ```bash
   python scripts/record_set_to_sdtm.py --tbco tBCO.json --rbco rBCO_*.json \
     --bmkb BMKB.json --study-data study_data.json --output-dir ./sdtm
   ```

   It stops with a list if a converter-critical field is missing or a result contradicts its censor
   state. Output: `DM.tsv`, `LB.tsv` (or the chosen domain), `SUPPLB.tsv`, `BM.tsv` (one row per
   BEST role).

### Step 7: Hand-over report

Give the user, in this order:

1. Files written and validator results
2. Unfilled fields (PLACEHOLDER or null), by file
3. Column mapping used for the lab files (Step 1)
4. Accessions resolved and where each was looked up
5. Domains the study needs beyond what was written (Step 6), and that BM is a proposed domain
6. Expected SDTM variables left empty, and why (`references/required-fields.md` §6)

## Reverse workflow: SDTM → record set

1. Convert:

   ```bash
   python scripts/sdtm_to_record_set.py --lb sdtm/LB.tsv --supp sdtm/SUPPLB.tsv \
     --bm sdtm/BM.tsv --output-dir ./reconstructed
   ```

   It writes one tBCO, one rBCO per subject and run, and the BMKB record, already finalized. It
   does not rebuild results or demographics: they never belong in BCOs.
2. Gate: run `validate_bco.py` on the BCOs and `validate_bmkb.py` on the BMKB record.
3. Ask the user for the PLACEHOLDER fields that matter to them (contributors, licence, run detail).
4. If the original record set is available, compare it field by field. Differences in key order or
   template layout are acceptable. Differences in condition, entity, role, limits, censor states or
   measurement timing are errors.
5. Report what could not be reconstructed (the list the script prints) and every PLACEHOLDER left.

## Worked example: Troponin I

`examples/troponin_I/` holds human-validated outputs: `Troponin_I_tBCO.json`, one rBCO for each of
two subjects, `Troponin_I_biomarkerKB.json` and `Troponin_I_SDTM.xlsx`. Its inputs are the simulated
documents in `fixtures/troponin_I/`. Match its shape, not its values: TnI-Ultra on ADVIA Centaur XP,
LoD 0.006 / LLOQ 0.03 / ULOQ 50 ng/mL, 99th percentile 0.04 ng/mL, acute myocardial infarction
(DOID:5844), roles diagnostic and prognostic.

Never write into `examples/`. Put test output in a scratch directory or `fixtures/<name>/_output/`.

## Checks

```bash
python scripts/run_checks.py     # every self-test plus a comparison against the gold example
```

Exit code 0 means everything passed.

## Files

```
SKILL.md                this file
references/             read on demand (see "Route by task")
  sdtmig-guide.md       SDTM domain index + DM, LB, SUPPLB, BM, reverse mapping
  sdtmig-v3.4.pdf       full SDTMIG; open at the pages sdtmig-guide.md lists
  bmkb-model.md         BiomarkerKB submission schema + accession rules
  best-definitions.md   FDA-NIH BEST biomarker roles
  bco-schema.md         IEEE 2791 field reference
  pitfalls.md           censor zones, traps, troubleshooting
  required-fields.md    what each field is required by, and what to do when it is missing
  schemas/              IEEE 2791 JSON Schemas (used by validate_bco.py)
scripts/                run, do not edit
assets/                 templates you fill (tBCO, rBCO, BMKB, study data) + entity_names.json cache
examples/               validated gold outputs (read-only)
fixtures/               simulated input documents
README.md, CHANGELOG.md for human maintainers
```
