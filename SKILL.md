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
  version: "0.1.0"
  repository: https://github.com/biocompute-objects/bco-rag
---

# Biomarker SDTM — BioCompute Objects and SDTM for Biomarker Data

Turns study **documents** (assay specs, patient data) into a reusable **record set** — a template BCO (tBCO), one run BCO (rBCO) per patient, and a BiomarkerKB (BMKB) record. Converts that record set to and from **SDTM** (standard clinical-trial tabulation).

Two directions:

1. **Forward** — Documents → tBCO + rBCO + BMKB → SDTM (DM, LB, SUPPLB, BM)
2. **Reverse** — SDTM → tBCO + rBCO + BMKB (round-trip)

## How this skill works — read this first

**You (the agent) author the artifacts.** The skill ships two kinds of asset, and it is
important not to confuse them:

- **Templates** (`assets/*_template.json`) — annotated blank forms. Keys beginning with
  `//_` are _guidance for you_; they are removed when you finalize. Read the template,
  understand its shape, then fill it from the source documents.
- **Scripts** (`scripts/*.py`) — only the jobs that must be exact and should not be
  re-derived by hand:
  - `finalize_draft.py` — strips `//_` annotation keys and computes the `etag`
  - `validate_bco.py` — structural + IEEE 2791 schema validation
  - `censor_state.py` — analytic censoring logic (value → zone, zone → SDTM fields)
  - `biomarker_accessions.py` — entity type → accession resource table
  - `record_set_to_sdtm.py` / `sdtm_to_record_set.py` — the SDTM conversions

**The scripts never decide values.** There is no intermediate "input schema" to translate
into — write the artifact directly from the template and the documents.

## Prerequisites

- Python 3.10+ with `scripts/` and `assets/` on the Python path (or run from the `scripts/` directory)
- `jsonschema` 4.18+ pip package (required by `validate_bco.py` for IEEE 2791 schema conformance)
- Source documents: assay spec, patient data table, and demographics

## Workflow — Forward direction

### Step 1: Ingest source documents

Collect the information the user has:

- **Assay specification** — biomarker name, platform, manufacturer, LoD/LLOQ/ULOQ, reference limits (99th percentile), specimen type, LOINC code, units, sampling schedule, interpretation rules
- **Patient data** — subject IDs, results per visit, collection times, units
- **Demographics** — age, sex, country for each subject

Documents carry **names, not identifiers**. Accessions (UniProt, DOID, …) are almost never
present in clinical documents — derive them yourself (Step 4). If a value is genuinely absent
from the documents, leave it `PLACEHOLDER`; do not invent values, and do not annotate the
absence in the output.

### Step 2: Write the tBCO (template BCO)

The tBCO encodes the _assay specification_ — one per biomarker per assay platform.

Read `assets/tbco_template.json`, fill it from the documents, then finalize and validate:

```bash
python scripts/finalize_draft.py --input tBCO.draft.json --output tBCO.json
python scripts/validate_bco.py tBCO.json
```

- Keep the `//_` guidance keys while you draft; finalize strips them.
- Leave the `etag` alone — finalize computes it.
- All 8 IEEE 2791 domains must survive plus the `assay_protocol_extension`.
- Anything the documents don't supply stays `PLACEHOLDER`.

### Step 3: Write one rBCO per patient

The rBCO captures _what actually happened on the instrument_ for one patient. Same shape as
Step 2: fill `assets/rbco_template.json`, finalize, validate.

Each measurement records a `censor_state` from the controlled vocabulary:

- `below_lod` — value below limit of detection
- `detected_below_lloq` — detected but below LLOQ
- `quantifiable` — within quantifiable range (includes `measurable`)
- `above_uloq` — above upper limit of quantification

**Do not decide censor states by eye — call the module.** It encodes the tBCO thresholds and
the SDTM field consequences:

```python
from censor_state import resolve_censor_state, make_sdtm_fields

state = resolve_censor_state(value=0.021, lod=0.006, lloq=0.03, uloq=50.0)
# Returns "detected_below_lloq"
```

### Step 4: Write the BMKB record

The BMKB record describes the _biomarker knowledge_ — entity, condition, role — independently
of any assay. It is the **provider-side submission schema**: a submitter must **not** emit
BiomarkerKB-assigned fields (`biomarker_id`, `biomarker_canonical_id`, `*_md5`,
`biomarker_id_new`, `source_list`) — BiomarkerKB assigns those on receipt.

