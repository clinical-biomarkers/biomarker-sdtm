#!/usr/bin/env python3
"""record_set_to_sdtm.py — record set (tBCO + rBCOs + BMKB) + study data → SDTM TSVs.

Inputs
------
- one tBCO (assay specification)
- one or more rBCOs (one per subject per analytical run)
- one BMKB record (biomarker knowledge)
- one study-data file (``assets/study_data_template.json``): demographics,
  result values as reported, and the claim metadata. It is an intermediate
  for this conversion only: BCOs and BMKB records never carry demographics or
  result values.

Outputs (in --output-dir): DM.tsv, <XX>.tsv, SUPP<XX>.tsv, BM.tsv, where XX
is the findings domain (LB by default; see --domain).

Before building anything the converter checks the fields it cannot work
without (missing-value policy in SKILL.md) and exits 1 listing every gap.

Usage
-----
    python scripts/record_set_to_sdtm.py --tbco tBCO.json \\
        --rbco rBCO_001.json rBCO_002.json --bmkb BMKB.json \\
        --study-data study_data.json --output-dir ./sdtm
    python scripts/record_set_to_sdtm.py --self-test

Mapping reference: references/sdtmig-guide.md.
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
from typing import Any, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from censor_state import (censor_state_for_reported, fmt_number, make_sdtm_fields,  # noqa: E402
                          normalise_censor_state, parse_reported)
from finalize_draft import strip_comments  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
_TROPI = os.path.join(_HERE, "..", "examples", "troponin_I")
_ENTITY_NAMES_PATH = os.path.join(_HERE, "..", "assets", "entity_names.json")

#: Specimen-based findings domains this converter can emit by prefix. All share
#: the generic specimen-based layout (SDTMIG 6.3.5.1); domain-specific variables
#: (e.g. GFGENREF for GF) must be added by hand.
SUPPORTED_DOMAINS = ("LB", "IS", "GF", "CP", "BS", "PC")

DM_COLUMNS = ["STUDYID", "DOMAIN", "USUBJID", "SUBJID", "RFSTDTC", "RFXSTDTC", "SITEID",
              "AGE", "AGEU", "SEX", "RACE", "ETHNIC", "COUNTRY"]
# Findings columns, written with "--" replaced by the domain prefix.
FINDINGS_COLUMNS = ["STUDYID", "DOMAIN", "USUBJID", "--SEQ", "--GRPID", "--REFID", "--TESTCD",
                    "--TEST", "--CAT", "--ORRES", "--ORRESU", "--LLOD", "--STRESC", "--STRESN",
                    "--STRESU", "--STNRLO", "--STNRHI", "--NRIND", "--SPEC", "--METHOD", "--NAM",
                    "--LOINC", "--LOBXFL", "--BLFL", "--LLOQ", "--ULOQ", "VISITNUM", "VISIT", "--DTC"]
SUPP_COLUMNS = ["STUDYID", "RDOMAIN", "USUBJID", "IDVAR", "IDVARVAL", "QNAM", "QLABEL", "QVAL",
                "QORIG", "QEVAL"]
BM_COLUMNS = ["STUDYID", "DOMAIN", "BMID", "BMVER", "BMENTNM", "BMENTID", "BMENTTP", "BMCVTERM",
              "BMROLE", "BMCOND", "BMCONDID", "BMASSAY", "BMNAM", "BMPLAT", "BMMETHOD", "BMSPEC",
              "BMSRCDOM", "BMSRCVAR", "BMSRCVAL", "BMSRCVR2", "BMSRCVL2", "BMBCOID", "BMRULE",
              "BMEVID", "BMASSRT", "BMASSDTC"]


# ---------------------------------------------------------------------------
# Record-set access (one place for every path into the JSON)
# ---------------------------------------------------------------------------

def load_json(path: str) -> dict:
    if not os.path.exists(path):
        raise ValueError(f"file not found: {path}")
    with open(path) as f:
        return strip_comments(json.load(f))


def _ext(bco: dict, key: str) -> dict:
    for item in bco.get("extension_domain") or []:
        if isinstance(item, dict) and isinstance(item.get(key), dict):
            return item[key]
    return {}


def assay_ext(tbco: dict) -> dict:
    return _ext(tbco, "assay_protocol_extension")


def run_ext(rbco: dict) -> dict:
    return _ext(rbco, "assay_run_extension")


def filled(v: Any) -> bool:
    """A real value: not None, not empty, not a PLACEHOLDER string."""
    if v is None:
        return False
    if isinstance(v, str):
        return bool(v.strip()) and "PLACEHOLDER" not in v
    return True


def _val(v: Any) -> Any:
    return v if filled(v) else ""


def make_grpid(name: str) -> str:
    """Group ID from an assay name, e.g. 'TnI-Ultra' -> 'TNIULTRA'."""
    return re.sub(r"[^A-Za-z0-9]", "", name).upper()[:20]


class Spec:
    """The fields of a tBCO the conversion reads."""

    def __init__(self, tbco: dict):
        ape = assay_ext(tbco)
        target, assay = ape.get("target") or {}, ape.get("assay") or {}
        ap = ape.get("analytical_performance") or {}
        self.object_id = tbco.get("object_id", "")
        self.testcd = target.get("lbtestcd")
        self.test = target.get("lbtest")
        self.assay_name = assay.get("assay_name")
        self.platform = assay.get("platform")
        self.method = assay.get("method")
        self.manufacturer = assay.get("manufacturer")
        self.loinc = assay.get("loinc_code")
        self.specimen = (ape.get("specimen_requirements") or {}).get("specimen_type")
        self.unit = (ape.get("reporting_convention") or {}).get("unit")
        self.lod = (ap.get("limit_of_detection") or {}).get("value")
        self.lloq = (ap.get("limit_of_quantitation") or {}).get("value")
        self.uloq = (ap.get("upper_limit_of_quantitation") or {}).get("value")
        self.ref_hi = self.ref_lo = None
        for rl in ape.get("reference_limits") or []:
            if not filled(rl.get("value")):
                continue
            if rl.get("direction") == "upper":
                self.ref_hi = rl["value"]
            elif rl.get("direction") == "lower":
                self.ref_lo = rl["value"]
        self.rules = ape.get("interpretation_rules") or []
        self.grpid = make_grpid(self.assay_name) if filled(self.assay_name) else ""

    def rule_for(self, role: str) -> str:
        """Human-readable rule for a BEST role: the rule tagged with it, else an untagged one."""
        tagged = [r for r in self.rules if r.get("role") == role]
        untagged = [r for r in self.rules if not r.get("role")]
        for r in tagged or untagged:
            text = r.get("display") or r.get("expression")
            if filled(text):
                return text
        return ""


def preflight(spec: Spec, rbcos: list[dict], bmkb: dict, study: dict, evidence: list[str]) -> list[str]:
    """Every converter-critical gap, as one message each (empty list = go)."""
    gaps = []
    need = {"tBCO target.lbtestcd (CDISC CT)": spec.testcd, "tBCO target.lbtest (CDISC CT)": spec.test,
            "tBCO assay.assay_name": spec.assay_name, "tBCO reporting_convention.unit": spec.unit,
            "tBCO specimen_requirements.specimen_type": spec.specimen,
            "tBCO limit_of_detection": spec.lod, "tBCO limit_of_quantitation": spec.lloq,
            "tBCO upper_limit_of_quantitation": spec.uloq}
    gaps += [f"{k} is unfilled" for k, v in need.items() if not filled(v) or v == 0]
    if filled(spec.testcd) and not re.match(r"^[A-Z_][A-Z0-9_]{0,7}$", str(spec.testcd)):
        gaps.append(f"tBCO target.lbtestcd {spec.testcd!r} breaks --TESTCD rules (<= 8 chars, A-Z0-9_)")
    cond = bmkb.get("condition") or {}
    for k in ("id", "name"):
        if not filled(cond.get(k)):
            gaps.append(f"BMKB condition.{k} is unfilled")
    roles = [r.get("role") for r in bmkb.get("best_biomarker_role") or []]
    if not roles or not all(filled(r) for r in roles):
        gaps.append("BMKB best_biomarker_role is unfilled")
    if not evidence:
        gaps.append("no evidence id (study_data claim.evidence or --evidence)")
    if not rbcos:
        gaps.append("no rBCO given")
    dm_ids = {d.get("usubjid") for d in study.get("dm") or []}
    for rb in rbcos:
        u = run_ext(rb).get("usubjid")
        if not filled(u):
            gaps.append(f"rBCO {rb.get('object_id', '?')} has no usubjid")
        elif u not in dm_ids:
            gaps.append(f"subject {u} has an rBCO but no row in study_data dm")
    return gaps


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def _nrind(state: str, value: Optional[float], spec: Spec) -> str:
    """Reference-range indicator against the tBCO reference limits (strict comparisons)."""
    hi, lo = spec.ref_hi, spec.ref_lo
    if hi is None and lo is None:
        return ""
    if state == "below_lod":
        if lo is not None and spec.lod is not None and spec.lod <= lo:
            return "LOW"
        return "NORMAL" if hi is not None else ""
    if state == "above_uloq":
        return "HIGH" if hi is not None and spec.uloq is not None and spec.uloq >= hi else ""
    if value is None:
        return ""
    if hi is not None and value > hi:
        return "HIGH"
    if lo is not None and value < lo:
        return "LOW"
    return "NORMAL"


def _results_index(study: dict) -> dict[tuple[str, str], dict]:
    return {(r.get("usubjid"), r.get("specimen_id")): r for r in study.get("results") or []}


def build_findings(spec: Spec, rbcos: list[dict], study: dict, dom: str = "LB") -> list[dict]:
    """One findings row per rBCO measurement, LBSEQ restarting at 1 per subject."""
    results = _results_index(study)
    rfx = {d.get("usubjid"): d.get("rfxstdtc") for d in study.get("dm") or []}
    category = (study.get("study") or {}).get("category")
    rows: list[dict] = []
    for rb in sorted(rbcos, key=lambda r: run_ext(r).get("usubjid", "")):
        ext = run_ext(rb)
        studyid, usubjid = ext.get("studyid", ""), ext.get("usubjid", "")
        seq_start = sum(1 for r in rows if r["USUBJID"] == usubjid)
        measurements = sorted(ext.get("measurements") or [],
                              key=lambda m: (str(m.get("collection_dtc", "")), int(m.get("idvarval", 0))))
        for n, m in enumerate(measurements, start=seq_start + 1):
            state = normalise_censor_state(m.get("censor_state", ""))
            res = results.get((usubjid, m.get("specimen_id")))
            if res is None:
                raise ValueError(f"{usubjid} specimen {m.get('specimen_id')}: no result in study_data")
            reported = str(res.get("result", "")).strip()
            op, number = parse_reported(reported)
            if number is not None:
                expected = censor_state_for_reported(reported, spec.lod, spec.lloq, spec.uloq)
                if expected != state:
                    raise ValueError(f"{usubjid} specimen {m.get('specimen_id')}: result {reported} is "
                                     f"{expected} against the tBCO limits, but the rBCO says {state}")
            stresc, stresn = make_sdtm_fields(state, number if op is None else None,
                                              spec.lod, spec.lloq, spec.uloq)
            unit = res.get("unit") or spec.unit
            if filled(spec.unit) and unit != spec.unit:
                raise ValueError(f"{usubjid} specimen {m.get('specimen_id')}: unit {unit} differs from "
                                 f"the tBCO unit {spec.unit}; convert before loading")
            rows.append({
                "STUDYID": studyid, "DOMAIN": dom, "USUBJID": usubjid,
                "--SEQ": n, "--GRPID": spec.grpid, "--REFID": _val(m.get("specimen_id")),
                "--TESTCD": spec.testcd, "--TEST": str(spec.test)[:40], "--CAT": _val(category),
                "--ORRES": reported or stresc, "--ORRESU": _val(unit),
                "--LLOD": fmt_number(spec.lod), "--STRESC": stresc,
                "--STRESN": "" if stresn is None else stresn, "--STRESU": _val(spec.unit),
                "--STNRLO": "" if spec.ref_lo is None else spec.ref_lo,
                "--STNRHI": "" if spec.ref_hi is None else spec.ref_hi,
                "--NRIND": _nrind(state, stresn, spec), "--SPEC": _val(spec.specimen),
                "--METHOD": _val(spec.method), "--NAM": _val(spec.manufacturer),
                "--LOINC": _val(spec.loinc), "--LOBXFL": "",
                "--BLFL": "Y" if n == 1 else "",
                "--LLOQ": spec.lloq, "--ULOQ": spec.uloq,
                "VISITNUM": _val(m.get("visitnum")), "VISIT": _val(m.get("visit")),
                "--DTC": _val(m.get("collection_dtc")),
                "_censor": state, "_rbco": rb.get("object_id", ""),
            })
        # Last observation before first exposure, when the study gives a product.
        start = rfx.get(usubjid)
        if filled(start):
            before = [r for r in rows if r["USUBJID"] == usubjid and r["--DTC"]
                      and r["--DTC"] < start and r["--STRESC"] != ""]
            if before:
                max(before, key=lambda r: r["--DTC"])["--LOBXFL"] = "Y"
    return rows


def build_supp(spec: Spec, rows: list[dict], dom: str = "LB") -> list[dict]:
    """Assay-level qualifiers once per subject (keyed on --GRPID); CENSOR per result (--SEQ)."""
    out: list[dict] = []

    def add(row: dict, idvar: str, idvarval: Any, qnam: str, qlabel: str, qval: Any,
            qorig: str, qeval: str) -> None:
        out.append({"STUDYID": row["STUDYID"], "RDOMAIN": dom, "USUBJID": row["USUBJID"],
                    "IDVAR": idvar, "IDVARVAL": idvarval, "QNAM": qnam, "QLABEL": qlabel,
                    "QVAL": qval, "QORIG": qorig, "QEVAL": qeval})

    seen: set[str] = set()
    for row in rows:
        if row["USUBJID"] not in seen:
            seen.add(row["USUBJID"])
            add(row, f"{dom}GRPID", spec.grpid, "ASSAYNAM", "Assay Name", spec.assay_name,
                "Assigned", "VENDOR")
            if filled(spec.platform):
                add(row, f"{dom}GRPID", spec.grpid, "ASSAYPLT", "Assay Platform", spec.platform,
                    "Assigned", "VENDOR")
            add(row, f"{dom}GRPID", spec.grpid, "RBCOID", "Run BCO Identifier", row["_rbco"],
                "Assigned", "SPONSOR")
    for row in rows:
        add(row, f"{dom}SEQ", row["--SEQ"], "CENSOR", "Censoring State", row["_censor"],
            "Derived", "SPONSOR")
    return out


def _entity_names() -> dict:
    try:
        with open(_ENTITY_NAMES_PATH) as f:
            return strip_comments(json.load(f))
    except FileNotFoundError:
        return {}
    except ValueError as e:
        raise ValueError(f"{_ENTITY_NAMES_PATH} is not valid JSON: {e}") from e


def _next_id(base: str, i: int) -> str:
    m = re.match(r"^(.*?)(\d+)$", base or "")
    if not m:
        return base if i == 0 else f"{base}-{i + 1}"
    return f"{m.group(1)}{int(m.group(2)) + i:0{len(m.group(2))}d}"


def build_bm(spec: Spec, bmkb: dict, study: dict, studyid: str, evidence: list[str],
             dom: str = "LB") -> list[dict]:
    """One BM row per BEST role in the BMKB record."""
    claim = study.get("claim") or {}
    comps = bmkb.get("biomarker_component") or [{}]
    comp = comps[0]
    cond = bmkb.get("condition") or {}
    roles = [r.get("role", "") for r in bmkb.get("best_biomarker_role") or []]
    name = _entity_names().get(comp.get("assessed_biomarker_entity_id", ""), "")
    rows = []
    for i, role in enumerate(roles):
        rows.append({
            "STUDYID": studyid, "DOMAIN": "BM",
            "BMID": _next_id(claim.get("bmid", ""), i), "BMVER": _val(claim.get("bmver")),
            "BMENTNM": name, "BMENTID": comp.get("assessed_biomarker_entity_id", ""),
            "BMENTTP": comp.get("assessed_entity_type", ""), "BMCVTERM": comp.get("biomarker", ""),
            "BMROLE": role.upper(), "BMCOND": cond.get("name", ""), "BMCONDID": cond.get("id", ""),
            "BMASSAY": spec.assay_name, "BMNAM": _val(spec.manufacturer), "BMPLAT": _val(spec.platform),
            "BMMETHOD": _val(spec.method), "BMSPEC": _val(spec.specimen),
            "BMSRCDOM": dom, "BMSRCVAR": f"{dom}TESTCD", "BMSRCVAL": spec.testcd,
            "BMSRCVR2": "ASSAYNAM", "BMSRCVL2": spec.assay_name, "BMBCOID": spec.object_id,
            "BMRULE": spec.rule_for(role), "BMEVID": ", ".join(evidence),
            "BMASSRT": _val(claim.get("asserted_by")), "BMASSDTC": _val(claim.get("assertion_date")),
        })
    return rows


def build_dm(study: dict, studyid: str) -> list[dict]:
    rows = []
    for d in study.get("dm") or []:
        row = {c: _val(d.get(c.lower())) for c in DM_COLUMNS}
        row.update(STUDYID=studyid, DOMAIN="DM")
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def findings_columns(dom: str) -> list[str]:
    return [c.replace("--", dom) for c in FINDINGS_COLUMNS]


def finalize_findings(rows: list[dict], dom: str) -> list[dict]:
    """Rename '--' keys to the domain prefix and drop internal fields."""
    return [{c.replace("--", dom): v for c, v in r.items() if not c.startswith("_")} for r in rows]


def write_tsv(rows: list[dict], columns: list[str], path: str) -> None:
    """Tab-separated, header always written, minimal quoting."""
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns, delimiter="\t", quoting=csv.QUOTE_MINIMAL,
                           extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({c: ("" if r.get(c) is None else r.get(c)) for c in columns})
    print(f"[DONE] wrote {path} ({len(rows)} rows)")


def convert(tbco: dict, rbcos: list[dict], bmkb: dict, study: dict,
            evidence: Optional[list[str]] = None, dom: str = "LB") -> dict[str, list[dict]]:
    """Build every dataset in memory; raise ValueError on any converter-critical gap."""
    if dom not in SUPPORTED_DOMAINS:
        raise ValueError(f"--domain {dom} not supported; choose from {list(SUPPORTED_DOMAINS)}")
    spec = Spec(tbco)
    ev = [e for e in (list(evidence or []) or list((study.get("claim") or {}).get("evidence") or []))
          if filled(e)]
    gaps = preflight(spec, rbcos, bmkb, study, ev)
    if gaps:
        raise ValueError("cannot convert; fill these first:\n  - " + "\n  - ".join(gaps))
    studyid = run_ext(rbcos[0]).get("studyid", "") or (study.get("study") or {}).get("studyid", "")
    findings = build_findings(spec, rbcos, study, dom)
    return {
        "DM": build_dm(study, studyid),
        dom: finalize_findings(findings, dom),
        "SUPP" + dom: build_supp(spec, findings, dom),
        "BM": build_bm(spec, bmkb, study, studyid, ev, dom),
    }


def write_all(datasets: dict[str, list[dict]], output_dir: str, dom: str = "LB") -> None:
    os.makedirs(output_dir, exist_ok=True)
    cols = {"DM": DM_COLUMNS, dom: findings_columns(dom), "SUPP" + dom: SUPP_COLUMNS, "BM": BM_COLUMNS}
    for name, rows in datasets.items():
        write_tsv(rows, cols[name], os.path.join(output_dir, f"{name}.tsv"))


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

SELF_TEST_STUDY = {
    "study": {"studyid": "BM-2026-01", "category": "CHEMISTRY"},
    "claim": {"bmid": "BM-001", "bmver": "1.0", "asserted_by": "Sponsor Biomarker Review Board",
              "assertion_date": "2026-09-01", "evidence": ["PMID:19710485"]},
    "dm": [
        {"usubjid": "BM-2026-01-001", "subjid": "001", "siteid": "01", "age": 67, "ageu": "YEARS",
         "sex": "M", "country": "DEU", "rfstdtc": "2026-03-15"},
        {"usubjid": "BM-2026-01-002", "subjid": "002", "siteid": "01", "age": 44, "ageu": "YEARS",
         "sex": "F", "country": "DEU", "rfstdtc": "2026-03-16"},
    ],
    "results": [
        {"usubjid": "BM-2026-01-001", "specimen_id": "S-0001-T1", "result": "0.021", "unit": "ng/mL"},
        {"usubjid": "BM-2026-01-001", "specimen_id": "S-0001-T2", "result": "0.058", "unit": "ng/mL"},
        {"usubjid": "BM-2026-01-001", "specimen_id": "S-0001-T3", "result": "0.094", "unit": "ng/mL"},
        {"usubjid": "BM-2026-01-002", "specimen_id": "S-0002-T1", "result": "<0.006", "unit": "ng/mL"},
        {"usubjid": "BM-2026-01-002", "specimen_id": "S-0002-T2", "result": "0.008", "unit": "ng/mL"},
        {"usubjid": "BM-2026-01-002", "specimen_id": "S-0002-T3", "result": "0.045", "unit": "ng/mL"},
    ],
}


def gold_inputs() -> tuple[dict, list[dict], dict]:
    tbco = load_json(os.path.join(_TROPI, "Troponin_I_tBCO.json"))
    rbcos = [load_json(os.path.join(_TROPI, f"Troponin_I_patient{i}_rBCO.json")) for i in (1, 2)]
    bmkb = load_json(os.path.join(_TROPI, "Troponin_I_biomarkerKB.json"))
    return tbco, rbcos, bmkb


def _self_test() -> int:
    import copy
    errors: list[str] = []
    tbco, rbcos, bmkb = gold_inputs()
    ds = convert(tbco, rbcos, bmkb, SELF_TEST_STUDY)
    lb, supp, bm, dm = ds["LB"], ds["SUPPLB"], ds["BM"], ds["DM"]

    def check(label: str, got: Any, expected: Any) -> None:
        if str(got) != str(expected):
            errors.append(f"{label}: got {got!r}, expected {expected!r}")

    check("LB rows", len(lb), 6)
    check("DM rows", len(dm), 2)
    expected = [  # (USUBJID suffix, LBSEQ, LBORRES, LBSTRESN, LBNRIND, LBBLFL, censor)
        ("001", 1, "0.021", 0.021, "NORMAL", "Y", "detected_below_lloq"),
        ("001", 2, "0.058", 0.058, "HIGH", "", "quantifiable"),
        ("001", 3, "0.094", 0.094, "HIGH", "", "quantifiable"),
        ("002", 1, "<0.006", "", "NORMAL", "Y", "below_lod"),
        ("002", 2, "0.008", 0.008, "NORMAL", "", "detected_below_lloq"),
        ("002", 3, "0.045", 0.045, "HIGH", "", "quantifiable"),
    ]
    censors = [r for r in supp if r["QNAM"] == "CENSOR"]
    for row, cen, exp in zip(lb, censors, expected):
        key = f"LB[{exp[0]}/{exp[1]}]"
        check(f"{key}.USUBJID", row["USUBJID"][-3:], exp[0])
        check(f"{key}.LBSEQ", row["LBSEQ"], exp[1])
        check(f"{key}.LBORRES", row["LBORRES"], exp[2])
        check(f"{key}.LBSTRESN", row["LBSTRESN"], exp[3])
        check(f"{key}.LBNRIND", row["LBNRIND"], exp[4])
        check(f"{key}.LBBLFL", row["LBBLFL"], exp[5])
        check(f"{key} CENSOR", cen["QVAL"], exp[6])
        check(f"{key} CENSOR IDVARVAL", cen["IDVARVAL"], row["LBSEQ"])
    r0 = lb[0]
    for col, exp in (("LBTESTCD", "TROPONI3"), ("LBTEST", "Troponin I Type 3"), ("LBGRPID", "TNIULTRA"),
                     ("LBSPEC", "SERUM"), ("LBLLOD", "0.006"), ("LBLLOQ", 0.03), ("LBULOQ", 50),
                     ("VISITNUM", 1), ("LBLOBXFL", "")):
        check(f"LB[0].{col}", r0[col], exp)
    qnams = sorted({r["QNAM"] for r in supp})
    check("SUPPLB QNAMs", qnams, ["ASSAYNAM", "ASSAYPLT", "CENSOR", "RBCOID"])
    check("SUPPLB rows", len(supp), 2 * 3 + 6)
    check("BM rows (one per role)", [r["BMROLE"] for r in bm], ["DIAGNOSTIC", "PROGNOSTIC"])
    check("BM ids", [r["BMID"] for r in bm], ["BM-001", "BM-002"])
    check("BM[0].BMRULE", bm[0]["BMRULE"], "Value > 0.04 ng/mL AND rise or fall >= 30% within 6 h")
    check("BM[0].BMSRCVAL", bm[0]["BMSRCVAL"], "TROPONI3")
    check("BM[0].BMENTNM", bm[0]["BMENTNM"], "Troponin I, cardiac muscle")

    # Preflight: a missing critical field stops the run with a message naming it.
    bad = copy.deepcopy(tbco)
    assay_ext(bad)["analytical_performance"]["upper_limit_of_quantitation"]["value"] = None
    try:
        convert(bad, rbcos, bmkb, SELF_TEST_STUDY)
        errors.append("preflight did not stop on a null ULOQ")
    except ValueError as e:
        if "upper_limit_of_quantitation" not in str(e):
            errors.append(f"preflight message does not name the ULOQ: {e}")
    # A result that contradicts the rBCO censor state is caught.
    wrong = copy.deepcopy(SELF_TEST_STUDY)
    wrong["results"][0]["result"] = "0.5"
    try:
        convert(tbco, rbcos, bmkb, wrong)
        errors.append("did not catch a result that contradicts its censor state")
    except ValueError:
        pass
    # Another specimen-based findings domain by prefix.
    is_ds = convert(tbco, rbcos, bmkb, SELF_TEST_STUDY, dom="IS")
    check("IS prefix", sorted(is_ds), ["BM", "DM", "IS", "SUPPIS"])
    check("IS BMSRCVAR", is_ds["BM"][0]["BMSRCVAR"], "ISTESTCD")

    out = os.path.join(_HERE, "..", "fixtures", "troponin_I", "_output", "sdtm_self_test")
    write_all(ds, out)
    if errors:
        print("[SELF-TEST] FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("[SELF-TEST] PASSED — 2 subjects, censoring, limits in LB, one BM row per role, "
          "preflight, IS prefix")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="Record set + study data -> SDTM TSVs.")
    p.add_argument("--tbco")
    p.add_argument("--rbco", nargs="+", help="one rBCO per subject per run")
    p.add_argument("--bmkb")
    p.add_argument("--study-data", help="filled assets/study_data_template.json")
    p.add_argument("--domain", default="LB", help=f"findings domain prefix: {', '.join(SUPPORTED_DOMAINS)}")
    p.add_argument("--evidence", default="", help="comma-separated ids; overrides study_data claim.evidence")
    p.add_argument("--output-dir", default="./sdtm")
    p.add_argument("--self-test", action="store_true")
    a = p.parse_args()
    if a.self_test:
        return _self_test()
    if not (a.tbco and a.rbco and a.bmkb and a.study_data):
        p.error("--tbco, --rbco, --bmkb and --study-data are required (or --self-test)")
    try:
        datasets = convert(load_json(a.tbco), [load_json(x) for x in a.rbco], load_json(a.bmkb),
                           load_json(a.study_data),
                           [e.strip() for e in a.evidence.split(",") if e.strip()], a.domain.upper())
    except ValueError as e:
        print(f"[ERROR] {e}")
        return 1
    if a.domain.upper() != "LB":
        print(f"[NOTE] {a.domain.upper()} uses the generic specimen-based layout. Add the variables "
              f"that domain requires by hand (see references/sdtmig-guide.md §2 for the PDF page).")
    write_all(datasets, a.output_dir, a.domain.upper())
    return 0


if __name__ == "__main__":
    sys.exit(main())
