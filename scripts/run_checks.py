#!/usr/bin/env python3
"""run_checks.py — Run every script self-test plus the gold SDTM comparison.

1. Runs each script's ``--self-test`` in a subprocess, in dependency order
   (``record_set_to_sdtm`` writes the TSVs that ``sdtm_to_record_set`` reads).
2. Gold comparison: converts the gold Troponin I record set (both subjects)
   to LB / SUPPLB / BM, with study data built from the fixture CSVs, and
   compares every cell against Troponin_I_SDTM.xlsx. DM is not compared: it is
   passed through from the study data unchanged.

Exit code: 0 if everything passes, 1 otherwise.

Usage
-----
    python scripts/run_checks.py
"""

from __future__ import annotations

import csv
import os
import subprocess
import sys
from typing import Any

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import record_set_to_sdtm as fwd  # noqa: E402

_ROOT = os.path.join(_HERE, "..")
_GOLD = os.path.join(_ROOT, "examples", "troponin_I")
_FIXTURES = os.path.join(_ROOT, "fixtures", "troponin_I")

SELF_TESTS = [
    "censor_state.py",
    "finalize_draft.py",
    "biomarker_accessions.py",
    "ols_lookup.py",          # offline; `--self-test --live` also queries OLS
    "cdisc_ct.py",
    "validate_bmkb.py",
    "validate_bco.py",
    "record_set_to_sdtm.py",
    "sdtm_to_record_set.py",  # reads the TSVs record_set_to_sdtm.py writes
]

# Cells where the converter is right and the gold xlsx is not. Each entry is
# reported but not counted as a failure; remove it once the xlsx is corrected.
KNOWN_GOLD_DEVIATIONS: dict[tuple[str, str], str] = {}


# ---------------------------------------------------------------------------
# Self-tests
# ---------------------------------------------------------------------------

def run_self_tests() -> list[str]:
    failed = []
    for script in SELF_TESTS:
        proc = subprocess.run(
            [sys.executable, os.path.join(_HERE, script), "--self-test"],
            capture_output=True, text=True,
        )
        if proc.returncode == 0:
            print(f"  PASS  {script}")
            continue
        failed.append(script)
        print(f"  FAIL  {script} (exit {proc.returncode})")
        tail = (proc.stdout + proc.stderr).strip().splitlines()[-25:]
        for line in tail:
            print(f"        | {line}")
    return failed


# ---------------------------------------------------------------------------
# Gold comparison
# ---------------------------------------------------------------------------

def _xlsx_sheet(wb: Any, name: str) -> list[dict[str, Any]]:
    """Rows of one gold sheet as dicts.

    Each sheet has a caption row, then the header row (starts with STUDYID),
    then on some sheets a provenance-letter row (S/T/R/K/N), then data.
    """
    rows = [r for r in wb[name].iter_rows(values_only=True)
            if any(v is not None for v in r)]
    h = next(i for i, r in enumerate(rows) if r[0] == "STUDYID")
    header = [c for c in rows[h] if c is not None]
    data = rows[h + 1:]
    if data and all(v in ("S", "T", "R", "K", "N") for v in data[0][:len(header)]):
        data = data[1:]
    return [dict(zip(header, r)) for r in data]


def _same(a: Any, b: Any) -> bool:
    """Cell equality: None == "", and numbers compare numerically."""
    a = "" if a is None else a
    b = "" if b is None else b
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return str(a) == str(b)