Fill `assets/bmkb_template.json` and write `BMKB.json`. There is no etag, so no finalize step
is needed — but validate the key set:

```bash
python scripts/validate_bmkb.py BMKB.json
```

Record shape:

```
condition { id, name, resource }
best_biomarker_role[] { role }
biomarker_component[] { component_index, entity_index,
                        assessed_biomarker_entity_id,
                        assessed_entity_type, biomarker }
entity_normal_ranges[]          # optional
provenance { provider, author, date, description }
```

**Assigning accessions — do this before writing the record.** The clinical documents give
_names_; the record needs _accessions_. The lookup table is available as code:

```bash
python scripts/biomarker_accessions.py            # print the table
```

```python
from biomarker_accessions import accession_resource_for
accession_resource_for("protein")   # -> "UniProt (UPKB)"
```

In order of preference (fall back only if the preferred resource has no entry):

- protein → UniProt (UPKB) → PDB → PRO → NCIt
- peptide → PRO; protein complex → PRO → GO
- gene → NCBI; gene (mutation) → NCBI dbSNP
- DNA → NCIt; RNA → HGNC → RNA Central (RNAC); miRNA → miRBase (MRB)
- glycan → GlyTouCan (GTC) → PubChem; carbohydrate → ChEBI
- metabolite → PubChem (PCCID) → ChEBI; lipoprotein → ChEBI
- chemical element → PubChem (PCCID) → NCIt; cell → CO → NCIt

Rules:

- `assessed_entity_type` is **lowercase**, from: `protein`, `gene`, `DNA`, `RNA`, `cell`,
  `lipid`, `glycan`, `metabolite`, `element`, `image`, `condition`
- **Condition** — id is a `DOID:`/`MONDO:`/`SNOMED:`/`NCIt:` CURIE; `name` is lowercase;
  `resource` names the ontology. Use the **study context** condition (e.g. acute myocardial
  infarction `DOID:5844`), never an example's condition.
- **`biomarker`** statement follows `{change} {aspect} of {entity_type} {symbol}/{entity_id}`
  (e.g. `Increased level of protein TNNI3/UPKB:P19429`). A bare entity name is not a biomarker.

Full detail: `references/bmkb-model.md` §6–§7.

**Record every accession you resolve.** The record carries the accession, but SDTM's BM domain
also needs the entity *name* (`BM.BMENTNM`). Those pairs live in `assets/entity_names.json`,
keyed by the accession exactly as it appears in `assessed_biomarker_entity_id`:

```json
"UPKB:P19429": "Troponin I, cardiac muscle"
```

Add the pair each time you resolve an entity type to an accession. A missing entry means
`BM.BMENTNM` comes out empty, and the conversion will fail on it.

**Why a local cache rather than a live lookup.** Resolving an accession over the network from
UniProt, CO or GlyTouCan would tie every run to an external service: its uptime, its rate
limits, and whatever its data happens to say that day. Keeping the mapping local makes the
conversion fully offline and deterministic, so the same documents produce the same BM row
every time, with no network access required. The trade-off is that the cache is only as
complete as what you add to it, which is why recording each pair matters.

### Step 5: Convert the record set to SDTM

```bash
python scripts/record_set_to_sdtm.py \
  --tbco tBCO.json \
  --rbco rBCO_patient1.json \
  --bmkb BMKB.json \
  --results results.json \
  --dm dm.json \
  --evidence PMID:19710485 \
  --output-dir ./sdtm
```

`--evidence` supplies the biomarker's evidence ids. The BMKB submission record carries no
evidence — it comes from the study documents (context-of-use / protocol citations).

The results JSON is an array of measurement events:

```json
{"results": [
  {"idvarval": 1, "lborres": "0.021", "lbstresc": "0.021", "lbstressn": 0.021, "visitnum": 1, "visit": "Baseline"},
  ...
]}
```

The DM JSON is demographics:

```json
{"dm": [
  {"usubjid": "BM-2026-01-001", "age": 67, "sex": "M", "country": "DEU", ...}
]}
```

Produces 4 TSV files:

- `DM.tsv` — Demographics (age, sex, country)
- `LB.tsv` — Lab results (values, units, LOINC, visit, specimen)
- `SUPPLB.tsv` — Assay qualifiers (limits, assay name, platform, rBCO id, censor state)
- `BM.tsv` — Biomarker context (entity, condition, assay ref, rule, tBCO ref)

### Step 6: Finalize and validate

