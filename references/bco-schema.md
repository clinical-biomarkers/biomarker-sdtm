---
doc: bco-schema
version: 1.0.0
status: current
updated: 2026-10-15
source: IEEE 2791-2021 schema
---

# IEEE 2791 BCO Schema Reference

> IEEE 2791-2020 — BioCompute Object schema.
> Latest schema: `https://w3id.org/ieee/ieee-2791-schema/2791object.json` (JSON Schema draft-07).
> Fetched 2026-10-13.

## Root Object

**Schema:** `2791object.json`

### Required fields
- `object_id` (string, read-only)
- `spec_version` (string, URI, read-only)
- `etag` (string, read-only, hex pattern `^([A-Za-z0-9]+)$`)
- `provenance_domain` (object — see below)
- `usability_domain` (array — see below)
- `description_domain` (object — see below)
- `execution_domain` (object — see below)
- `io_domain` (object — see below)

### Optional fields
- `extension_domain` (array of extension objects)
- `parametric_domain` (array — see below)
- `error_domain` (object — see below)

### Shared definitions (used across domains)

**`uri` type:**
  - `uri` (string, URI format) **required**
  - `filename` (string, optional)
  - `access_time` (string, date-time, optional)
  - `sha1_checksum` (string, hex pattern, optional)

**`object_id` type:** string, unique, never reused

**`contributor` type:**
  - `name` (string) **required**
  - `affiliation` (string, optional)
  - `email` (string, email format, optional)
  - `contribution` (array of PAV ontology terms) **required**
    - enum: `authoredBy`, `contributedBy`, `createdAt`, `createdBy`, `createdWith`, `curatedBy`, `derivedFrom`, `importedBy`, `importedFrom`, `providedBy`, `retrievedBy`, `retrievedFrom`, `sourceAccessedBy`
  - `orcid` (string, URI format, optional)

---

## Provenance Domain

**Required:** `name`, `version`, `created`, `modified`, `contributors`, `license`

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Public searchable name |
| `version` | string | Semantic versioning (semver) |
| `created` | string (date-time) | Creation timestamp |
| `modified` | string (date-time) | Last modified timestamp |
| `contributors` | array[contributor] | List of contributors |
| `license` | string | License identifier |
| `review` | array | Review status entries: `{status, reviewer, date?, reviewer_comment?}` |
| `derived_from` | object_id | Parent BCO this is derived from |
| `obsolete_after` | string (date-time) | Expiration date |
| `embargo` | object | `{start_time?, end_time?}` |

**Review status enum:** `unreviewed`, `in-review`, `approved`, `rejected`, `suspended`

---

## Usability Domain

**Type:** array of strings

Free-text descriptions of the purpose and function. Each entry describes a scientific objective, using ontology cross-references where appropriate.

Example: `"Identify baseline single nucleotide polymorphisms SNPs [SO:0000694]..."`

---

## Description Domain

**Required:** `keywords`, `pipeline_steps`

| Field | Type | Description |
|-------|------|-------------|
| `keywords` | array[string] | Search keywords |
| `xref` | array[object] | External references with `{namespace, name, ids[], access_time}` |
| `platform` | array[string] | Platforms where the workflow can run |
| `pipeline_steps` | array[object] | Workflow step definitions |

**Pipeline step object** (required: `step_number`, `name`, `description`, `input_list`, `output_list`):
- `step_number` (integer) — position in pipeline
- `name` (string) — tool/step name
- `description` (string) — purpose of this step
- `version` (string, optional) — tool version
- `prerequisite` (array[{`name`, `uri`}], optional)
- `input_list` (array[uri])
- `output_list` (array[uri])

---

## Execution Domain

**Required:** `script`, `script_driver`, `software_prerequisites`, `external_data_endpoints`, `environment_variables`

| Field | Type | Description |
|-------|------|-------------|
| `script` | array[{`uri`}] | Script URIs |
| `script_driver` | string | Executable driver (e.g. `hive`, `cwl-runner`, `shell`) |
| `software_prerequisites` | array[object] | `{name, version, uri}` |
| `external_data_endpoints` | array[object] | `{name, url}` |
| `environment_variables` | object | Key-value string pairs |

---

## Parametric Domain

**Type:** array of objects

Each entry (required: `param`, `value`, `step`):
- `param` (string) — parameter name
- `value` (string) — non-default value
- `step` (string) — pipeline step reference

---

## Input/Output Domain

**Required:** `input_subdomain`, `output_subdomain`

| Field | Type | Description |
|-------|------|-------------|
| `input_subdomain` | array[{`uri`}] | Global input files |
| `output_subdomain` | array[{`mediatype`, `uri`}] | Global output files |

`mediatype` defaults to `application/octet-stream`. Use IANA media types.

---

## Error Domain

**Required:** `empirical_error`, `algorithmic_error`

Both are open-ended objects (not constrained by schema — keys SHOULD use full URIs).

| Field | Type | Description |
|-------|------|-------------|
| `empirical_error` | object | Empirically determined: LOD, false +/-, confidence, etc. |
| `algorithmic_error` | object | Algorithmic/stochastic error bounds |

---

## Extension Domain

**Type:** array of objects

Each entry (required: `extension_schema`):
- `extension_schema` (string, URI) — resolves to the extension's JSON Schema
- Additional properties: any user-defined fields

---

## Usage Notes for the Skill

- **tBCO:** Template BCO uses all 8 domains. Provenance describes the assay template. Description + Execution describe the assay workflow. Parametric holds assay parameters. IO links assay inputs/outputs.
- **rBCO:** Run BCO — Provenance links `derived_from` → tBCO `object_id`. Execution describes the instrument run. Error holds QC/LOD info. IO holds patient-specific files.
- **Required top-level values:** `object_id`, `spec_version` (`https://w3id.org/ieee/ieee-2791-schema/`), `etag` (SHA-256 or UUID).

*Source: IEEE 2791 JSON Schemas from `w3id.org/ieee/ieee-2791-schema/` (2791object.json + 7 domain sub-schemas).*
