#!/usr/bin/env python3
"""grade_run.py — score an agent's output folder against the gold example.

Grades what is checkable and ignores wording:

1. files: a tBCO, rBCOs, a BMKB record and the SDTM TSVs are present
2. validators: validate_bco / validate_bmkb pass, etags verify
3. SDTM: every cell of the gold xlsx (DM, LB, SUPPLB, BM). BMEVID compares as a citation
   (first author, year, volume and first page), since documents may abbreviate it
4. record set: controlled fields only (codes, identifiers, limits, units, roles, rule
   text, censor states, timings). Free-text fields (handling, rationales, error notes)
   are not graded.

Usage
-----
    python scripts/grade_run.py <run_folder> [--gold examples/troponin_I]
    python scripts/grade_run.py --self-test

Exit code 0 when everything graded matches; 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import record_set_to_sdtm as fwd  # noqa: E402
import sdtm_to_record_set as rev  # noqa: E402
import validate_bco  # noqa: E402
import validate_bmkb  # noqa: E402
from finalize_draft import verify_etag  # noqa: E402

DEFAULT_GOLD = os.path.join(_HERE, "..", "examples", "troponin_I")
SDTM_KEYS = {"DM": ("USUBJID",), "LB": ("USUBJID", "LBSEQ"),
             "SUPPLB": ("USUBJID", "IDVAR", "IDVARVAL", "QNAM"), "BM": ("BMID",)}
SKIP_DIRS = {"roundtrip", "reconstructed", "rec", "_output"}


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def find_outputs(folder: str) -> dict[str, Any]:
    """Classify the run's files by content, ignoring round-trip folders."""
    found: dict[str, Any] = {"tbco": None, "rbcos": [], "bmkb": None, "sdtm_dir": None,
                             "roundtrip": []}
    for root, dirs, files in os.walk(folder):
        rel_parts = set(os.path.relpath(root, folder).split(os.sep))
        in_roundtrip = bool(rel_parts & SKIP_DIRS)
        for f in sorted(files):
            p = os.path.join(root, f)
            if f in ("LB.tsv", "BM.tsv") and not in_roundtrip:
                found["sdtm_dir"] = root
            if not f.endswith(".json") or "draft" in f.lower():
                continue
            try:
                obj = json.load(open(p))
            except (OSError, ValueError):
                continue
            if not isinstance(obj, dict):
                continue
            kind = ("tbco" if fwd.assay_ext(obj) else "rbco" if fwd.run_ext(obj)
                    else "bmkb" if "biomarker_component" in obj else None)
            if kind is None:
                continue
            if in_roundtrip:
                found["roundtrip"].append((kind, p, obj))
            elif kind == "rbco":
                found["rbcos"].append((p, obj))
            else:
                found[kind] = (p, obj)
    return found


# ---------------------------------------------------------------------------
# Comparators
# ---------------------------------------------------------------------------

def same(a: Any, b: Any) -> bool:
    a = "" if a is None else a
    b = "" if b is None else b
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return str(a).strip() == str(b).strip()


def _citation_key(s: str) -> tuple:
    s = str(s or "")
    author = (re.match(r"\s*([A-Za-z\-']+)", s) or [None, ""])[1].lower()
    nums = re.findall(r"\d+", s)
    year = next((n for n in nums if len(n) == 4 and n.startswith(("19", "20"))), "")
    rest = [n for n in nums if n != year]
    return author, year, tuple(rest[:2])   # volume, (issue or first page)


def same_citation(a: Any, b: Any) -> bool:
    if same(a, b):
        return True
    ka, kb = _citation_key(a), _citation_key(b)
    return bool(ka[0]) and ka[0] == kb[0] and ka[1] == kb[1] and ka[2][:1] == kb[2][:1]


class Score:
    def __init__(self) -> None:
        self.sections: dict[str, list[int]] = {}
        self.diffs: list[str] = []

    def check(self, section: str, label: str, got: Any, exp: Any, cmp=same) -> None:
        s = self.sections.setdefault(section, [0, 0])
        s[1] += 1
        if cmp(got, exp):
            s[0] += 1
        else:
            self.diffs.append(f"[{section}] {label}: run {str(got)[:80]!r} | gold {str(exp)[:80]!r}")

    def ok(self) -> bool:
        return all(m == t for m, t in self.sections.values())


# ---------------------------------------------------------------------------
# Grading
# ---------------------------------------------------------------------------

def _xlsx_rows(path: str, sheet: str) -> list[dict]:
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True)
    rows = [r for r in wb[sheet].iter_rows(values_only=True) if any(v is not None for v in r)]
    h = next(i for i, r in enumerate(rows) if r[0] == "STUDYID")
    header = [c for c in rows[h] if c is not None]
    data = rows[h + 1:]
    if data and all(v in ("S", "T", "R", "K", "N") for v in data[0][:len(header)]):
        data = data[1:]
    return [dict(zip(header, r)) for r in data]


