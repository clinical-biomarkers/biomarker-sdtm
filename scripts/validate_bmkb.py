#!/usr/bin/env python3
"""validate_bmkb.py — validate a BiomarkerKB submission record.

The agent fills ``assets/bmkb_template.json`` directly, so this checks the result
against the submission schema in ``references/bmkb-model.md`` — including the
things that are easy to get wrong: emitting BiomarkerKB-assigned fields, a
non-lowercase condition name, a `biomarker_component` entry with the wrong key set, or an entity
type outside the allowed set.

Usage
-----
    python validate_bmkb.py BMKB.json [more.json ...]
    python validate_bmkb.py --self-test

Exit code 0 = all records valid; 1 = at least one failed.
"""

from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from biomarker_accessions import ENTITY_TYPES, CONDITION_RESOURCES  # noqa: E402

# The submission schema — exactly these top-level keys.
REQUIRED_TOP = {"condition", "best_biomarker_role", "biomarker_component", "provenance"}
OPTIONAL_TOP = {"entity_normal_ranges"}
ALLOWED_TOP = REQUIRED_TOP | OPTIONAL_TOP

# BiomarkerKB assigns these on receipt; a submitter must not emit them.
ASSIGNED = {"biomarker_id", "biomarker_canonical_id", "biomarker_id_md5",
            "canon_id_md5", "biomarker_id_new", "source_list"}

COMPONENT_FIELDS = {"component_index", "entity_index",
                    "assessed_biomarker_entity_id", "assessed_entity_type", "biomarker"}

PROVENANCE_FIELDS = {"provider", "author", "date", "description"}

#: FDA-NIH BEST roles (lowercase), see references/best-definitions.md.
BEST_ROLES = ("diagnostic", "prognostic", "predictive", "monitoring", "safety",
              "susceptibility/risk", "pharmacodynamic/response")

#: Change concepts allowed at the start of the ``biomarker`` statement.
CHANGES = ("increased", "decreased", "elevated", "reduced", "presence", "absence")

_STATEMENT = re.compile(
    r"^(?P<change>\w+)\s+(?P<aspect>\w+)\s+of\s+(?P<type>\S+)\s+"
    r"(?P<symbol>[^/\s]+)/(?P<id>[A-Za-z][A-Za-z0-9]*:\S+)$")


def _placeholders(obj, path: str = "$") -> list[str]:
    """Paths of strings still holding PLACEHOLDER."""
    if isinstance(obj, dict):
        return [p for k, v in obj.items() for p in _placeholders(v, f"{path}.{k}")]
    if isinstance(obj, list):
        return [p for i, v in enumerate(obj) for p in _placeholders(v, f"{path}[{i}]")]
    return [path] if isinstance(obj, str) and "PLACEHOLDER" in obj else []

GOLD = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "..", "examples", "troponin_I", "Troponin_I_biomarkerKB.json")


def warnings(obj: dict) -> list[str]:
    """Unfilled values: allowed in a draft, listed in the hand-over report."""
    return [f"UNFILLED PLACEHOLDER at {p}" for p in _placeholders(obj)]


def validate(obj: dict) -> list[str]:
    """Return a list of problems (empty == valid). See warnings() for unfilled values."""
    errors: list[str] = []

    # 1) top-level key set
    missing = REQUIRED_TOP - set(obj)
    if missing:
        errors.append(f"missing required top-level field(s): {sorted(missing)}")
    notes = sorted(k for k in obj if k.startswith("//_"))
    if notes:
        errors.append(f"template guidance keys left in the record ({len(notes)} //_ keys): run "
                      f"`python scripts/finalize_draft.py --input <draft> --output BMKB.json --no-etag`")
    extra = {k for k in set(obj) - ALLOWED_TOP if not k.startswith("//_")}
    if extra:
        errors.append(f"unexpected top-level field(s): {sorted(extra)}")
    emitted = ASSIGNED & set(obj)
    if emitted:
        errors.append(f"BiomarkerKB-assigned field(s) must not be emitted: {sorted(emitted)}")

    # 2) condition
    cond = obj.get("condition")
    if not isinstance(cond, dict):
        errors.append("condition must be an object")
    else:
        for k in ("id", "name", "resource"):
            if not cond.get(k):
                errors.append(f"condition.{k} is empty")
        name = cond.get("name", "")
        if name and "PLACEHOLDER" not in name and name != name.lower():
            errors.append(f"condition.name must be lowercase: {name!r}")
        cid = cond.get("id", "")
        if cid and "PLACEHOLDER" not in cid and not any(
                cid.startswith(p + ":") for p in CONDITION_RESOURCES):
            errors.append(f"condition.id should be a {'/'.join(CONDITION_RESOURCES)} CURIE: {cid!r}")

    # 3) best_biomarker_role
    roles = obj.get("best_biomarker_role")
    if not isinstance(roles, list) or not roles:
        errors.append("best_biomarker_role must be a non-empty list")
    else:
        for r in roles:
            if not isinstance(r, dict) or not r.get("role"):
                errors.append("each best_biomarker_role entry needs a 'role'")
            elif r["role"] not in BEST_ROLES and "PLACEHOLDER" not in r["role"]:
                errors.append(f"best_biomarker_role {r['role']!r} is not a BEST role "
                              f"(lowercase): {list(BEST_ROLES)}")

    # 4) biomarker_component — exactly five fields
    comps = obj.get("biomarker_component")
    if not isinstance(comps, list) or not comps:
        errors.append("biomarker_component must be a non-empty list")
    else:
        for i, c in enumerate(comps):
            if not isinstance(c, dict):
                errors.append(f"biomarker_component[{i}] must be an object")
                continue
            missing_c = COMPONENT_FIELDS - set(c)
            if missing_c:
                errors.append(f"biomarker_component[{i}] missing: {sorted(missing_c)}")
            extra_c = set(c) - COMPONENT_FIELDS
            if extra_c:
                errors.append(f"biomarker_component[{i}] has disallowed field(s): {sorted(extra_c)}")
            et = c.get("assessed_entity_type", "")
            if et and "PLACEHOLDER" not in et and et not in ENTITY_TYPES:
                errors.append(f"biomarker_component[{i}].assessed_entity_type must be one of "
                              f"{list(ENTITY_TYPES)} (lowercase): {et!r}")
            cv = c.get("biomarker", "")
            if cv and "PLACEHOLDER" not in cv:
                m = _STATEMENT.match(cv)
                if not m:
                    errors.append(f"biomarker_component[{i}].biomarker does not follow "
                                  f"'{{change}} {{aspect}} of {{type}} {{symbol}}/{{PREFIX:id}}': {cv!r}")
                else:
                    if m["change"].lower() not in CHANGES:
                        errors.append(f"biomarker_component[{i}].biomarker change "
                                      f"{m['change']!r} not in {list(CHANGES)}")
                    if et and "PLACEHOLDER" not in et and m["type"] != et:
                        errors.append(f"biomarker_component[{i}].biomarker names type "
                                      f"{m['type']!r} but assessed_entity_type is {et!r}")
                    eid = c.get("assessed_biomarker_entity_id", "")
                    if eid and "PLACEHOLDER" not in eid and m["id"] != eid:
                        errors.append(f"biomarker_component[{i}].biomarker names id "
                                      f"{m['id']!r} but assessed_biomarker_entity_id is {eid!r}")

    # 5) entity_normal_ranges (optional)
    enr = obj.get("entity_normal_ranges")
    if enr is not None and not isinstance(enr, list):
        errors.append("entity_normal_ranges must be a list when present")

    # 6) provenance
    prov = obj.get("provenance")
    if not isinstance(prov, dict):
        errors.append("provenance must be an object (single, not a list)")
    else:
        for k in sorted(PROVENANCE_FIELDS):
            if not prov.get(k):
                errors.append(f"provenance.{k} is empty")

    return errors


