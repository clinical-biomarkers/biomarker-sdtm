---
doc: cdisc-ct
version: 1.0.0
status: current
updated: 2026-10-19
source: NCI EVS, "SDTM Terminology.txt", release of 2026-09-25 (https://evs.nci.nih.gov/ftp1/CDISC/SDTM/)
---

# CDISC Controlled Terminology extract

`sdtm_ct_extract.tsv` is a slim extract of the SDTM terminology, so the skill can choose CT values
offline. Query it with `python scripts/cdisc_ct.py`; there is no need to read the file.

| Codelist | Terms | Used for |
|---|---|---|
| LBTESTCD (paired with LBTEST) | 2,513 | tBCO `target.lbtestcd` / `target.lbtest` |
| ISTESTCD (paired with ISTEST) | 100 | the same, with `--domain IS` |
| GFTESTCD (paired with GFTEST) | 20 | the same, with `--domain GF` |
| SPECTYPE | 129 | `specimen_requirements.specimen_type` (LBSPEC, BMSPEC) |
| UNIT | 950 | `reporting_convention.unit` (LBORRESU, LBSTRESU) |
| METHOD | 534 | `assay.method` (LBMETHOD, BMMETHOD) |

Columns: `codelist`, `c_code`, `submission_value`, `paired_name` (the --TEST name for a --TESTCD),
`synonyms`, `nci_preferred_term`. Definitions are left out to keep the file small.

**Refreshing.** CDISC publishes a new release each quarter. Download the latest
`SDTM Terminology.txt` from NCI EVS, regenerate the extract with the same columns and codelists,
update the release date above, and run `python scripts/run_checks.py`.