def grade(run: str, gold: str) -> Score:
    sc = Score()
    out = find_outputs(run)

    # 1. files
    for label, present in (("tBCO", out["tbco"]), ("rBCO", out["rbcos"]), ("BMKB record", out["bmkb"]),
                           ("SDTM folder", out["sdtm_dir"])):
        sc.check("files", label, "present" if present else "missing", "present")
    gold_t = fwd.load_json(os.path.join(gold, "Troponin_I_tBCO.json"))
    gold_r = {fwd.run_ext(o)["usubjid"]: o for o in
              (fwd.load_json(os.path.join(gold, f)) for f in sorted(os.listdir(gold)) if f.endswith("_rBCO.json"))}
    gold_b = fwd.load_json(os.path.join(gold, "Troponin_I_biomarkerKB.json"))

    # 2. validators
    bcos = ([out["tbco"]] if out["tbco"] else []) + out["rbcos"]
    for p, obj in bcos:
        bad = [m for m in validate_bco.validate_bco(obj) if not validate_bco._is_warning(m)]
        sc.check("validators", f"validate_bco {os.path.basename(p)}", "; ".join(bad[:2]) or "pass", "pass")
        sc.check("validators", f"etag {os.path.basename(p)}", "ok" if verify_etag(obj) else "mismatch", "ok")
    if out["bmkb"]:
        bad = validate_bmkb.validate(out["bmkb"][1])
        sc.check("validators", "validate_bmkb", "; ".join(bad[:2]) or "pass", "pass")
    for kind, p, obj in out["roundtrip"]:
        bad = (validate_bmkb.validate(obj) if kind == "bmkb"
               else [m for m in validate_bco.validate_bco(obj) if not validate_bco._is_warning(m)])
        sc.check("round trip", f"validates {os.path.basename(p)}", "; ".join(bad[:2]) or "pass", "pass")

    # 3. SDTM cells
    xlsx = os.path.join(gold, "Troponin_I_SDTM.xlsx")
    if out["sdtm_dir"]:
        for dom, keys in SDTM_KEYS.items():
            path = os.path.join(out["sdtm_dir"], f"{dom}.tsv")
            ours = rev.read_tsv(path) if os.path.exists(path) else []
            key = lambda r: "/".join(str(r.get(c)) for c in keys)  # noqa: E731
            o = {key(r): r for r in ours}
            for kk, g in ((key(r), r) for r in _xlsx_rows(xlsx, dom)):
                for col, val in g.items():
                    cmp = same_citation if col == "BMEVID" else same
                    sc.check("SDTM", f"{dom}[{kk}].{col}", (o.get(kk) or {}).get(col, "<row missing>"), val, cmp)

    # 4. record set, controlled fields
    if out["tbco"]:
        t, gt = fwd.assay_ext(out["tbco"][1]), fwd.assay_ext(gold_t)
        g = lambda d, *ks: _dig(d, ks)  # noqa: E731
        for path in (("target", "lbtestcd"), ("target", "lbtest"), ("target", "entity_type"),
                     ("target", "matrix", "curie"), ("specimen_requirements", "specimen_type"),
                     ("specimen_requirements", "specimen_curie"), ("assay", "assay_name"),
                     ("assay", "manufacturer"), ("assay", "platform"), ("assay", "method"),
                     ("assay", "loinc_code"), ("reporting_convention", "unit")):
            sc.check("tBCO", ".".join(path), g(t, *path), g(gt, *path))
        sc.check("tBCO", "analyte_identifiers", sorted(i.get("curie") for i in t["target"].get("analyte_identifiers") or []),
                 sorted(i.get("curie") for i in gt["target"].get("analyte_identifiers") or []))
        for lim in ("limit_of_detection", "limit_of_quantitation", "upper_limit_of_quantitation"):
            for f in ("value", "unit"):
                sc.check("tBCO", f"{lim}.{f}", g(t, "analytical_performance", lim, f), g(gt, "analytical_performance", lim, f))
        rl = lambda x: sorted((r.get("direction"), r.get("value"), r.get("unit")) for r in x.get("reference_limits") or [])  # noqa: E731
        sc.check("tBCO", "reference_limits", rl(t), rl(gt))
        rules = lambda x: sorted((r.get("role"), r.get("display")) for r in x.get("interpretation_rules") or [])  # noqa: E731
        sc.check("tBCO", "interpretation_rules (role, display)", rules(t), rules(gt))
    by_subject = {fwd.run_ext(o).get("usubjid"): o for _, o in out["rbcos"]}
    for u, go in gold_r.items():
        ro = by_subject.get(u)
        sc.check("rBCO", f"{u} present", "present" if ro else "missing", "present")
        if not ro:
            continue
        e, ge = fwd.run_ext(ro), fwd.run_ext(go)
        sc.check("rBCO", f"{u} object_id", ro.get("object_id"), go.get("object_id"))
        sc.check("rBCO", f"{u} derived_from", ro["provenance_domain"].get("derived_from"),
                 go["provenance_domain"].get("derived_from"))
        for f in ("run_id", "studyid"):
            sc.check("rBCO", f"{u} {f}", e.get(f), ge.get(f))
        srt = lambda ms: sorted(ms or [], key=lambda m: str(m.get("collection_dtc")))  # noqa: E731
        for f in ("specimen_id", "collection_dtc", "visit", "visitnum", "censor_state", "lbtestcd"):
            sc.check("rBCO", f"{u} measurements.{f}", [m.get(f) for m in srt(e.get("measurements"))],
                     [m.get(f) for m in srt(ge.get("measurements"))])
    if out["bmkb"]:
        b = out["bmkb"][1]
        for f in ("id", "name", "resource"):
            sc.check("BMKB", f"condition.{f}", (b.get("condition") or {}).get(f), gold_b["condition"][f])
        sc.check("BMKB", "roles", sorted(r.get("role") for r in b.get("best_biomarker_role") or []),
                 sorted(r["role"] for r in gold_b["best_biomarker_role"]))
        c, gc = (b.get("biomarker_component") or [{}])[0], gold_b["biomarker_component"][0]
        for f in ("assessed_biomarker_entity_id", "assessed_entity_type", "biomarker"):
            sc.check("BMKB", f, c.get(f), gc[f])
    return sc


