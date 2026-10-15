---
doc: references-readme
version: 1.0.0
status: current
updated: 2026-10-15
---

# references/ — reference material for the biomarker-sdtm skill

Documents and schemas the skill loads **on demand**. `SKILL.md` stays a thin index; the
detail lives here.

## Layout

```
references/
├── README.md            # this file — index, naming and versioning rules
├── bmkb-model.md        # BiomarkerKB submission schema + accession lookup
├── bco-schema.md        # IEEE 2791 BCO field spec (narrative)
├── best-definitions.md  # FDA-NIH BEST biomarker roles
├── sdtmig-guide.md      # SDTMIG v3.4 rules for DM, LB, SUPPLB, BM
├── pitfalls.md          # known traps across BCO / BMKB / SDTM
├── sdtmig-v3.4.pdf      # full SDTMIG v3.4 specification (consult when the summary isn't enough)
└── schemas/             # IEEE 2791 JSON Schemas (machine-readable)
```

## Naming rules

- **Docs** — kebab-case, topic-named: `<topic>.md`. No dates or versions in the filename;
  the file is the living reference.
- **Templates** — `assets/<thing>_template.json`.
- **IEEE schemas** — keep their **upstream filenames** (`2791object.json`,
  `*_domain.json`). They cross-reference each other by bare filename via `$ref`, so renaming
  breaks resolution. They live together in `schemas/` so those relative refs still work.
- **Source PDFs** — kebab-case, versioned where it matters (`sdtmig-v3.4.pdf`). Record the
  upstream filename here when the shipped name differs.

## Versioning rules

Every versioned artifact declares its version in one of two ways:

- **Markdown docs** — a YAML front matter block at the top of the file:

  ```
  ---
  doc: <slug>
  version: <major>.<minor>.<patch>
  status: current | draft | superseded
  updated: YYYY-MM-DD
  source: <where the content came from>
  ---
  ```

- **JSON templates** — the version is recorded in this README's table, **not** injected into
  the JSON: a stray metadata key would flow into generated BCO/BMKB output and could break
  downstream validation.

Bump **major** for a breaking schema change, **minor** for added fields, **patch** for fixes.
When a schema changes, update it in the same change as its generator, its template, and the
gold example — they are one unit.

## Manifest

| Artifact | Version | Status | Updated | Notes |
|---|---|---|---|---|
| `bmkb-model.md` | 2.0.0 | current | 2026-10-15 | Rewritten to the provider-side submission schema |
| `bco-schema.md` | 1.0.0 | current | 2026-10-13 | |
| `best-definitions.md` | 1.0.0 | current | 2026-10-13 | |
| `sdtmig-guide.md` | 1.0.0 | current | 2026-10-13 | |
| `pitfalls.md` | 1.0.0 | current | 2026-10-13 | |
| `schemas/2791object.json` | upstream | current | 2026-10-13 | IEEE 2791 root schema |
| `sdtmig-v3.4.pdf` | 3.4 | current | 2026-10-15 | Full spec; upstream name `SDTMIG v3.4-FINAL_2022-07-21.pdf` |
| `assets/bmkb_template.json` | 2.0.0 | current | 2026-10-15 | Matches bmkb-model.md v2 |
| `assets/entity_names.json` | 1.0.0 | current | 2026-10-15 | Accession→name resolution cache (BM.BMENTNM) |
| `assets/tbco_template.json` | 1.0.0 | current | 2026-10-13 | |
| `assets/rbco_template.json` | 1.0.0 | current | 2026-10-13 | |
| `assets/bm_row_template.json` | 1.0.0 | current | 2026-10-13 | |