```bash
python scripts/finalize_draft.py --input tBCO.json            # in place
python scripts/finalize_draft.py --input tBCO.json --check    # verify the etag
python scripts/validate_bco.py tBCO.json rBCO_patient1.json
```

Exit code 0 = all valid. `validate_bco.py` checks:

- All 8 BCO domains are present
- The `etag` is a well-formed 64-char SHA-256 digest
- No unfilled `PLACEHOLDER` strings (warns only)
- Required fields are non-empty
- Conformance to the IEEE 2791 JSON Schemas in `references/schemas/` (schema violations fail the file)

`finalize_draft.py --check` additionally verifies the etag actually _matches the content_.

## Workflow — Reverse direction (SDTM → record set)

```bash
python scripts/sdtm_to_record_set.py \
  --dm sdtm/DM.tsv \
  --lb sdtm/LB.tsv \
  --supplb sdtm/SUPPLB.tsv \
  --bm sdtm/BM.tsv \
  --output-dir ./reconstructed
```

Reconstructs tBCO, rBCO, and BMKB JSON from the four SDTM TSV files. The censor state is reverse-derived from `LBORRES` and the assay limits in `SUPPLB` using `censor_state.derive_censor_state_from_sdtm()`.

**Round-trip** — the output should be semantically equivalent to the original record set. Structural diffs (template key alignment) are acceptable; semantic differences (condition, entity, measurement values) are not.

## Worked example: Troponin I

The reference example lives in `examples/troponin_I/`:

- `Troponin_I_tBCO.json` — Template BCO (Siemens TnI-Ultra assay on ADVIA Centaur XP)
- `Troponin_I_patient1_rBCO.json` — Run BCO for patient 1
- `Troponin_I_biomarkerKB.json` — BMKB record for cardiac troponin I
- `Troponin_I_SDTM.xlsx` — SDTM output (Definitions, DM, LB, SUPPLB, BM sheets)
- `Troponin_I_readme.txt` — Package index with relationship diagram

Study it before authoring a new one — it is the shape to match.

### What it models

- **Analyte:** Cardiac troponin I (TNNI3, UniProtKB P19429)
- **Assay:** TnI-Ultra on Siemens ADVIA Centaur XP
- **Condition:** Acute myocardial infarction (DOID:5844)
- **LoD:** 0.006 ng/mL · **LLOQ:** 0.03 ng/mL · **ULOQ:** 50 ng/mL
- **99th percentile URL:** 0.04 ng/mL (interpretation: value > 0.04 ng/mL = elevated)
- **Reference:** Keller T et al., N Engl J Med 2009;361:868-77 (PMID 19710485)

### Reproducing / checking it

```bash
# 1. Self-tests for the helper modules
python scripts/finalize_draft.py --self-test
python scripts/censor_state.py --self-test
python scripts/biomarker_accessions.py --self-test

# 2. Verify the gold BCOs are finalized and valid
python scripts/finalize_draft.py --check --input examples/troponin_I/Troponin_I_tBCO.json
python scripts/validate_bco.py examples/troponin_I/Troponin_I_tBCO.json \
                              examples/troponin_I/Troponin_I_patient1_rBCO.json

# 3. Record set → SDTM → record set (round trip)
python scripts/record_set_to_sdtm.py --self-test
python scripts/sdtm_to_record_set.py --self-test
```

Test output belongs in a scratch/`_output/` directory — **never** in `examples/`, which holds
only human-validated outputs.

## Troubleshooting

### "The BCO fails validation"

**Cause:** a domain section is missing, a required field is empty, or the etag is malformed.

**Fix:** run `validate_bco.py` first — it reports which check failed.

- Ensure all 8 domains are present (`provenance_domain`, `usability_domain`, `description_domain`, `execution_domain`, `parametric_domain`, `io_domain`, `error_domain`, plus the extension)
- No required field should be `null` or `""`
- Re-run `finalize_draft.py --input <file>` if you hand-edited the JSON

### "etag mismatch"

**Cause:** the content changed after the etag was computed (hand-edits, merges).

**Fix:** `python scripts/finalize_draft.py --input <file>` — it recomputes the etag over the
canonical JSON with the `etag` field cleared. Confirm with `--check`.

### "Censor state not in controlled vocabulary"

**Cause:** you used `BLQ`, `BLOQ`, `<LLOQ`, or another non-standard term.