def study_data_from_fixtures() -> dict:
    """The study-data intermediate an agent would build from the two fixture CSVs.

    Shows the column mapping the lab files need (their headers are lab-native,
    not SDTM): samp_id -> specimen_id, subject -> USUBJID suffix, result as
    reported, Years -> YEARS, gender -> sex, Germany -> DEU.
    """
    study_id = "BM-2026-01"
    dm = []
    with open(os.path.join(_FIXTURES, "08_demographics.csv"), newline="") as f:
        for row in csv.DictReader(f):
            dm.append({"usubjid": f"{study_id}-{row['subject']}", "subjid": row["subject"],
                       "siteid": row["site"], "age": int(row["age"]), "ageu": row["age_unit"].upper(),
                       "sex": row["gender"], "country": {"Germany": "DEU"}.get(row["country"], row["country"]),
                       "rfstdtc": row["first_visit_dt"]})
    results = []
    with open(os.path.join(_FIXTURES, "07_lab_results.csv"), newline="") as f:
        for row in csv.DictReader(f):
            results.append({"usubjid": f"{study_id}-{row['subject']}", "specimen_id": row["samp_id"],
                            "result": row["result"].strip(), "unit": row["unit"]})
    return {"study": {"studyid": study_id, "category": "CHEMISTRY"},
            "claim": {"bmid": "BM-001", "bmver": "1.0", "asserted_by": "Sponsor Biomarker Review Board",
                      "assertion_date": "2026-09-01", "evidence": ["PMID:19710485"]},
            "dm": dm, "results": results}


def compare_gold() -> tuple[int, list[str], list[str]]:
    """Return (cells compared, failures, known deviations)."""
    try:
        import openpyxl
    except ImportError:
        return 0, ["openpyxl is not installed (pip install openpyxl)"], []

    tbco, rbcos, bmkb = fwd.gold_inputs()
    ds = fwd.convert(tbco, rbcos, bmkb, study_data_from_fixtures())

    wb = openpyxl.load_workbook(os.path.join(_GOLD, "Troponin_I_SDTM.xlsx"), data_only=True)
    gold = {name: _xlsx_sheet(wb, name) for name in ("LB", "SUPPLB", "BM")}

    n = 0
    failures: list[str] = []
    known: list[str] = []

    def cmp(domain: str, key: str, col: str, got: Any, exp: Any) -> None:
        nonlocal n
        n += 1
        if _same(got, exp):
            return
        msg = f"{domain}[{key}].{col}: got {got!r}, gold {exp!r}"
        if (domain, col) in KNOWN_GOLD_DEVIATIONS:
            known.append(f"{msg} ({KNOWN_GOLD_DEVIATIONS[(domain, col)]})")
        else:
            failures.append(msg)

    def cmp_rows(domain: str, ours: list[dict], theirs: list[dict], key_cols: tuple) -> None:
        def key(r: dict) -> str:
            return "/".join(str(r.get(c)) for c in key_cols)
        ours_by = {key(r): r for r in ours}
        theirs_by = {key(r): r for r in theirs}
        for k in sorted(set(ours_by) | set(theirs_by)):
            if k not in ours_by:
                failures.append(f"{domain}[{k}]: in gold, not produced")
            elif k not in theirs_by:
                failures.append(f"{domain}[{k}]: produced, not in gold")
            else:
                for col in theirs_by[k]:
                    cmp(domain, k, col, ours_by[k].get(col, "<missing column>"),
                        theirs_by[k][col])

    cmp_rows("LB", ds["LB"], gold["LB"], ("USUBJID", "LBSEQ"))
    cmp_rows("SUPPLB", ds["SUPPLB"], gold["SUPPLB"], ("USUBJID", "IDVAR", "IDVARVAL", "QNAM"))
    cmp_rows("BM", ds["BM"], gold["BM"], ("BMID",))
    return n, failures, known


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 60)
    print("  Self-tests")
    print("=" * 60)
    failed_tests = run_self_tests()

    print()
    print("=" * 60)
    print("  Gold comparison: forward conversion vs Troponin_I_SDTM.xlsx")
    print("=" * 60)
    n, failures, known = compare_gold()
    for msg in failures:
        print(f"  FAIL  {msg}")
    for msg in known:
        print(f"  KNOWN {msg}")
    print(f"  {n} cells compared: {n - len(failures) - len(known)} match, "
          f"{len(failures)} differ, {len(known)} known gold deviation(s)")

    print()
    ok = not failed_tests and not failures
    if ok:
        print("[PASS] all checks passed")
    else:
        parts = []
        if failed_tests:
            parts.append(f"self-tests failed: {', '.join(failed_tests)}")
        if failures:
            parts.append(f"{len(failures)} gold cell(s) differ")
        print(f"[FAIL] {'; '.join(parts)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
