# CHANGELOG — `biomarker-sdtm`

Concise record of what changed and when. Newest first. Times are America/New_York (ET).

> **Layout note (2026-10-15).** The repository root is now the skill itself
> (`biomarker-sdtm/`, renamed from `bco-generator` on 2026-10-15). Development notes, source material and archives live **outside**
> the repo.

---

## 2026-10-19 12:03 (fix) — scripts: mechanical review fixes

Scripts only; no gold files edited. `python scripts/run_checks.py` runs every self-test plus a
cell-by-cell forward-vs-xlsx gold comparison, and exits 1 on any failure.

- **B01** Read `assay.assay_name` (was `assay.name`): ASSAYNAM `TnI-Ultra`, LBGRPID `TNIULTRA`,
  BMASSAY `TnI-Ultra`. Also fixed in the reverse `sdtm_extension` paths.
- **B05** `validate_bco.py` validates against `references/schemas/` through a local
  `referencing.Registry`; schema errors fail the file, and jsonschema is now required.
- **B07** Reverse self-test asserts 42 fields against the gold JSON and exits 1 on failure.
- **R01/R02** Reverse uses `censor_state.derive_censor_state_from_sdtm` and the shared `_make_grpid`.
- **R04** Dead code, unused params, `generated_*` lookups and schema-v1 fallbacks removed.
- **B12** SUPPLB CENSOR `IDVARVAL` is taken from the built LB rows (= LBSEQ, int).
- **B11 (partial)** LBBLFL is `Y` or null.
- **P04** Null analytical limits are tolerated: LBLOD/LBLLOQ/LBULOQ are omitted, and a
  censored result with no value and a null limit raises a clear `ValueError`, as does
  `censor_state` on a null threshold.
- **R05/F04** New `scripts/run_checks.py`. **P11** all scripts run from any cwd (verified).
- **Open:** run_checks fails on (a) 22 gold BCO schema errors (tBCO: `io_domain` `mediatype`,
  `parametric_domain` `step`/`rule`/`unit`; rBCO: `pipeline_steps[].prerequisite` strings,
  `mediatype`) and (b) 5 xlsx cells that the gold JSON does not produce: LBTEST case ×3,
  BMCOND case, BMRULE text. LBBLFL `N` in the xlsx is reported as a known deviation.

## 2026-10-15 18:13 (supervisor)
- **`_load_entity_names()` tidied.** It was the only loader that kept `//_` annotation keys,
  so it now strips them via `finalize_draft.strip_comments()` rather than a second private
  implementation of the same convention. This matters more now that the agent is told to
  write entries into that file. The in-line `//_note` guidance stays in the file for whoever
  maintains it, and is simply not surfaced to the conversion.
- **A malformed cache now fails loudly.** It previously caught `(OSError, ValueError)` and
  returned `{}`, so a hand-edit that broke the JSON surfaced later as a confusing
  "BM.BMENTNM is empty". A *missing* file is still not an error (the cache is optional); a
  file that exists but will not parse raises with the path and the parser message.
- Verified all three paths (strip / missing / malformed) and the suite is still 4/4.

## 2026-10-15 18:10 (supervisor)
- **Closed the `entity_names.json` gap in `SKILL.md`.** It was listed in the file tree but the
  agent was never told what to do with it, so any entity outside the cache produced an empty
  `BM.BMENTNM` with no way to recover. Step 4 now instructs the agent to record every
  accession-to-name pair it resolves, and explains why the cache is local: it keeps the
  conversion offline and deterministic rather than depending on a service's uptime, rate
  limits and current data.
- Added a matching troubleshooting entry, `"BM.BMENTNM is empty"`, pointing back to the fix.
- Chose colons, commas and full stops over em-dashes in the new prose; existing em-dashes in
  the file left untouched as instructed.