**Fix:** use only `below_lod`, `detected_below_lloq`, `quantifiable` (or `measurable`), `above_uloq`. Better: let `censor_state.resolve_censor_state()` decide.

### "LBSTRESN should be null for censored value"

**Cause:** a value below LoD or detected below LLOQ has a numeric standard result.

**Fix:** only `quantifiable` values get a numeric `LBSTRESN`. `censor_state.make_sdtm_fields()` handles this.

### "BM domain provenance code wrong"

**Cause:** a BM column has the wrong provenance letter (T/R/K/N/S).

**Fix:** consult `references/sdtmig-guide.md` §BM:

- **T** = from tBCO (assay name, platform, method, specimen, BCO id, rule)
- **K** = from BiomarkerKB (entity name/id/type, CV term, role, condition)
- **N** = new/assigned (BMID, BMVER, source domain/var/value references)

### "Wrong accession"

**Cause:** an entity accession was emitted with the wrong resource, or the entity type wasn't mapped.

**Fix:** use `biomarker_accessions.accession_resource_for(<type>)` and confirm the id resolves. Never guess an accession — look it up.

### "BM.BMEVID is empty"

**Cause:** the BMKB record carries no evidence (by design), and no evidence was supplied.

**Fix:** pass `--evidence PMID:...` to `record_set_to_sdtm.py`, taken from the study documents.

### "BM.BMENTNM is empty"

**Cause:** the accession in the record has no entry in `assets/entity_names.json`. The BMKB
record carries accessions rather than names, so the name has to be resolved from the cache.

**Fix:** add the pair to `assets/entity_names.json`, keyed by the accession exactly as it
appears in `assessed_biomarker_entity_id` (for example `"UPKB:P19429": "Troponin I, cardiac
muscle"`), then re-run the conversion.

### "jsonschema not available"

**Fix:** `pip install jsonschema` (4.18+). Without it `validate_bco.py` fails every file, because schema conformance is part of validation.

---

## File structure

```
biomarker-sdtm/
├── SKILL.md              # this file — frontmatter + instructions
├── README.md             # repo overview
├── CHANGELOG.md          # change history
├── references/           # docs + schemas loaded on demand (see references/README.md)
│   ├── README.md            # index + naming & versioning convention
│   ├── bmkb-model.md        # BiomarkerKB submission schema + accession lookup
│   ├── sdtmig-guide.md      # SDTMIG v3.4 rules for DM, LB, SUPPLB, BM
│   ├── best-definitions.md  # FDA-NIH BEST biomarker categories
│   ├── bco-schema.md        # IEEE 2791 field spec (narrative)
│   ├── pitfalls.md          # censoring, units, assays, BM, BMKB, SDTM
│   ├── sdtmig-v3.4.pdf      # full SDTMIG v3.4 spec — consult when the summary isn't enough
│   └── schemas/             # IEEE 2791 JSON Schemas (upstream filenames, cross-`$ref`ed)
├── scripts/              # runtime helpers — the deterministic work
│   ├── finalize_draft.py       # strip //_ annotations + compute/verify etag
│   ├── validate_bco.py         # IEEE 2791 structural + schema validator
│   ├── validate_bmkb.py        # BMKB submission-schema validator
│   ├── biomarker_accessions.py # entity type → accession resource table
│   ├── censor_state.py         # censoring logic (value→zone, zone→SDTM fields)
│   ├── record_set_to_sdtm.py   # Forward: record set → 4 SDTM TSVs
│   └── sdtm_to_record_set.py   # Reverse: 4 SDTM TSVs → record set
├── assets/               # templates — you fill these
│   ├── tbco_template.json
│   ├── rbco_template.json
│   ├── bmkb_template.json
│   ├── bm_row_template.json
│   └── entity_names.json
├── examples/             # validated reference outputs (gold) + adjudication log
└── fixtures/             # simulated input documents for testing
```

**Naming & versioning.** Kebab-case topic names for docs; `<thing>_template.json` for
templates; upstream filenames for IEEE schemas (they `$ref` each other by bare filename).
Every versioned artifact carries `version` + `status` + `updated` — see `references/README.md`.

## Controlled vocabulary (censor states)

- `below_lod` — value < LoD — `LBORRES` = `<0.006` — `LBSTRESN` = null
- `detected_below_lloq` — LoD ≤ value < LLOQ — `<0.03` — null
- `quantifiable` — LLOQ ≤ value ≤ ULOQ — `0.08` — `0.08`
- `above_uloq` — value > ULOQ — `>0.30` — null
