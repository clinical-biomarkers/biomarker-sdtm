---
doc: bmkb-model
version: 2.0.0
status: current
updated: 2026-10-15
source: BiomarkerKB data-submission wiki + Troponin I example
---

# BiomarkerKB Data Model Reference (submission schema)

> BiomarkerKB (biomarkerkb.org) is GWU's biomarker knowledgebase. This reference defines the
> **provider-side submission schema** — the shape a data provider produces. It is **not** the
> full API response: BiomarkerKB assigns several fields (accession ids, digests, source tags)
> only *after* it receives the data, so a submitter must not emit them.

**Sources:** BiomarkerKB data-submission wiki; the Troponin I worked example.

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
- `id`: a CURIE from **Disease Ontology (DOID), MONDO, SNOMED, or NCIt** — format `DOID:0080600`.
- `resource`: the ontology the id came from.

## 4. `best_biomarker_role`

```
[ { "role": "diagnostic" } ]
```

Valid roles (lowercase): `diagnostic`, `prognostic`, `predictive`, `monitoring`, `safety`,
`susceptibility/risk`, `pharmacodynamic/response`. See `best-definitions.md`.

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

**`assessed_entity_type`** — report in **all lowercase**. Allowed values only:

`protein`, `gene`, `DNA`, `RNA`, `cell`, `lipid`, `glycan`, `metabolite`, `element`,
`image`, `condition`

## 7. ⭐ Accession lookup — where the id comes from

The provider supplies the **name** (from the clinical documents); the **accession** must be
looked up using the entity type. Use the resource in order of preference; fall back to the
next only if the preferred resource has no entry.

Nested by entity type → resource (in order of preference):

- **protein** → UniProt (UPKB) → PDB → PRO → NCIt
- **peptide** → PRO
- **protein complex** → PRO → GO
- **gene** → NCBI
- **gene (mutation)** → NCBI dbSNP
- **DNA** → NCIt
- **RNA** → HGNC → RNA Central (RNAC)
- **miRNA** → miRBase (MRB)
- **glycan** → GlyTouCan (GTC) → PubChem
- **carbohydrate** → ChEBI
- **metabolite** → PubChem (PCCID) → ChEBI
- **lipoprotein** → ChEBI
- **chemical element** → PubChem (PCCID) → NCIt
- **cell** → CO → NCIt

Other ids:

- **Condition accession** — Disease Ontology / MONDO / SNOMED / NCIt (§3).
- **Specimen** — UBERON CURIE + LOINC (when a specimen is carried).
- Prefix convention in the id: e.g. UniProt → `UPKB:P19429`.

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

## 10. Mapping BMKB → SDTM BM domain

- `biomarker_component[].assessed_biomarker_entity_id` → `BMENTID`
- entity **name resolved from the accession** (cached UniProt/CO/GlyTouCan) → `BMENTNM`
- `biomarker_component[].assessed_entity_type` → `BMENTTP` (uppercase)
- `biomarker_component[].biomarker` → `BMCVTERM`
- `best_biomarker_role[].role` → `BMROLE` (uppercase)
- `condition.name` → `BMCOND` · `condition.id` → `BMCONDID`
- `provenance.date` → `BMASSDTC`
- BMID / BMVER / BMSRC* are study-side, not BMKB
- **`BMEVID` is not sourced from BMKB** — the submission record carries no evidence;
  the study documents (context-of-use / protocol citations) supply it.

Provenance codes in the BM domain: **K** = BiomarkerKB-sourced fields.

## 11. Notes

1. **Do not emit BMKB-assigned fields** (§2) — the provider submits; BiomarkerKB assigns.
2. **Condition is the study context** (e.g. AMI `DOID:5844`), not any example's condition.
3. **Look up accessions from the entity type** (§7) — clinical documents carry names, not ids.

---

*See also: `best-definitions.md`, `sdtmig-guide.md`, `bco-schema.md`.*