## 2026-10-15 18:01 (supervisor)
- **`README.md` em-dashes removed** (16 → 0). Replaced contextually rather than swapped for a
  single character: colons after list labels and in the Resources list, a comma mid-sentence,
  a semicolon where a new clause was doing the work, and one sentence split in two where a
  paired dash-as-parenthesis would otherwise have become comma soup.

## 2026-10-15 17:50 (supervisor)
- **BEST attributed in `README.md`** — added the FDA-NIH BEST Resource to the Resources list.
  It was already fully cited in `references/best-definitions.md` (citation + homepage,
  glossary, contents-of-a-biomarker-description, and FDA pages), but two lines there pointed
  at `references/BEST-Resource.pdf`, which is not shipped; those dead paths are gone.
- **Added a Disclaimer** to the end of `README.md` covering clinical use, regulatory
  submission, verification of generated values, schema drift, and warranty/liability.

## 2026-10-15 17:37 (supervisor)
- **`README.md`** — removed the Conventions section; added **Resource versions**, tabulating
  the three external standards the skill depends on (BCO / SDTM / SDTMIG) against the shipped
  copies; added the acknowledgement that this work is supported by BiomarkerKB.
- **`references/sdtmig-guide.md`** — its References block pointed at two files under
  `references/` that are not there: SDTMIG had been renamed to `sdtmig-v3.4.pdf` and the
  SDTM v2.1 model document was never shipped. Both now cited by version instead of by a
  dead path, and the stale `notes/` reference (moved outside the repo) dropped.

## 2026-10-15 17:16 (supervisor)
- **Removed the last schema-v2 remnants.** `_extract_evidence()` in `record_set_to_sdtm.py`
  read only fields that no longer exist (`evidence_source`, `biomarker_component_new`,
  `crossrefs`), so it always returned an empty list — dead code. Removed it and its call
  site; the tBCO remains the secondary evidence source after the study documents.
- **`assets/bm_row_template.json`** — dropped a stale COVID-19 example from the condition
  warning (the reference record has used AMI since schema v2).
- The only surviving mention of a removed field is the deliberate warning in `pitfalls.md`
  telling the agent *not* to emit them.
- Suite still 4/4.

## 2026-10-15 17:15 (supervisor) — `pitfalls.md` corrected; censor-state validation enforced
- **Removed two obsolete pitfalls** left over from the BMKB v2 rewrite: the nested
  `biomarker_component_new[]` model (no longer in the submission schema) and the
  `evidence_source` duplication. Replaced with the pitfalls that *are* current: emitting
  BiomarkerKB-assigned fields, the five-field constraint, and the fact that the record
  carries no evidence.
- **Corrected three wrong tBCO field paths** — `assay_performance` should be
  `analytical_performance`, and the limits are `limit_of_quantitation` /
  `upper_limit_of_quantitation` (not `lower_/upper_limit_of_quantification`).
- **Corrected the censoring vocabulary** — the canonical fourth state is `quantifiable`;
  `measurable` is only a synonym. `pitfalls.md` had it the other way round, which would
  have taught the agent the wrong value.
- **Fixed a silent-failure bug in `censor_state.make_sdtm_fields()`**: an unrecognised censor
  state passed through as *quantifiable*, emitting a numeric `LBSTRESN` for a censored result
  — the exact invalid-SDTM case §1 warns about. It now normalises the documented synonym
  (`measurable` → `quantifiable`) and raises on anything else.
- Suite still 4/4.

## 2026-10-15 17:11 (supervisor)
- **`SKILL.md` re-synced.** The previous terminology pass on this file was overwritten ~21s
  after it ran (its mtime post-dated every other file the pass touched), so the file still
  carried the old vocabulary and — more seriously — pointed 8 times at
  `component_to_sdtm.py` / `sdtm_to_component.py`, which had just been renamed. The agent
  would have followed its own instructions straight into missing files.
- Re-applied as **targeted replacements rather than a bulk transform**, to leave the
  `biomarker_component[]` record-shape block untouched and to preserve hand edits
  (`author:` retained as-is). Title updated to match the skill name; "artifacts" → "outputs"
  where it mirrored the README.
