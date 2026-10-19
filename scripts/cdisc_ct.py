#!/usr/bin/env python3
"""cdisc_ct.py — look up CDISC Controlled Terminology in the shipped extract (offline).

The extract (references/cdisc-ct/sdtm_ct_extract.tsv) holds the codelists this skill
fills: LBTESTCD/LBTEST, ISTESTCD/ISTEST, GFTESTCD/GFTEST, SPECTYPE, UNIT and METHOD,
from the NCI EVS SDTM Terminology release named in references/cdisc-ct/README.md.

Usage
-----
    python scripts/cdisc_ct.py search "cardiac troponin I"            # LBTESTCD by default
    python scripts/cdisc_ct.py search "serum" --codelist SPECTYPE
    python scripts/cdisc_ct.py check LBTESTCD TROPONI3                # exit 0 if it is a CT term
    python scripts/cdisc_ct.py --self-test

Choose the term whose name and synonyms match the analyte in the documents. If no
term fits, the codelists are extensible: use a sponsor-defined value, keep it
within the --TESTCD rules, and report it.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys

EXTRACT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "references",
                       "cdisc-ct", "sdtm_ct_extract.tsv")
CODELISTS = ("LBTESTCD", "ISTESTCD", "GFTESTCD", "SPECTYPE", "UNIT", "METHOD")
_ROWS: list[dict] | None = None


def rows() -> list[dict]:
    global _ROWS
    if _ROWS is None:
        with open(EXTRACT, newline="", encoding="utf-8") as f:
            _ROWS = list(csv.DictReader(f, delimiter="\t"))
    return _ROWS


def _tokens(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (s or "").lower()))


def search(term: str, codelist: str = "LBTESTCD", limit: int = 10) -> list[dict]:
    """Terms of *codelist* ranked by how well their names and synonyms match *term*."""
    q = term.strip().lower()
    qt = _tokens(term)
    scored = []
    for r in rows():
        if r["codelist"] != codelist:
            continue
        names = [r["submission_value"], r["paired_name"], r["nci_preferred_term"],
                 *[s.strip() for s in r["synonyms"].split(";") if s.strip()]]
        exact = any(n.lower() == q for n in names if n)
        overlap = max((len(qt & _tokens(n)) / max(len(qt | _tokens(n)), 1) for n in names if n), default=0)
        if exact or overlap > 0:
            scored.append((not exact, -overlap, r["submission_value"], r))
    scored.sort(key=lambda x: x[:3])
    return [r for *_, r in scored[:limit]]


def check(codelist: str, value: str) -> dict | None:
    """The CT row for *value* in *codelist* (exact submission value), or None."""
    for r in rows():
        if r["codelist"] == codelist and r["submission_value"] == value:
            return r
    return None


def synonym_of(codelist: str, value: str) -> dict | None:
    """The CT row whose synonyms include *value* (e.g. UNIT 'ng/mL' -> submission value 'ug/L')."""
    v = value.strip().lower()
    for r in rows():
        if r["codelist"] == codelist and v in [s.strip().lower() for s in r["synonyms"].split(";")]:
            return r
    return None


def ct_notes(pairs: list[tuple[str, str, str]]) -> list[str]:
    """Notes for (codelist, value, field) values that are not CT submission values."""
    notes = []
    for codelist, value, field in pairs:
        if not value or check(codelist, value):
            continue
        syn = synonym_of(codelist, value)
        if syn:
            notes.append(f"{field} {value!r} is a CDISC synonym; the {codelist} submission value is "
                         f"{syn['submission_value']!r} ({syn['c_code']})")
        else:
            notes.append(f"{field} {value!r} is not in CDISC {codelist}; report it as sponsor-defined")
    return notes


def _self_test() -> int:
    errors = []
    top = search("cardiac troponin I")
    if not top or top[0]["submission_value"] != "TROPONI3":
        errors.append(f"cardiac troponin I -> {top[0]['submission_value'] if top else None}, expected TROPONI3")
    if (check("LBTESTCD", "TROPONI3") or {}).get("paired_name") != "Troponin I Type 3":
        errors.append("TROPONI3 should pair with 'Troponin I Type 3'")
    if not check("SPECTYPE", "SERUM"):
        errors.append("SERUM missing from SPECTYPE")
    if (synonym_of("UNIT", "ng/mL") or {}).get("submission_value") != "ug/L":
        errors.append("UNIT ng/mL should resolve to the submission value ug/L")
    if not ct_notes([("UNIT", "ng/mL", "unit")]) or ct_notes([("SPECTYPE", "SERUM", "specimen")]):
        errors.append("ct_notes should flag ng/mL and accept SERUM")
    if check("LBTESTCD", "TNNI3"):
        errors.append("TNNI3 (a gene symbol) should not be a lab test code")
    if errors:
        print("[SELF-TEST] FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"[SELF-TEST] PASSED — {len(rows())} CT rows; search, pairing and check work")
    return 0


def main() -> int:
    if "--self-test" in sys.argv:
        return _self_test()
    p = argparse.ArgumentParser(description="Look up CDISC CT in the shipped extract.")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search")
    s.add_argument("term")
    s.add_argument("--codelist", default="LBTESTCD", choices=CODELISTS)
    s.add_argument("--limit", type=int, default=10)
    c = sub.add_parser("check")
    c.add_argument("codelist", choices=CODELISTS)
    c.add_argument("value")
    a = p.parse_args()
    if a.cmd == "check":
        r = check(a.codelist, a.value)
        if not r:
            syn = synonym_of(a.codelist, a.value)
            if syn:
                print(f"[SYNONYM] {a.value!r} is a synonym; the CT submission value is "
                      f"{syn['submission_value']!r} ({syn['c_code']})")
                return 3
            print(f"[NOT CT] {a.value!r} is not in {a.codelist}: if no CT term fits, keep it as a "
                  f"sponsor-defined value and report it")
            return 1
        print(f"[OK] {r['submission_value']} ({r['c_code']})" + (f" = {r['paired_name']}" if r["paired_name"] else ""))
        return 0
    hits = search(a.term, a.codelist, a.limit)
    if not hits:
        print(f"[NONE] no {a.codelist} term matches {a.term!r}")
        return 2
    for r in hits:
        pair = f" | {r['paired_name']}" if r["paired_name"] else ""
        print(f"{r['submission_value']:<12} {r['c_code']:<9}{pair} | {r['synonyms'][:70]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
