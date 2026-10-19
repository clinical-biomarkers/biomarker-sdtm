#!/usr/bin/env python3
"""sdtm_to_record_set.py — SDTM TSVs → record set (tBCO, one rBCO per subject per run, BMKB).

BCOs and BMKB records are public-facing and never hold demographics or result
values (owner decision B08), so this direction rebuilds only what those
objects carry. It does not rebuild results or DM, and it prints what it could
not reconstruct.

Usage
-----
    python scripts/sdtm_to_record_set.py --lb sdtm/LB.tsv --supp sdtm/SUPPLB.tsv \\
        --bm sdtm/BM.tsv --output-dir ./reconstructed [--domain LB]
    python scripts/sdtm_to_record_set.py --self-test

Mapping reference: references/sdtmig-guide.md §7.
"""

from __future__ import annotations

import csv
import json
import os
import sys
from collections import OrderedDict
from typing import Any, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from censor_state import derive_censor_state_from_sdtm  # noqa: E402
from finalize_draft import finalize  # noqa: E402
from biomarker_accessions import RESOURCES  # noqa: E402
from record_set_to_sdtm import filled  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
SPEC_VERSION = "https://w3id.org/ieee/ieee-2791-schema/2791object.json"
PH = "PLACEHOLDER"


#: Not reconstructed, by design or because SDTM does not carry it.
LOSSY = ["result values (LBORRES/LBSTRESN): never stored in a BCO",
         "demographics (DM): never stored in a BCO or BMKB record",
         "BMEVID, BMASSRT and BMASSDTC: the BMKB submission record has no field for them",
         "BMKB provenance (provider, author, record date): not in SDTM",
         "instrument, lots, calibration and QC detail of each run",
         "IFU detail of the assay (handling, stability, interferences, imprecision)"]


def read_tsv(path: str) -> list[dict[str, str]]:
    """Read a TSV written by record_set_to_sdtm.py (minimal or full quoting)."""
    if not os.path.exists(path):
        raise ValueError(f"TSV not found: {path}")
    with open(path, newline="") as f:
        return [{k.strip(): (v or "").strip() for k, v in row.items()}
                for row in csv.DictReader(f, delimiter="\t")]


def _num(s: str) -> Optional[float]:
    try:
        v = float(s)
    except (TypeError, ValueError):
        return None
    return int(v) if v.is_integer() else v


def _or_ph(v: Any) -> Any:
    return v if filled(v) else PH


def _assay_quals(supp: list[dict], dom: str) -> dict[str, str]:
    q: dict[str, str] = {}
    for r in supp:
        if r.get("IDVAR") == f"{dom}GRPID":
            q.setdefault(r["QNAM"], r["QVAL"])
    return q


def _skeleton(object_id: str, name: str, usability: str) -> dict:
    """IEEE 2791 domains with PLACEHOLDER content (schema-valid once finalized)."""
    return {
        "object_id": object_id or PH, "spec_version": SPEC_VERSION, "etag": "",
        "provenance_domain": {
            "name": name, "version": "1.0.0", "license": PH, "created": PH, "modified": PH,
            "contributors": [{"name": PH, "affiliation": PH, "contribution": ["createdBy"],
                              "email": "PLACEHOLDER@example.org"}]},
        "usability_domain": [usability],
        "extension_domain": [],
        "description_domain": {"keywords": [], "xref": [], "pipeline_steps": []},
        "execution_domain": {"script": [], "script_driver": PH,
                             "software_prerequisites": [{"name": PH, "version": PH, "uri": {"uri": PH}}],
                             "external_data_endpoints": [], "environment_variables": {}},
        "io_domain": {"input_subdomain": [], "output_subdomain": []},
        "error_domain": {"empirical_error": {}, "algorithmic_error": {}},
    }