- **Suite back to 4/4** — the install symlink now resolves.

## 2026-10-15 17:08 (supervisor) — terminology: "component" → "record set"
- **Resolved the vocabulary split** flagged earlier. The three-part output (tBCO + rBCO +
  BMKB record) is now consistently the **record set** across `SKILL.md`, `README.md`, the
  `references/` docs and the script docstrings.
- **Scripts renamed:** `component_to_sdtm.py` → `record_set_to_sdtm.py`,
  `sdtm_to_component.py` → `sdtm_to_record_set.py`; the entry point
  `convert_component_to_sdtm()` → `convert_record_set_to_sdtm()`.
- **Deliberately NOT renamed** — these are BiomarkerKB *schema field names*, not our concept:
  `biomarker_component`, `biomarker_component_new`, `component_index`, and the tBCO's own
  `"components"` key in the assay extension. Verified they survived the pass intact.
- Historical entries below keep the old wording.

## 2026-10-15 16:57 (supervisor) — renamed `bco-generator` → `biomarker-sdtm`

- **Why:** `bco-generator` led with jargon nobody outside the project recognises, and worked
  against the README's own positioning (lead with SDTM, then reveal the standard). The new
  name states the mainstream function and scopes it to the domain.
- **Scope of change:** the SKILL.md `name:` field (also the slash command and install key),
  the README title/tree/slash examples, the `references/` headings, the dev harness's
  triggering check, and the repository directory. Historical entries below keep the old name.
- No script logic depended on the name — the harness locates the skill by its `SKILL.md`.

## 2026-10-15 16:07 (supervisor)

- **`README.md` revised** for a Claude-skill audience: BCO and BiomarkerKB named in the
  opening line; "etc." added to the SDTM domain list with a note that `BM` is a proposed
  Biomarker domain; the three-part output renamed the **biomarker record set** (no longer
  "artifacts") and superscripted ¹²³ in the diagram with a matching legend spelling out
  _template_ and _run_; install instructions rewritten for Claude (clone → ZIP → upload →
  `/bco-generator`); funding attribution added (BioCompute: FDA through 2026; BiomarkerKB:
  NIH CFDE, ongoing) with the _Patterns_ paper linked; funding moved into a GitHub `[!NOTE]`
  callout; Status section removed.
- **Outstanding:** the BioCompute Portal URL is not recorded anywhere in the project material
  and is left as a placeholder.

## 2026-10-15 15:25 (supervisor)

- **`README.md` rewritten** around the SDTM workflow as the headline, with the BCO and
  BiomarkerKB standards introduced after it as portable by-products; added short
  what-it-is / who-funds-it / why-it-matters-clinically descriptions and a resource list.
  Diagram converted from ASCII to Mermaid.
- **Stale `inputs/` paths fixed** in `examples/README.md` (4) and `fixtures/README.md` (1)
  after the rename to `fixtures/`.

## 2026-10-15 15:12 (supervisor)

- **Gold standard keeps real attribution** — reverted the earlier anonymisation of the
  reference package: the tBCO/rBCO contributors and the BMKB record's `provider`/`author`
  name the actual authors again. Gold artifacts are evidence, so they record who produced
  them. (Both BCOs re-finalized; their etags changed with the content.)
- **Shipped the full SDTMIG v3.4 specification** into the skill as
  `references/sdtmig-v3.4.pdf` (upstream name `SDTMIG v3.4-FINAL_2022-07-21.pdf`), so the
  agent can consult the source when the distilled `sdtmig-guide.md` is not sufficient.
  `sdtmig-guide.md` now points at it.

## 2026-10-15 14:59 (supervisor) — repo restructure + pre-release version

- \*\*Version reset to `0.1.0`.
- **Repository root moved to the skill.** `examples/` and `fixtures/` (was `inputs/`) moved
  inside `bco-generator/` so a clone is self-contained; the scripts no longer reach above
  the skill for either. Dev notes, source material and `_archive/` now sit outside the repo.
