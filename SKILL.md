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
  version: "0.2.0"
  repository: https://github.com/biocompute-objects/bco-rag
---

# Biomarker SDTM

Turns study documents (protocol, context of use, assay IFU, validation report, lab results,
demographics) into a **record set**: one template BCO (tBCO) per assay, one run BCO (rBCO) per
patient, and one BiomarkerKB (BMKB) record. Converts the record set to SDTM (DM, LB, SUPPLB, BM) and
back.

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
| Write the BMKB record | `references/bmkb-model.md`, `references/best-definitions.md` (role) | `assets/bmkb_template.json`, `assets/entity_names.json` | `biomarker_accessions.py`, `validate_bmkb.py` | Step 5 |
| Record set → SDTM | `references/sdtmig-guide.md` §1–2 first, then the domain sections | `results.json`, `dm.json` | `record_set_to_sdtm.py` | Step 7 report |
| SDTM → record set | `references/sdtmig-guide.md` §7 | — | `sdtm_to_record_set.py`, then both validators | Reverse step 3 |
| Decide which SDTM domains apply | `references/sdtmig-guide.md` §2 (domain index) | — | — | Report |
| Diagnose an error | `references/pitfalls.md` §9 | — | — | — |

Open `references/sdtmig-v3.4.pdf` only when `sdtmig-guide.md` cannot answer the question, and only
at the page its domain index (§2) lists. For the proposed BM domain the source of truth is
`sdtmig-guide.md` §6 (copied from the gold xlsx), not the PDF.

## Missing values

The source documents will not supply everything. Apply one rule everywhere:

- **Strings:** leave `"PLACEHOLDER"`. **Numbers:** `null`. Never invent a value, never copy a value
  from the example, and never use `0` as a stand-in.
- **Converter-critical fields stop the run.** If any of these is missing, ask the user before Step 6
  and do not convert until they answer: LoD, LLOQ and ULOQ; the reporting unit; the specimen type;
  the condition; the BEST role; at least one evidence id.
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
- **Optional in IEEE 2791 but required here** (a missing one is only a `NOTE:` line in the validator
  output, so check for it yourself): `parametric_domain`, `error_domain`, `extension_domain`
  holding `assay_protocol_extension` (tBCO) or `assay_run_extension` (rBCO)

### Step 3: Write one rBCO per patient

Fill `assets/rbco_template.json` for each subject; `provenance_domain.derived_from` is the tBCO
`object_id`. Set each measurement's `censor_state` with the module, never by eye:

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

- **Condition:** the study's condition from the context-of-use document; `id` is a DOID, MONDO,
  SNOMED or NCIt CURIE; `name` lowercase; `resource` names the ontology.
- **Role:** choose from the BEST definitions in `references/best-definitions.md` using the
  context-of-use statement. List every role the document asserts.
- **Entity:** pick `assessed_entity_type`, then get the accession resource:

  ```bash
  python scripts/biomarker_accessions.py      # prints entity type → resource chain
  ```

  Look the accession up in that resource; never guess it. Write the `biomarker` statement as
  `{change} {aspect} of {entity_type} {symbol}/{entity_id}`, e.g.
  `Increased level of protein TNNI3/UPKB:P19429` (rules: `references/bmkb-model.md` §6–7).
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

First check `references/sdtmig-guide.md` §2: if the biomarker's results belong in a domain other than
LB (genomic → GF, cell phenotype → CP, drug concentration → PC, ...) or its role needs context
domains (EX, AE, CE, ...), tell the user before converting. The converter writes only DM, LB, SUPPLB
and BM.

Build the two input files from the lab results and demographics:

```json
{"results": [{"idvarval": 1, "lborres": "0.021", "lbstresc": "0.021", "lbstressn": 0.021, "visitnum": 1, "visit": "ADMISSION"}]}
```

```json
{"dm": [{"usubjid": "BM-2026-01-001", "subjid": "001", "siteid": "01", "age": 67, "ageu": "YEARS", "sex": "M", "country": "DEU", "rfstdtc": "2026-03-15"}]}
```

`idvarval` matches the rBCO measurement's `idvarval`. Then:

```bash
python scripts/record_set_to_sdtm.py --tbco tBCO.json --rbco rBCO_patient1.json \
  --bmkb BMKB.json --results results.json --dm dm.json \
  --evidence PMID:19710485 --output-dir ./sdtm
```

`--evidence` takes the citations from the context-of-use or protocol (comma-separated); the BMKB
record carries none. Output: `DM.tsv`, `LB.tsv`, `SUPPLB.tsv`, `BM.tsv`.

### Step 7: Hand-over report

Give the user, in this order:

1. Files written and validator results
2. Unfilled fields (PLACEHOLDER or null), by file
3. Column mapping used for the lab files (Step 1)
4. Accessions resolved and where each was looked up
5. Domains the study needs beyond DM/LB/SUPPLB/BM (Step 6 check), and that BM is a proposed domain
6. Known deviations from SDTMIG in the converter output (`references/sdtmig-guide.md` §5: limits in
   SUPPLB)

## Reverse workflow: SDTM → record set

1. Convert:

   ```bash
   python scripts/sdtm_to_record_set.py --dm sdtm/DM.tsv --lb sdtm/LB.tsv \
     --supplb sdtm/SUPPLB.tsv --bm sdtm/BM.tsv --output-dir ./reconstructed
   ```

2. Finalize the reconstructed BCOs (`finalize_draft.py --input <file>`).
3. Gate: run `validate_bco.py` on the BCOs and `validate_bmkb.py` on the BMKB record.
4. If the original record set is available, compare it field by field. Differences in key order or
   template layout are acceptable. Differences in condition, entity, role, limits, censor states or
   measurement timing are errors.
5. Report what could not be reconstructed (`references/sdtmig-guide.md` §7, last paragraph) and
   every PLACEHOLDER left.

## Worked example: Troponin I

`examples/troponin_I/` holds human-validated outputs (`Troponin_I_tBCO.json`,
`Troponin_I_patient1_rBCO.json`, `Troponin_I_biomarkerKB.json`, `Troponin_I_SDTM.xlsx`). Its inputs
are the simulated documents in `fixtures/troponin_I/`. Match its shape, not its values:
TnI-Ultra on ADVIA Centaur XP, LoD 0.006 / LLOQ 0.03 / ULOQ 50 ng/mL, 99th percentile 0.04 ng/mL,
acute myocardial infarction (DOID:5844).

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
  schemas/              IEEE 2791 JSON Schemas (used by validate_bco.py)
scripts/                run, do not edit
assets/                 templates you fill + entity_names.json cache
examples/               validated gold outputs (read-only)
fixtures/               simulated input documents
README.md, CHANGELOG.md for human maintainers
```