def reconstruct_tbco(rows: list[dict], supp: list[dict], bm: list[dict], dom: str) -> dict:
    first = rows[0] if rows else {}
    q = _assay_quals(supp, dom)
    bm0 = bm[0] if bm else {}
    g = lambda var: first.get(f"{dom}{var}", "")  # noqa: E731
    unit = g("STRESU") or g("ORRESU")
    limit = lambda v: {"value": v, "unit": _or_ph(unit)}  # noqa: E731
    lod = _num(g("LLOD")) if g("LLOD") else _num(q.get("LBLOD", ""))
    lloq = _num(g("LLOQ")) if g("LLOQ") else _num(q.get("LBLLOQ", ""))
    uloq = _num(g("ULOQ")) if g("ULOQ") else _num(q.get("LBULOQ", ""))
    ref = []
    if _num(g("STNRHI")) is not None:
        ref.append({"type": PH, "direction": "upper", "value": _num(g("STNRHI")), "unit": _or_ph(unit),
                    "strata": [], "population": {"source": PH, "n": None}})
    if _num(g("STNRLO")) is not None:
        ref.append({"type": PH, "direction": "lower", "value": _num(g("STNRLO")), "unit": _or_ph(unit),
                    "strata": [], "population": {"source": PH, "n": None}})
    rules = [{"rule_id": f"R{i}", "role": r.get("BMROLE", "").lower(), "outcome": PH,
              "expression": _or_ph(r.get("BMRULE")), "display": _or_ph(r.get("BMRULE")), "components": []}
             for i, r in enumerate(bm, start=1)]
    assay_name = q.get("ASSAYNAM") or bm0.get("BMASSAY", "")
    t = _skeleton(bm0.get("BMBCOID", ""), f"Assay specification for {_or_ph(g('TEST'))} ({_or_ph(assay_name)})",
                  "Reconstructed from SDTM. Only the fields SDTM carries are filled; the rest are PLACEHOLDER.")
    t["extension_domain"] = [{"extension_schema": PH, "assay_protocol_extension": {
        "spec_id": PH, "spec_version": "1.0.0",
        "target": {"analyte_name": _or_ph(bm0.get("BMENTNM")), "lbtestcd": _or_ph(g("TESTCD")),
                   "lbtest": _or_ph(g("TEST")),
                   "analyte_identifiers": [{"curie": bm0["BMENTID"]}] if filled(bm0.get("BMENTID")) else [],
                   "entity_type": _or_ph(bm0.get("BMENTTP")), "measured_property": PH,
                   "matrix": {"term": PH, "curie": PH}, "detects": PH},
        "assay": {"assay_name": _or_ph(assay_name), "manufacturer": _or_ph(g("NAM") or bm0.get("BMNAM")),
                  "platform": _or_ph(q.get("ASSAYPLT") or bm0.get("BMPLAT")),
                  "method": _or_ph(g("METHOD") or bm0.get("BMMETHOD")), "assay_generation": PH,
                  "regulatory_status": PH, "calibration_traceability": PH, "loinc_code": _or_ph(g("LOINC"))},
        "specimen_requirements": {"specimen_type": _or_ph(g("SPEC") or bm0.get("BMSPEC")),
                                  "specimen_curie": PH, "container_additive": PH, "minimum_volume": PH,
                                  "handling": PH, "stability": PH},
        "subject_preconditions": [], "sampling_schedule": {"anchor": PH, "serial_required": None, "timepoints": []},
        "analytical_performance": {"limit_of_detection": limit(lod), "limit_of_quantitation": limit(lloq),
                                   "upper_limit_of_quantitation": limit(uloq)},
        "reference_limits": ref, "interpretation_rules": rules,
        "reporting_convention": {"unit": _or_ph(unit), "decimal_places": None, "censoring": PH}}}]
    t["parametric_domain"] = []
    return finalize(t)


def reconstruct_rbcos(rows: list[dict], supp: list[dict], tbco: dict, dom: str) -> list[dict]:
    """One rBCO per (subject, run), measurements in --SEQ order, no result values."""
    ap = tbco["extension_domain"][0]["assay_protocol_extension"]["analytical_performance"]
    lod, lloq, uloq = (ap[k]["value"] for k in ("limit_of_detection", "limit_of_quantitation",
                                                 "upper_limit_of_quantitation"))
    run_ids = {r["USUBJID"]: r["QVAL"] for r in supp if r.get("QNAM") == "RBCOID"}
    censor = {(r["USUBJID"], r["IDVARVAL"]): r["QVAL"] for r in supp
              if r.get("QNAM") == "CENSOR" and r.get("IDVAR") == f"{dom}SEQ"}
    by_subject: "OrderedDict[str, list[dict]]" = OrderedDict()
    for r in rows:
        by_subject.setdefault(r["USUBJID"], []).append(r)
    out = []
    for usubjid, subj_rows in by_subject.items():
        meas = []
        for r in sorted(subj_rows, key=lambda r: int(r[f"{dom}SEQ"])):
            seq = r[f"{dom}SEQ"]
            state = censor.get((usubjid, seq)) or derive_censor_state_from_sdtm(
                r.get(f"{dom}ORRES", ""), r.get(f"{dom}STRESN", ""), lod, lloq, uloq)
            meas.append({"idvar": f"{dom}SEQ", "idvarval": int(seq), "lbtestcd": r.get(f"{dom}TESTCD", ""),
                         "visitnum": _num(r.get("VISITNUM", "")), "visit": r.get("VISIT", ""),
                         "specimen_id": r.get(f"{dom}REFID", ""), "specimen_type": r.get(f"{dom}SPEC", ""),
                         "collection_dtc": r.get(f"{dom}DTC", ""), "analysis_dtc": PH,
                         "censor_state": state, "repeated": False})
        counts = {s: sum(1 for m in meas if m["censor_state"] == s)
                  for s in ("below_lod", "detected_below_lloq", "above_uloq")}
        rb = _skeleton(run_ids.get(usubjid, ""), f"Run record, subject {usubjid}",
                       f"Reconstructed from SDTM for subject {usubjid}. Instrument, lot, calibration and QC "
                       f"detail are not in SDTM and are PLACEHOLDER.")
        rb["provenance_domain"]["derived_from"] = tbco["object_id"]
        rb["extension_domain"] = [{"extension_schema": PH, "assay_run_extension": {
            "run_id": PH, "studyid": subj_rows[0].get("STUDYID", ""), "usubjid": usubjid,
            "specification": {"tbco_object_id": tbco["object_id"], "spec_id": PH, "spec_version": "1.0.0",
                              "conformance": PH},
            "laboratory": {"name": PH, "accreditation": PH},
            "instrument": {"serial_number": PH, "software_version": PH},
            "consumables": {"reagent_lot": PH, "calibrator_lot": PH},
            "calibration": {"calibrated_dtc": PH, "accepted": None, "record": PH},
            "quality_control": {"accepted": None, "record": PH},
            "measurements": meas, "deviations": []}}]
        rb["error_domain"]["empirical_error"] = {f"measurements_{k}": v for k, v in counts.items()}
        out.append(finalize(rb))
    return out