def _self_test() -> int:
    failures = []

    if not os.path.exists(GOLD):
        print(f"[SKIP] gold record not found at {GOLD}")
        return 0

    gold = json.load(open(GOLD))
    errs = validate(gold)
    if errs:
        failures.append(f"gold record rejected: {errs}")

    # negative controls — each must be caught
    bad_assigned = dict(gold, biomarker_id="AN6373-1")
    if not validate(bad_assigned):
        failures.append("did not catch a BiomarkerKB-assigned field")

    bad_case = json.loads(json.dumps(gold))
    bad_case["condition"]["name"] = "Acute Myocardial Infarction"
    if not validate(bad_case):
        failures.append("did not catch a non-lowercase condition name")

    bad_comp = json.loads(json.dumps(gold))
    bad_comp["biomarker_component"][0]["assessed_biomarker_entity_url"] = "x"
    if not validate(bad_comp):
        failures.append("did not catch a disallowed biomarker_component field")

    bad_type = json.loads(json.dumps(gold))
    bad_type["biomarker_component"][0]["assessed_entity_type"] = "Protein"
    if not validate(bad_type):
        failures.append("did not catch a non-lowercase entity type")

    bad_role = json.loads(json.dumps(gold))
    bad_role["best_biomarker_role"] = [{"role": "surrogate"}]
    if not validate(bad_role):
        failures.append("did not catch a non-BEST role")

    bad_cv = json.loads(json.dumps(gold))
    bad_cv["biomarker_component"][0]["biomarker"] = "Troponin I"
    if not validate(bad_cv):
        failures.append("did not catch a bare entity name as the biomarker statement")

    bad_id = json.loads(json.dumps(gold))
    bad_id["biomarker_component"][0]["biomarker"] = "Increased level of protein TNNI3/UPKB:P00000"
    if not validate(bad_id):
        failures.append("did not catch a statement id that disagrees with the entity id")

    draft = json.loads(json.dumps(gold))
    draft["provenance"]["author"] = "PLACEHOLDER - author"
    if validate(draft) or not warnings(draft):
        failures.append("PLACEHOLDER should be a warning, not an error or silent")

    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets",
                           "bmkb_template.json")) as f:
        from finalize_draft import strip_comments
        template = strip_comments(json.load(f))
    if validate(template):
        failures.append(f"blank template should validate with warnings only: {validate(template)}")
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets",
                           "bmkb_template.json")) as f:
        raw_template = json.load(f)
    if not any("--no-etag" in e for e in validate(raw_template)):
        failures.append("unstripped template should fail with a pointer to --no-etag")

    if failures:
        print("[SELF-TEST] FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("[SELF-TEST] PASSED — gold accepted; 8 negative controls caught; template is warnings-only")
    return 0


def main() -> None:
    if "--self-test" in sys.argv:
        sys.exit(_self_test())

    files = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not files:
        print("usage: validate_bmkb.py BMKB.json [more.json ...]   |   --self-test")
        sys.exit(1)

    failed = False
    for path in files:
        try:
            obj = json.load(open(path))
        except (OSError, ValueError) as e:
            print(f"FAIL: {path} — {e}")
            failed = True
            continue
        errs, warns = validate(obj), warnings(obj)
        if errs:
            failed = True
            print(f"FAIL: {path}")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"PASS: {path}" + (f" ({len(warns)} unfilled)" if warns else ""))
        for w in warns:
            print(f"  ! {w}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