def _dig(d: Any, keys: tuple) -> Any:
    for k in keys:
        d = d.get(k) if isinstance(d, dict) else None
    return d


def report(sc: Score) -> None:
    for name, (m, t) in sc.sections.items():
        print(f"  {'PASS' if m == t else 'FAIL'}  {name:<11} {m}/{t}")
    for d in sc.diffs:
        print(f"        {d}")
    print("[PASS] run matches the gold on every graded field" if sc.ok()
          else f"[FAIL] {len(sc.diffs)} graded difference(s)")


# ---------------------------------------------------------------------------
# Self-test: a run built from the gold scores 100%; one wrong censor state is caught
# ---------------------------------------------------------------------------

def _self_test() -> int:
    import run_checks
    with tempfile.TemporaryDirectory() as tmp:
        for f in os.listdir(DEFAULT_GOLD):
            if f.endswith(".json"):
                shutil.copy(os.path.join(DEFAULT_GOLD, f), tmp)
        t, rs, b = fwd.gold_inputs()
        with open(os.path.devnull, "w") as dn:
            old, sys.stdout = sys.stdout, dn
            try:
                fwd.write_all(fwd.convert(t, rs, b, run_checks.study_data_from_fixtures()), os.path.join(tmp, "sdtm"))
            finally:
                sys.stdout = old
        sc = grade(tmp, DEFAULT_GOLD)
        if not sc.ok():
            print("[SELF-TEST] FAILED: a run built from the gold does not score 100%")
            report(sc)
            return 1
        p = os.path.join(tmp, "Troponin_I_patient1_rBCO.json")
        o = json.load(open(p))
        fwd.run_ext(o)["measurements"][0]["censor_state"] = "quantifiable"
        json.dump(o, open(p, "w"))
        bad = grade(tmp, DEFAULT_GOLD)
        if not any("censor_state" in d for d in bad.diffs):
            print("[SELF-TEST] FAILED: a wrong censor state was not caught")
            return 1
    if not same_citation("Keller T et al. N Engl J Med 2009;361(9):868-877",
                         "Keller T, Zeller T, Peetz D, et al. Sensitive troponin I assay. N Engl J Med. 2009;361(9):868–877."):
        print("[SELF-TEST] FAILED: abbreviated citation should match")
        return 1
    if same_citation("Smith J. Lancet 2009;361:868", "Keller T. N Engl J Med 2009;361:868"):
        print("[SELF-TEST] FAILED: different first author should not match")
        return 1
    print(f"[SELF-TEST] PASSED — gold-built run scores {sum(m for m, _ in sc.sections.values())}/"
          f"{sum(t for _, t in sc.sections.values())}; wrong censor state caught; citation matching")
    return 0


def main() -> int:
    if "--self-test" in sys.argv:
        return _self_test()
    p = argparse.ArgumentParser(description="Score an agent run folder against the gold example.")
    p.add_argument("run_folder")
    p.add_argument("--gold", default=DEFAULT_GOLD)
    a = p.parse_args()
    sc = grade(a.run_folder, a.gold)
    report(sc)
    return 0 if sc.ok() else 1


if __name__ == "__main__":
    sys.exit(main())