def reconstruct_bmkb(bm: list[dict]) -> dict:
    if not bm:
        return {}
    b0 = bm[0]
    cid = b0.get("BMCONDID", "")
    roles = list(OrderedDict.fromkeys(r.get("BMROLE", "").lower() for r in bm if r.get("BMROLE")))
    return {
        "condition": {"id": _or_ph(cid), "name": _or_ph(b0.get("BMCOND", "").lower()),
                      "resource": RESOURCES.get(cid.split(":")[0].upper(), (PH,))[0] if ":" in cid else PH},
        "best_biomarker_role": [{"role": r} for r in roles] or [{"role": PH}],
        "biomarker_component": [{"component_index": "1", "entity_index": "1",
                                 "assessed_biomarker_entity_id": _or_ph(b0.get("BMENTID")),
                                 "assessed_entity_type": _or_ph(b0.get("BMENTTP")),
                                 "biomarker": _or_ph(b0.get("BMCVTERM"))}],
        "provenance": {"provider": PH, "author": PH, "date": PH,
                       "description": f"Reconstructed from SDTM BM row(s) {', '.join(r.get('BMID', '') for r in bm)}"},
    }


def convert(rows: list[dict], supp: list[dict], bm: list[dict], dom: str = "LB") -> dict[str, Any]:
    if not rows:
        raise ValueError(f"{dom}.tsv has no rows")
    tbco = reconstruct_tbco(rows, supp, bm, dom)
    return {"tbco": tbco, "rbcos": reconstruct_rbcos(rows, supp, tbco, dom), "bmkb": reconstruct_bmkb(bm)}


def write_out(result: dict, output_dir: str, prefix: str) -> list[str]:
    os.makedirs(output_dir, exist_ok=True)
    paths = []

    def dump(name: str, obj: dict) -> None:
        p = os.path.join(output_dir, name)
        with open(p, "w") as f:
            json.dump(obj, f, indent=2, ensure_ascii=False)
            f.write("\n")
        paths.append(p)

    dump(f"{prefix}_tBCO.json", result["tbco"])
    for rb in result["rbcos"]:
        u = rb["extension_domain"][0]["assay_run_extension"]["usubjid"]
        dump(f"{prefix}_rBCO_{u}.json", rb)
    dump(f"{prefix}_BMKB.json", result["bmkb"])
    return paths


# ---------------------------------------------------------------------------
# Self-test: gold record set -> SDTM -> record set, compared with the gold JSON
# ---------------------------------------------------------------------------