- **`references/` pruned to agent-facing material only** — the unsent provider question
  draft and the BEST source PDF moved out to `_dev/`.
- **`scripts/` pruned to the agent's runtime path** — the verification harness moved out to
  `_dev/`.
- **`DEVLOG.md` → `CHANGELOG.md`**; personal names removed throughout the repo.

## 2026-10-15 13:42 (supervisor) — architecture change: agent authors, scripts finalize

- **Decision (project owner):** the skill's caller is an LLM agent, so the intermediate
  "input schema" hop is gone. The agent now fills the templates **directly**; scripts keep
  only the parts that must be exact.
- **Retired** (archived outside the repo, not deleted): `generate_tbco.py`,
  `generate_rbco.py`, `generate_bmkb.py`. Their `TBcoInput`/`RunData` dataclasses and
  field-mapping layers are gone.
- **New:** `scripts/finalize_draft.py` (strip `//_` annotations + compute/verify etag),
  `scripts/biomarker_accessions.py` (accession table as code, `--self-test`),
  `scripts/validate_bmkb.py` (submission-schema validator with negative controls).
- **Single etag definition:** `SHA-256(canonical JSON with `etag` cleared)` —
  self-describing, key-order independent, idempotent. Replaces three inconsistent
  implementations. The gold tBCO/rBCO were re-finalized to match; `sdtm_to_component.py`
  now imports `compute_etag`.
- **Validator contract fixed:** `validate_bco.py` file-mode treated unfilled `PLACEHOLDER`s
  and `NOTE:` lines as failures even though its docstring promised "warns only" — so no
  gold artifact could ever pass. File mode now fails only on _structural_ errors.
- **`SKILL.md`** rewritten around "you author, the scripts finalize/validate/convert".

## 2026-10-15 13:17 (supervisor)

- **Adjudication log** — split the actor columns: `generated_by` (the model that produced
  the artifact) alongside `decided_by` (the human adjudicator). 6 issues remain `open`.
- **BMKB schema v2** — rewrote `references/bmkb-model.md` + `assets/bmkb_template.json` +
  the gold `Troponin_I_biomarkerKB.json`. Dropped all BiomarkerKB-assigned fields
  (`biomarker_id`, `*_md5`, `biomarker_id_new`, `source_list`), simplified `condition` to
  `{id, name, resource}`, cut `biomarker_component` to five fields, renamed `citation` →
  `provenance` (single object). Both converters updated to match.
- **Accession table** — added the entity-type → resource lookup to `bmkb-model.md` §7 and
  `SKILL.md` Step 4, plus `accession_resource_for()`.
- **Naming/versioning** — convention documented in `references/README.md` (kebab-case docs,
  front-matter `version`/`status`/`updated`, manifest table; a schema bump travels with its
  template and gold example). `references/` gained `schemas/`.
- **Test hygiene** — all self-test output redirected out of `examples/` into
  `fixtures/troponin_I/_output/`.
- **Two gaps surfaced by the refactor, resolved same day:** dropping the entity name and
  evidence from the BMKB record left `BM.BMENTNM` and `BM.BMEVID` empty. Decision: resolve
  the entity name **from the accession** (`assets/entity_names.json` +
  `_resolve_entity_name()`), and take evidence **from the study documents** (new
  `--evidence` flag). `BMASSDTC` re-pointed to `provenance.date`.

## 2026-10-15 12:52 (supervisor)

- **Cleaned `examples/troponin_I/`** — removed all generated/self-test artifacts; the folder
  holds only the 5 validated files.
- **`examples/` = validated-examples database** — added `README.md` and
  `adjudication_log.csv` (agent-vs-gold discrepancy table, pre-seeded with 6 open issues).
- **Hardened the test input set** — removed the human README from the document folder,
  stripped UniProt/DOID accessions and PMIDs from the agent-facing documents, rewrote the
  CSVs with lab-native headers (no longer mirroring SDTM), removed the spoon-fed
  assay-limit block from the data-transfer spec.
