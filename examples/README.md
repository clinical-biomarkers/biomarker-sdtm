# examples/ — Validated Examples Database

This folder is the **curated, expert-validated reference set** for the BCO skill. It is the
ground truth that future agents must learn from and be evaluated against.

> **Rule:** only *human-validated* artifacts belong here. Generated output, scratch files, and
> test runs go under `../fixtures/` (or a scratch dir) — never here. Keep this folder clean.

## Structure

```
examples/
├── README.md                 # this file
├── adjudication_log.csv      # decisions on agent-vs-gold discrepancies
└── <example_name>/           # one validated example per folder
    ├── <name>_tBCO.json          # the validated template BCO
    ├── <name>_patient1_rBCO.json # the validated run BCO
    ├── <name>_biomarkerKB.json   # the validated BMKB record
    ├── <name>_SDTM.xlsx          # the validated SDTM output
    └── <name>_readme.txt         # human index of the example
```

Each example is a **complete, validated input→output pair**: the clinical inputs that produced
it live under `../fixtures/<example_name>/`, and the validated outputs live here.

## What "validated" means

An artifact is validated only when a domain expert (e.g. the SDTM / biomarker reviewer) has
reviewed it against a real clinical source. Until then it is a draft and does not belong here.

## Adding an example

1. Put the clinical input documents under `../fixtures/<example_name>/`.
2. Add the validated outputs here under `examples/<example_name>/`.
3. Add a `readme` describing the example and its provenance.
4. Record any known limitations in `adjudication_log.csv`.

## Adjudication log (`adjudication_log.csv`)

When an agent's output **differs from the human gold standard**, that discrepancy is recorded
here and adjudicated. This is the audit trail of how the skill's output was reconciled with
expert judgement.

Columns:

- `issue_id` — stable id (e.g. `TROPI-001`)
- `example` — which example folder it concerns
- `artifact` — which output (tBCO / rBCO / BMKB / SDTM-BM / …)
- `field_path` — the exact field, e.g. `BM.BMRULE`
- `agent_value` — what the agent produced
- `gold_value` — what the human gold standard says
- `discrepancy_type` — information-loss | wrong-value | naming | casing | structural
- `status` — open | raised | resolved | accepted-as-is
- `decision` — the adjudicated outcome (agent fixed / gold changed / tolerated)
- `decided_by` — who adjudicated (name/role)
- `decided_at` — ISO date
- `rationale` — why

**Workflow:** agent run → diff against gold → open a row per discrepancy → human adjudicates →
decision + rationale recorded → the skill or the gold is updated accordingly.

## Related

- `../fixtures/` — simulated/real clinical inputs and test outputs (not validated)
- `../PLAN.md`, `../DEVLOG.md` — project plan and log
