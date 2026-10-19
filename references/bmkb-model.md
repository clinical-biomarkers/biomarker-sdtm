---
doc: bmkb-model
version: 2.2.0
status: current
updated: 2026-10-19
source: BiomarkerKB data-submission wiki + Troponin I example
---

# BiomarkerKB Data Model Reference (submission schema)

> BiomarkerKB (biomarkerkb.org) is GWU's biomarker knowledgebase. This reference defines the
> **provider-side submission schema** — the shape a data provider produces. It is **not** the
> full API response: BiomarkerKB assigns several fields (accession ids, digests, source tags)
> only *after* it receives the data, so a submitter must not emit them.

**Sources:** BiomarkerKB data-submission wiki; the Troponin I worked example.

## Contents

1. Conceptual model · 2. Submission schema · 3. `condition` · 4. `best_biomarker_role` ·
5. `biomarker_component[]` · 6. The biomarker statement and entity type · 7. Accession lookup ·
8. `entity_normal_ranges[]` · 9. `provenance` · 10. Mapping to the BM domain · 11. Notes

---

## 1. Conceptual model

A record asserts: **this biomarker (a specific entity + change) is associated with this
condition, in this role**, with provenance for who supplied it.

```
condition (id, name, resource)
best_biomarker_role[]      (BEST)
biomarker_component[]      (component_index, entity_index,
                            assessed_biomarker_entity_id,
                            assessed_entity_type, biomarker)
entity_normal_ranges[]     (optional, age/sex-stratified norms)
provenance                 (provider, author, date, description)
```

## 2. Submission schema

```
{
  "condition": { "id", "name", "resource" },
  "best_biomarker_role": [ { "role" } ],
  "biomarker_component": [
    { "component_index", "entity_index",
      "assessed_biomarker_entity_id", "assessed_entity_type", "biomarker" }
  ],
  "entity_normal_ranges": [ ... ],
  "provenance": { "provider", "author", "date", "description" }
}
```

**Fields BiomarkerKB assigns on receipt — a submitter must NOT include them:**
`biomarker_id`, `biomarker_canonical_id`, `biomarker_id_md5`, `canon_id_md5`,
`biomarker_id_new`, `source_list`.

## 3. `condition`

```
{ "id": "DOID:5844", "name": "acute myocardial infarction", "resource": "Disease Ontology" }
```

- `name` is **lowercase** (e.g. `colon cancer`).
- `id`: a CURIE from **Disease Ontology (DOID), MONDO or NCIt** (`DOID:0080600`, `MONDO:0005068`,
  `NCIT:C27996`), looked up through OLS (§7). SNOMED is allowed but not on OLS: use it only when a
  document gives the code.
- `resource`: the ontology name (`Disease Ontology`, `MONDO`, `NCI Thesaurus`).

## 4. `best_biomarker_role`

```
[ { "role": "diagnostic" }, { "role": "prognostic" } ]
```

Valid roles (lowercase): `diagnostic`, `prognostic`, `predictive`, `monitoring`, `safety`,
`susceptibility/risk`, `pharmacodynamic/response`. One entry per role the study supports; how to
choose them is in `best-definitions.md`.

## 5. `biomarker_component[]`

One entry per biomarker-entity pairing. **Exactly five fields:**

- `component_index` — index within the record set (`"1"`)
- `entity_index` — index within the entity (`"1"`)
- `assessed_biomarker_entity_id` — the entity's ontology id (see §7)
- `assessed_entity_type` — lowercase, from the allowed set (see §6)
- `biomarker` — the controlled-vocabulary statement (see §6)

## 6. The biomarker statement and entity type

The `biomarker` field follows **`{change} {aspect} of {entity_type} {symbol}/{entity_id}`**,
e.g. `Increased level of protein TNNI3/UPKB:P19429`.

- **Change:** increased, decreased, elevated, reduced, presence, absence
- **Aspect:** level, expression, activity, concentration, mutation
- A bare entity name is **not** a biomarker — the change concept is mandatory.

**`assessed_entity_type`**, all lowercase, allowed values only:

`protein`, `gene`, `dna`, `rna`, `cell`, `lipid`, `glycan`, `metabolite`, `element`, `image`,
`condition`

More specific kinds (peptide, protein complex, gene (mutation), miRNA, carbohydrate, lipoprotein,
chemical element) keep their own resource chain in §7 but are written as their parent type
(`python scripts/biomarker_accessions.py` shows the mapping).

## 7. Accession lookup

The documents give the entity **name**; the record needs a **CURIE**.

1. Pick the entity type (§6). Run `python scripts/biomarker_accessions.py` for its resource chain,
   in order of preference. A `*` marks resources the OLS MCP server can resolve.
2. Look the entity up **only through the OLS MCP server** (its search tool). Take the first
   resource in the chain that OLS has a match for.
3. Convert the OLS term id to a CURIE with `curie_from_ols()` in that script:
   - a Protein Ontology term named by a UniProt accession, `PR_P19429`, becomes `UPKB:P19429`
   - every other term, `GO_0005861`, `DOID_5844` or `NCIT_C16612`, becomes `GO:0005861`,
     `DOID:5844`, `NCIT:C16612`
4. If OLS has no entry (UniProt-only, PubChem, GlyTouCan, miRBase, dbSNP, NCBI Gene, LOINC, ...),
   leave the id `PLACEHOLDER` and list it in the hand-over report. Never guess an id, and never use
   another lookup route.
5. If the OLS MCP server is not connected, tell the user before going on.

Write every identifier as a CURIE (`PREFIX:local`), in the BMKB record and in the tBCO
(`target.analyte_identifiers[].curie`). Specimens use UBERON (`UBERON:0001977`, blood serum).

## 8. `entity_normal_ranges[]` (optional)

Age/sex-stratified population norms from clinical data sources.

```
entity_normal_ranges[]
├── entity_name, entity_id
└── source[]
    ├── source_name, lab_term
    └── ranges[]
        ├── age_grp, sex, n_val, units
        └── mean_val, median_val, sd_val, min, max, q1, q3, iqr,
            lower_whisker, upper_whisker
```

Informative metadata only — it does **not** feed the tBCO's `analytical_performance.reference_limits`.

## 9. `provenance`

A single object naming who supplied the record — **not** a citation list.

```
{ "provider": "...", "author": "...", "date": "YYYY-MM-DD", "description": "..." }
```

- `provider` — the submitting organisation / person
- `author` — who authored the record
- `date` — ISO date the record was produced
- `description` — free-text note on the record's origin

## 10. Mapping to the BM domain

The BMKB → BM variable mapping and provenance letters are in `sdtmig-guide.md` §6, the only copy.
Two points matter while writing the record: the entity *name* is not carried (BM.BMENTNM is resolved
from `assets/entity_names.json`), and the record carries no evidence (BM.BMEVID comes from the
study documents via `--evidence`).

## 11. Notes

1. **Do not emit BMKB-assigned fields** (§2) — the provider submits; BiomarkerKB assigns.
2. **Condition is the study context** (e.g. AMI `DOID:5844`), not any example's condition.
3. **Look up accessions from the entity type** (§7) — clinical documents carry names, not ids.

---

*See also: `best-definitions.md`, `sdtmig-guide.md`, `bco-schema.md`.*