- **Accession instruction:** confirmed the skill had **no** rule mapping
  `assessed_entity_type` → id namespace. Only the BiomarkerKB wiki carried it.

## 2026-10-15 11:38 (supervisor)

- **Created a simulated input-document set** (9 files): protocol synopsis, biomarker
  context-of-use, assay instructions-for-use, method validation report, laboratory manual,
  data-transfer spec, results CSV, demographics CSV, README.
- Reverse-engineered from the **Keller 2009 NEJM paper (PMID 19710485, full text)** plus the
  reference package, so the set _contains_ the values behind the fidelity gaps (decision
  rule, evidence citation, assertion date, real assay name).
- Purpose: supply the missing **documents → component** step the self-test never exercised.

## 2026-10-15 11:00 (supervisor)

- **Automated loop paused.** All automated work finished 2026-10-14; the loop then
  re-reported the same blocked manual steps each run.
- **Changelog repaired** — stripped stray artifacts, restored newest-first order.
- **Install path corrected:** the default-profile skill path is `~/.hermes/skills/<name>/`.

## 2026-10-14 17:18 (loop — end of automated work)

- **Phase 5 verification** — 3/3 automated checks PASS: Functional, Round-trip, Schema.
  Fixed a `validate_bco.py` sentinel bug. 2 manual steps remained.
- **Phase 4 complete** — `SKILL.md` full rewrite: description + trigger phrases, 6-step
  forward workflow, 4-step reverse workflow, worked example, troubleshooting entries.

## 2026-10-14 (loop)

- `censor_state.py` — value↔zone + SDTM field mapping, forward and reverse.
- `validate_bco.py` — IEEE 2791 validator (8-domain structure, etag, placeholders,
  jsonschema). Self-test pass.
- `sdtm_to_component.py` — reverse: 4 SDTM TSVs → component. Self-test 13/13.
- `component_to_sdtm.py` — forward: component → DM/LB/SUPPLB/BM TSVs. Self-test pass.
- Template generators for tBCO / rBCO / BMKB with self-tests.
- All four JSON templates created and validated.
- `pitfalls.md`, `bmkb-model.md` created; BM-domain notes merged into `sdtmig-guide.md`.

## 2026-10-13 17:42 (loop)

- **Phase 0 complete** — schemas pinned, BEST Resource downloaded, provider questions drafted.
- Fetched and stored all 8 IEEE 2791 JSON schemas; wrote `bco-schema.md`.
- Extracted borrowable code from the upstream [BCO-RAG repository](https://github.com/biocompute-objects/bco-rag).

## 2026-10-13 17:01 (loop)

- Studied the SDTMIG v3.4 PDF; created `references/sdtmig-guide.md`.

## 2026-10-13 17:07 (supervisor)

- **Cadence change** — the development loop moved to hourly (08:00–22:00 ET).

## 2026-10-13 16:48 (supervisor)

- Recorded decisions: use the latest schema; **AMI is the correct
  condition**; SDTM domains derived from the SDTM guides; the skill need not be standalone
  (BiomarkerKB MCP in development); target Claude, test on Hermes.
- Revised the plan; added the persistence protocol; created the development-loop job.

## 2026-10-13 16:01 (supervisor)

- **Organised materials**: source material, the validated example, and design notes.
- **Merged** the earlier design document into the project context analysis.
- **Created the skill scaffold** (`SKILL.md` + `references/`, `scripts/`, `assets/`).
- **Created** the plan and the development log.

## 2026-10-08 (session start)

- Compiled project context and a short summary.
- Explored the reference links (BiomarkerKB format, the Anthropic skill guide, and the
  `sbl-sdsc/mcp-okn` blueprint).
- Received the **Troponin I worked example** (5 files) from the data provider.
- Located the upstream BCO-RAG repository → **decision: drop RAG**.
- Confirmed scope (documents → tBCO + rBCO + BMKB; bi-directional SDTM;
  no RAG).