def _self_test() -> int:
    import tempfile
    import record_set_to_sdtm as fwd
    import validate_bco
    import validate_bmkb

    tbco, rbcos, bmkb = fwd.gold_inputs()
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        fwd.write_all(fwd.convert(tbco, rbcos, bmkb, fwd.SELF_TEST_STUDY), tmp)
        res = convert(read_tsv(os.path.join(tmp, "LB.tsv")), read_tsv(os.path.join(tmp, "SUPPLB.tsv")),
                      read_tsv(os.path.join(tmp, "BM.tsv")))

    def check(label: str, got: Any, exp: Any) -> None:
        if got != exp:
            errors.append(f"{label}: got {got!r}, expected {exp!r}")

    gt, rt = fwd.assay_ext(tbco), fwd.assay_ext(res["tbco"])
    for k in ("limit_of_detection", "limit_of_quantitation", "upper_limit_of_quantitation"):
        check(f"tBCO {k}", rt["analytical_performance"][k]["value"], gt["analytical_performance"][k]["value"])
    for k in ("lbtestcd", "lbtest", "entity_type"):
        check(f"tBCO target.{k}", rt["target"][k], gt["target"][k])
    check("tBCO identifiers", rt["target"]["analyte_identifiers"], gt["target"]["analyte_identifiers"])
    for k in ("assay_name", "manufacturer", "platform", "method", "loinc_code"):
        check(f"tBCO assay.{k}", rt["assay"][k], gt["assay"][k])
    check("tBCO specimen", rt["specimen_requirements"]["specimen_type"], gt["specimen_requirements"]["specimen_type"])
    check("tBCO unit", rt["reporting_convention"]["unit"], gt["reporting_convention"]["unit"])
    check("tBCO upper reference limit", rt["reference_limits"][0]["value"], gt["reference_limits"][0]["value"])
    check("tBCO rule roles", [r["role"] for r in rt["interpretation_rules"]],
          [r["role"] for r in gt["interpretation_rules"]])
    check("tBCO rule text", [r["display"] for r in rt["interpretation_rules"]],
          [r["display"] for r in gt["interpretation_rules"]])
    check("tBCO object_id", res["tbco"]["object_id"], tbco["object_id"])

    check("rBCO count (one per subject)", len(res["rbcos"]), len(rbcos))
    for rb_gold, rb_new in zip(rbcos, res["rbcos"]):
        eg, en = fwd.run_ext(rb_gold), fwd.run_ext(rb_new)
        check("rBCO usubjid", en["usubjid"], eg["usubjid"])
        check("rBCO object_id", rb_new["object_id"], rb_gold["object_id"])
        for f in ("specimen_id", "collection_dtc", "visit", "visitnum", "censor_state", "lbtestcd"):
            check(f"{eg['usubjid']} measurements[].{f}", [m[f] for m in en["measurements"]],
                  [m[f] for m in sorted(eg["measurements"], key=lambda m: m["collection_dtc"])])
        for k in ("measurements_below_lod", "measurements_detected_below_lloq", "measurements_above_uloq"):
            check(f"{eg['usubjid']} {k}", rb_new["error_domain"]["empirical_error"][k],
                  rb_gold["error_domain"]["empirical_error"][k])

    nb = res["bmkb"]
    for k in ("id", "name", "resource"):
        check(f"BMKB condition.{k}", nb["condition"][k], bmkb["condition"][k])
    check("BMKB roles", nb["best_biomarker_role"], bmkb["best_biomarker_role"])
    for k in ("assessed_biomarker_entity_id", "assessed_entity_type", "biomarker"):
        check(f"BMKB component.{k}", nb["biomarker_component"][0][k], bmkb["biomarker_component"][0][k])

    for obj in [res["tbco"], *res["rbcos"]]:
        bad = [m for m in validate_bco.validate_bco(obj) if not validate_bco._is_warning(m)]
        if bad:
            errors.append(f"reconstructed BCO {obj['object_id']} fails validate_bco: {bad[:3]}")
    if validate_bmkb.validate(nb):
        errors.append(f"reconstructed BMKB fails validate_bmkb: {validate_bmkb.validate(nb)}")

    if errors:
        print("[SELF-TEST] FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"[SELF-TEST] PASSED — gold -> SDTM -> record set matches the gold on every field SDTM "
          f"carries; {len(res['rbcos'])} rBCOs; outputs validate")
    return 0


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="SDTM TSVs -> record set (no results, no demographics).")
    p.add_argument("--lb", help="findings TSV (LB.tsv, or IS.tsv etc. with --domain)")
    p.add_argument("--supp", "--supplb", dest="supp", help="SUPP<domain>.tsv")
    p.add_argument("--bm", help="BM.tsv")
    p.add_argument("--dm", help="ignored: BCOs carry no demographics (kept for older commands)")
    p.add_argument("--domain", default="LB")
    p.add_argument("--output-dir", default="./reconstructed")
    p.add_argument("--prefix", default="reconstructed")
    p.add_argument("--self-test", action="store_true")
    a = p.parse_args()
    if a.self_test:
        return _self_test()
    if not (a.lb and a.supp and a.bm):
        p.error("--lb, --supp and --bm are required (or --self-test)")
    try:
        res = convert(read_tsv(a.lb), read_tsv(a.supp), read_tsv(a.bm), a.domain.upper())
    except ValueError as e:
        print(f"[ERROR] {e}")
        return 1
    for path in write_out(res, a.output_dir, a.prefix):
        print(f"[DONE] {path}")
    print("\nNot reconstructed:")
    for item in LOSSY:
        print(f"  - {item}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
