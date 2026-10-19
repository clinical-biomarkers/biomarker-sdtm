#!/usr/bin/env python3
"""record_set_to_sdtm.py — Convert a 3-part BCO record set to SDTM tabular datasets.

Takes the generated outputs of the three generators (tBCO, rBCO, BMKB) plus
a results table and optional demographics, and produces four TSV files
(DM, LB, SUPPLB, BM) matching the Troponin I reference example format.

Usage
-----
    python record_set_to_sdtm.py \\
        --tbco ../examples/troponin_I/Troponin_I_tBCO.json \\
        --rbco ../examples/troponin_I/Troponin_I_patient1_rBCO.json \\
        --bmkb ../examples/troponin_I/Troponin_I_biomarkerKB.json \\
        --results results.json \\
        --dm dm.json \\
        --output-dir ./sdtm

    python record_set_to_sdtm.py --self-test

The results JSON is a dict:
    {"results": [
        {"idvarval": 1, "lborres": "0.021", "lbstresc": "0.021", "lbstressn": 0.021},
        ...
    ]}

The DM JSON is a dict:
    {"dm": [
        {"usubjid": "BM-2026-01-001", "subjid": "001", "siteid": "01",
         "age": 67, "ageu": "YEARS", "sex": "M", "country": "DEU",
         "rfstdtc": "2026-03-15"},
        ...
    ]}

Mapping reference: ``references/sdtmig-guide.md``.
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from finalize_draft import strip_comments  # noqa: E402


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_HERE = os.path.dirname(os.path.abspath(__file__))
_TROPI = os.path.join(
    _HERE, "..", "examples", "troponin_I"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_json(path: str) -> dict:
    """Load a JSON file, with helpful error."""
    if not os.path.exists(path):
        print(f"[ERROR] file not found: {path}")
        sys.exit(1)
    with open(path) as f:
        return json.load(f)


def _make_grpid(name: str) -> str:
    """Derive a short group ID from an assay name, e.g. 'TnI-Ultra' → 'TNIULTRA'."""
    cleaned = re.sub(r"[^a-zA-Z0-9]", "", name).upper()
    return cleaned[:20]


def _get_assay_info(ext: dict) -> dict[str, str]:
    """Extract assay name and platform from the extension's assay_protocol_extension.

    The tBCO stores these under the ``assay`` sub-dict as ``assay_name`` and
    ``platform`` (see assets/tbco_template.json).
    Handles missing/None assay section gracefully.
    """
    assay = ext.get("assay") or {}
    aname = assay.get("assay_name") or ""
    aplat = assay.get("platform") or ""
    return {"name": aname, "platform": aplat}


def _lb_grpid(tbco: dict) -> str:
    """Assay group ID — derive from assay name or spec_id."""
    ext = tbco.get("extension_domain", [{}])[0].get("assay_protocol_extension", {})
    info = _get_assay_info(ext)
    aname = info["name"]
    if aname and "PLACEHOLDER" not in aname and aname != "None":
        return _make_grpid(aname)
    spec_id = ext.get("spec_id", "")
    if spec_id and "PLACEHOLDER" not in spec_id:
        return _make_grpid(spec_id)
    return "UNKNOWN"


def _lbtestcd_from_tbco(tbco: dict) -> str:
    """Derive LBTESTCD — from analyte identifiers or assay name."""
    ext = tbco.get("extension_domain", [{}])[0].get("assay_protocol_extension", {})
    target = ext.get("target", {})
    aname = target.get("analyte_name", "")
    if aname and "PLACEHOLDER" not in aname:
        if "troponin" in aname.lower():
            return "TNNI3"
    info = _get_assay_info(ext)
    aname2 = info["name"]
    if aname2 and "PLACEHOLDER" not in aname2 and aname2 != "None":
        return _make_grpid(aname2)[:8]
    spec_id = ext.get("spec_id", "")
    if spec_id and "PLACEHOLDER" not in spec_id:
        return _make_grpid(spec_id)[:8]
    return "XXXBIOM"


def _compute_nrind(value: Optional[float], ref_hi: Optional[float]) -> str:
    """Determine LBNRIND: NORMAL / HIGH / LOW / null."""
    if value is None or ref_hi is None:
        return ""
    if value >= ref_hi:
        return "HIGH"
    if value <= 0:
        return "LOW"
    return "NORMAL"


def _enshorten(s: str, maxlen: int) -> str:
    """Truncate a string to maxlen chars for SDTM variable limits."""
    if len(s) <= maxlen:
        return s
    return s[:maxlen]


def _get_ref_hi(ext: dict) -> Optional[float]:
    """Get the upper reference limit value from the tBCO extension."""
    for rl in ext.get("reference_limits", []):
        if rl.get("direction") == "upper" and rl.get("value"):
            return rl["value"]
    return None


def _get_analytical_perf(ext: dict) -> dict:
    """Get analytical performance limits; an unfilled limit is None (null)."""
    ap = ext.get("analytical_performance") or {}
    return {
        "lod": (ap.get("limit_of_detection") or {}).get("value"),
        "lloq": (ap.get("limit_of_quantitation") or {}).get("value"),
        "uloq": (ap.get("upper_limit_of_quantitation") or {}).get("value"),
    }


# Censored result with no supplied value → (operator, analytical limit) for LBORRES.
_CENSOR_BOUND = {
    "below_lod": ("<", "lod"),
    "detected_below_lloq": ("<", "lloq"),
    "above_uloq": (">", "uloq"),
}


def _sorted_measurements(rbco: dict) -> list[dict]:
    """rBCO measurements in LBSEQ order (by idvarval, chronological).

    build_lb() numbers LB rows in this order, and build_supplb() pairs each
    LB row with its measurement by position, so both must use this helper.
    """
    ext_r = rbco.get("extension_domain", [{}])[0].get("assay_run_extension", {})
    return sorted(ext_r.get("measurements", []),
                  key=lambda m: int(m.get("idvarval", 0)))


# ---------------------------------------------------------------------------
# LB dataset builder
# ---------------------------------------------------------------------------

def build_lb(
    tbco: dict,
    rbco: dict,
    results: list[dict],
    studyid: str,
    usubjid: str,
) -> list[dict]:
    """Build LB rows from the record set model + external result values.

    Returns a list of dicts, each representing one LB record row
    (keys matching the xlsx column headers).
    """
    ext_t = tbco.get("extension_domain", [{}])[0].get("assay_protocol_extension", {})
    # --- tBCO-derived constants for all rows ---
    grpid = _lb_grpid(tbco)
    lbtestcd = _lbtestcd_from_tbco(tbco)

    target = ext_t.get("target", {})
    lbtest = _enshorten(target.get("analyte_name", ""), 40)
    if not lbtest or "PLACEHOLDER" in lbtest:
        lbtest = lbtestcd
    lbcat = "CHEMISTRY"

    # Units
    rc = ext_t.get("reporting_convention", {})
    lborresu = rc.get("unit", "ng/mL") or "ng/mL"
    lbstresu = rc.get("unit", "ng/mL") or "ng/mL"

    # Reference limits
    ref_hi = _get_ref_hi(ext_t)

    # Specimen + method
    spec_req = ext_t.get("specimen_requirements", {})
    lbspec_raw = spec_req.get("specimen_type", "")
    lbspec = "SERUM" if ("PLACEHOLDER" in lbspec_raw or not lbspec_raw) else lbspec_raw

    assay = ext_t.get("assay") or {}
    lbmethod = assay.get("method") or ""
    lbnam = assay.get("manufacturer") or ""
    lbloinc = assay.get("loinc_code") or ""

    # Analytical performance limits (for censoring fallback)
    perf = _get_analytical_perf(ext_t)

    # Build a lookup from results by idvarval
    results_by_idvar: dict[int, dict] = {}
    for r in results:
        vid = r.get("idvarval")
        if vid is not None:
            results_by_idvar[int(vid)] = r

    lb_rows: list[dict] = []
    is_first_visit = True  # only the first chrono visit gets baseline Y

    for lbseq, m in enumerate(_sorted_measurements(rbco), start=1):
        idvarval = int(m.get("idvarval", lbseq))
        result = results_by_idvar.get(idvarval, {})
        censor_state = m.get("censor_state", "")

        # Determine LBORRES / LBSTRESC / LBSTRESN
        lborres = result.get("lborres", "")
        lbstresc = result.get("lbstresc", lborres)
        lbstressn = result.get("lbstressn")

        # If no result supplied, reconstruct from censor_state
        if not lborres and censor_state in _CENSOR_BOUND:
            op, limit = _CENSOR_BOUND[censor_state]
            if perf[limit] is None:
                raise ValueError(
                    f"measurement idvarval={idvarval}: censor_state "
                    f"{censor_state!r} has no result value and the tBCO "
                    f"analytical_performance {limit.upper()} is null; supply "
                    f"the result or the limit"
                )
            lborres = f"{op}{perf[limit]}"
            lbstresc = lborres
            lbstressn = None

        # LBNRIND
        lbnrind = _compute_nrind(lbstressn, ref_hi)

        # Baseline flag — SDTMIG allows only "Y" or null
        visit = m.get("visit", "")
        lblfl = "Y" if is_first_visit else ""
        is_first_visit = False

        row = {
            "STUDYID": studyid,
            "DOMAIN": "LB",
            "USUBJID": usubjid,
            "LBSEQ": lbseq,
            "LBGRPID": grpid,
            "LBREFID": m.get("specimen_id", ""),
            "LBTESTCD": lbtestcd,
            "LBTEST": lbtest,
            "LBCAT": lbcat,
            "LBORRES": lborres,
            "LBORRESU": lborresu,
            "LBSTRESC": lbstresc,
            "LBSTRESN": lbstressn if lbstressn is not None else "",
            "LBSTRESU": lbstresu,
            "LBSTNRHI": ref_hi if ref_hi else "",
            "LBNRIND": lbnrind,
            "LBSPEC": lbspec,
            "LBMETHOD": lbmethod,
            "LBNAM": lbnam,
            "LBLOINC": lbloinc,
            "VISIT": visit,
            "LBBLFL": lblfl,
            "LBDTC": m.get("collection_dtc", ""),
        }
        lb_rows.append(row)

    return lb_rows


# ---------------------------------------------------------------------------
# SUPPLB dataset builder
# ---------------------------------------------------------------------------

def build_supplb(
    tbco: dict,
    rbco: dict,
    lb_rows: list[dict],
    studyid: str,
    usubjid: str,
) -> list[dict]:
    """Build SUPPLB rows.

    Assay-level qualifiers (ASSAYNAM, ASSAYPLT, LBLOD, LBLLOQ, LBULOQ, RBCOID)
    — keyed on LBGRPID.  Per-result qualifier (CENSOR) — keyed on LBSEQ, taken
    from the built *lb_rows* so IDVARVAL always equals the emitted LBSEQ.
    """
    ext_t = tbco.get("extension_domain", [{}])[0].get("assay_protocol_extension", {})
    grpid = _lb_grpid(tbco)
    info = _get_assay_info(ext_t)
    aname = info["name"]
    aplat = info["platform"]
    perf = _get_analytical_perf(ext_t)

    rbco_object_id = rbco.get("object_id", "")

    rows: list[dict] = []
    supplb_base = {
        "STUDYID": studyid,
        "RDOMAIN": "LB",
        "USUBJID": usubjid,
    }

    def add_row(qnam: str, qlabel: str, qval: str, idvar: str, idvarval: str | int,
                qorig: str = "Assigned", qeval: str = "VENDOR") -> None:
        rows.append({
            **supplb_base,
            "IDVAR": idvar,
            "IDVARVAL": idvarval,
            "QNAM": qnam,
            "QLABEL": qlabel,
            "QVAL": qval,
            "QORIG": qorig,
            "QEVAL": qeval,
        })

    # --- Assay-level (keyed on LBGRPID) — one block per subject ---

    # ASSAYNAM — try multiple sources
    assay_name = ""
    if aname and "PLACEHOLDER" not in aname and aname != "None":
        assay_name = aname
    else:
        # Fall back to spec_id for a readable name
        spec_id = ext_t.get("spec_id", "")
        if spec_id and "PLACEHOLDER" not in spec_id:
            parts = spec_id.split("_")
            if len(parts) > 1:
                for p in parts:
                    if p != "TNNI3" and len(p) > 2:
                        assay_name = p.capitalize() if p.isupper() else p
            if not assay_name:
                assay_name = spec_id
    if assay_name:
        add_row("ASSAYNAM", "Assay Name", assay_name, "LBGRPID", grpid, qeval="VENDOR")

    # ASSAYPLT
    if aplat and "PLACEHOLDER" not in aplat and aplat != "None":
        add_row("ASSAYPLT", "Assay Platform", aplat, "LBGRPID", grpid, qeval="VENDOR")

    # LBLOD
    if perf["lod"] is not None:
        add_row("LBLOD", "Limit of Detection", str(perf["lod"]), "LBGRPID", grpid, qeval="VENDOR")

    # LBLLOQ
    if perf["lloq"] is not None:
        add_row("LBLLOQ", "Lower Limit of Quantitation", str(perf["lloq"]), "LBGRPID", grpid, qeval="VENDOR")

    # LBULOQ
    if perf["uloq"] is not None:
        add_row("LBULOQ", "Upper Limit of Quantitation", str(perf["uloq"]), "LBGRPID", grpid, qeval="VENDOR")

    # RBCOID — always emit (even with PLACEHOLDER, it's the link to the run)
    add_row("RBCOID", "Run BCO Identifier", rbco_object_id or "UNKNOWN",
            "LBGRPID", grpid, qorig="Assigned", qeval="SPONSOR")

    # --- Per-result (keyed on LBSEQ) — CENSOR state ---
    measurements = _sorted_measurements(rbco)
    if len(measurements) != len(lb_rows):
        raise ValueError(
            f"build_supplb: {len(lb_rows)} LB rows but {len(measurements)} "
            f"rBCO measurements; LB rows must be built from the same rBCO"
        )
    for lb_row, m in zip(lb_rows, measurements):
        censor = m.get("censor_state", "")
        if censor:
            add_row("CENSOR", "Censoring State", censor,
                    "LBSEQ", lb_row["LBSEQ"], qorig="Derived", qeval="SPONSOR")

    return rows


# ---------------------------------------------------------------------------
# BM dataset builder
# ---------------------------------------------------------------------------

def _extract_bmkb_entity(bmkb: dict) -> dict[str, str]:
    """Extract entity id, type, and CV term from a BMKB submission record.

    Submission schema (bmkb-model.md v2): ``biomarker_component[]`` carries five
    fields — ``component_index``, ``entity_index``, ``assessed_biomarker_entity_id``,
    ``assessed_entity_type``, ``biomarker``. The entity *name* is not part of the
    record; resolve it from the accession when a name is required (BM.BMENTNM).
    """
    flat = bmkb.get("biomarker_component", [])
    if not flat:
        return {"id": "", "type": "", "cv": ""}

    fc = flat[0]
    return {
        "id": fc.get("assessed_biomarker_entity_id", ""),
        "type": fc.get("assessed_entity_type", ""),
        "cv": fc.get("biomarker", ""),
    }


def _extract_condition(bmkb: dict) -> dict[str, str]:
    """Extract condition from BMKB."""
    cond = bmkb.get("condition") or {}
    return {"name": cond.get("name", ""), "id": cond.get("id", "")}


# ---------------------------------------------------------------------------
# Entity-name resolution
# ---------------------------------------------------------------------------

_ENTITY_NAMES_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "assets", "entity_names.json"
)
_ENTITY_NAMES_CACHE: Optional[dict] = None


def _load_entity_names() -> dict:
    """Accession -> entity name, from assets/entity_names.json (resolution cache).

    Annotation keys (``//_note``) are stripped on load, via the same helper the
    BCO finalizer uses, so the file can keep its in-line guidance for whoever
    maintains it.

    A missing file is not an error, since the cache is optional. A file that
    exists but will not parse is, because the empty result would otherwise
    surface later as a confusing "BM.BMENTNM is empty".
    """
    global _ENTITY_NAMES_CACHE
    if _ENTITY_NAMES_CACHE is None:
        try:
            with open(_ENTITY_NAMES_PATH) as f:
                _ENTITY_NAMES_CACHE = strip_comments(json.load(f))
        except FileNotFoundError:
            _ENTITY_NAMES_CACHE = {}
        except ValueError as e:
            raise ValueError(f"{_ENTITY_NAMES_PATH} is not valid JSON: {e}") from e
    return _ENTITY_NAMES_CACHE


def _resolve_entity_name(entity_id: str) -> str:
    """Resolve an entity name from its accession.

    The BMKB submission record carries the accession, not the name, so the name
    is resolved from the accession (UniProt / CO / GlyTouCan per bmkb-model.md
    §7).
    """
    if not entity_id:
        return ""
    return _load_entity_names().get(entity_id, "")


def build_bm(
    tbco: dict,
    bmkb: dict,
    studyid: str,
    grpid: str,
    evidence: Optional[list] = None,
) -> list[dict]:
    """Build the BM (biomarker context) dataset.

    One row per biomarker claim.  Merges BMKB knowledge + tBCO assay info.

    *evidence* — biomarker evidence ids (e.g. ``["PMID:19710485"]``). The BMKB
    submission record carries no evidence, so it comes from the study documents
    (context-of-use / protocol citations) and is passed in here.
    """
    ext_t = tbco.get("extension_domain", [{}])[0].get("assay_protocol_extension", {})
    info = _get_assay_info(ext_t)
    spec_req = ext_t.get("specimen_requirements", {})
    irules = ext_t.get("interpretation_rules", [])

    tbco_object_id = tbco.get("object_id", "")

    # Entity info from BMKB — the name is resolved from the accession.
    entity = _extract_bmkb_entity(bmkb)
    entity["name"] = _resolve_entity_name(entity["id"])
    cond = _extract_condition(bmkb)

    # Evidence: the BMKB submission record carries none, so it comes from the
    # study documents (passed in); the tBCO is the secondary source.
    ev_ids = list(evidence) if evidence else []
    if not ev_ids:
        ev_ids = ext_t.get("biomarker_evidence", []) or []
    evidence_str = ", ".join(ev_ids) if ev_ids else ""

    # BEST role
    role = ""
    broles = bmkb.get("best_biomarker_role", [])
    if broles:
        role = broles[0].get("role", "").upper()

    # Specimen type
    lbspec_raw = spec_req.get("specimen_type", "")
    bmspec = "SERUM" if ("PLACEHOLDER" in lbspec_raw or not lbspec_raw) else lbspec_raw

    # Interpretation rule
    rule_text = ""
    if irules:
        rule_text = irules[0].get("expression", "")

    # Assay name for BMASSAY
    assay_name = info["name"]
    if not assay_name or "PLACEHOLDER" in assay_name or assay_name == "None":
        assay_name = grpid  # fall back to group ID

    row = {
        "STUDYID": studyid,
        "DOMAIN": "BM",
        "BMID": "BM-001",
        "BMVER": "1.0",
        "BMENTNM": entity["name"],
        "BMENTID": entity["id"],
        "BMENTTP": entity["type"],
        "BMCVTERM": entity["cv"],
        "BMROLE": role,
        "BMCOND": cond["name"],
        "BMCONDID": cond["id"],
        "BMASSAY": assay_name,
        "BMNAM": (ext_t.get("assay") or {}).get("manufacturer") or "",
        "BMPLAT": info["platform"],
        "BMMETHOD": (ext_t.get("assay") or {}).get("method") or "",
        "BMSPEC": bmspec,
        "BMSRCDOM": "LB",
        "BMSRCVAR": "LBTESTCD",
        "BMSRCVAL": _lbtestcd_from_tbco(tbco),
        "BMSRCVR2": "ASSAYNAM",
        "BMSRCVL2": assay_name,
        "BMBCOID": tbco_object_id,
        "BMRULE": rule_text,
        "BMEVID": evidence_str,
        "BMASSRT": "Sponsor Biomarker Review Board",
        "BMASSDTC": (bmkb.get("provenance") or {}).get("date", ""),
    }
    return [row]


# ---------------------------------------------------------------------------
# DM dataset builder
# ---------------------------------------------------------------------------

def build_dm(
    studyid: str,
    dm_rows: list[dict],
) -> list[dict]:
    """Build DM rows from supplied demographics data."""
    result = []
    for d in dm_rows:
        result.append({
            "STUDYID": studyid,
            "DOMAIN": "DM",
            "USUBJID": d.get("usubjid", ""),
            "SUBJID": d.get("subjid", ""),
            "SITEID": d.get("siteid", ""),
            "AGE": d.get("age", ""),
            "AGEU": d.get("ageu", ""),
            "SEX": d.get("sex", ""),
            "COUNTRY": d.get("country", ""),
            "RFSTDTC": d.get("rfstdtc", ""),
        })
    return result


# ---------------------------------------------------------------------------
# TSV writer
# ---------------------------------------------------------------------------

def write_tsv(rows: list[dict], path: str) -> None:
    """Write a list of dicts as a tab-separated file."""
    if not rows:
        # Write header only, empty dataset
        with open(path, "w", newline="") as f:
            f.write("")
        return

    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t",
                                quoting=csv.QUOTE_NONNUMERIC)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    print(f"[DONE] wrote {path} ({len(rows)} rows)")


# ---------------------------------------------------------------------------
# Main conversion
# ---------------------------------------------------------------------------

def convert_record_set_to_sdtm(
    tbco_path: str,
    rbco_path: str,
    bmkb_path: str,
    results_path: str,
    dm_path: Optional[str],
    output_dir: str,
    evidence: Optional[list] = None,
) -> int:
    """Run the full conversion, return exit code."""
    os.makedirs(output_dir, exist_ok=True)

    tbco = _load_json(tbco_path)
    rbco = _load_json(rbco_path)
    bmkb = _load_json(bmkb_path)
    results_data = _load_json(results_path) if results_path else {}
    dm_data = _load_json(dm_path) if dm_path else {}

    results_list = results_data.get("results", [])
    dm_list = dm_data.get("dm", [])

    # Study context from rBCO
    ext_r = rbco.get("extension_domain", [{}])[0].get("assay_run_extension", {})
    studyid = ext_r.get("studyid", "STUDY")
    usubjid = ext_r.get("usubjid", "")

    grpid = _lb_grpid(tbco)

    print(f"[CONVERT] Study: {studyid}, Subject: {usubjid}, Group: {grpid}")

    # --- Build datasets ---
    lb_rows = build_lb(tbco, rbco, results_list, studyid, usubjid)
    supplb_rows = build_supplb(tbco, rbco, lb_rows, studyid, usubjid)
    bm_rows = build_bm(tbco, bmkb, studyid, grpid, evidence=evidence)
    dm_rows = build_dm(studyid, dm_list)

    # --- Write TSVs ---
    write_tsv(lb_rows, os.path.join(output_dir, "LB.tsv"))
    write_tsv(supplb_rows, os.path.join(output_dir, "SUPPLB.tsv"))
    write_tsv(bm_rows, os.path.join(output_dir, "BM.tsv"))
    write_tsv(dm_rows, os.path.join(output_dir, "DM.tsv"))

    return 0


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _self_test() -> None:
    """Build SDTM datasets from the gold Troponin I record set and verify
    structural and content correctness against the xlsx reference (patient 1).
    """
    print("=" * 60)
    print("  record_set_to_sdtm.py — Self-test")
    print("=" * 60)

    tbco_path = os.path.join(_TROPI, "Troponin_I_tBCO.json")
    rbco_path = os.path.join(_TROPI, "Troponin_I_patient1_rBCO.json")
    bmkb_path = os.path.join(_TROPI, "Troponin_I_biomarkerKB.json")

    tbco = _load_json(tbco_path)
    rbco = _load_json(rbco_path)
    bmkb = _load_json(bmkb_path)

    # Results table — from the xlsx LB sheet (patient 1)
    results_list = [
        {"idvarval": 1, "lborres": "0.021", "lbstresc": "0.021", "lbstressn": 0.021},
        {"idvarval": 2, "lborres": "0.058", "lbstresc": "0.058", "lbstressn": 0.058},
        {"idvarval": 3, "lborres": "0.094", "lbstresc": "0.094", "lbstressn": 0.094},
    ]

    # Demographics — from the xlsx DM sheet (patient 1)
    dm_list = [
        {"usubjid": "BM-2026-01-001", "subjid": "001", "siteid": "01",
         "age": 67, "ageu": "YEARS", "sex": "M", "country": "DEU",
         "rfstdtc": "2026-03-15"},
    ]

    ext_r = rbco.get("extension_domain", [{}])[0].get("assay_run_extension", {})
    studyid = ext_r.get("studyid", "BM-2026-01")
    usubjid = ext_r.get("usubjid", "BM-2026-01-001")
    grpid = _lb_grpid(tbco)

    print(f"\n  Files: gold (group={grpid}), Subject: {usubjid}")

    # --- Build ---
    # Evidence lives in the study documents, not the BMKB record.
    evidence = ["PMID:19710485"]
    lb_rows = build_lb(tbco, rbco, results_list, studyid, usubjid)
    supplb_rows = build_supplb(tbco, rbco, lb_rows, studyid, usubjid)
    bm_rows = build_bm(tbco, bmkb, studyid, grpid, evidence=evidence)
    dm_rows = build_dm(studyid, dm_list)

    # --- Verify ---
    errors: list[dict] = []

    def err(msg: str) -> None:
        errors.append({"msg": msg})

    # === LB ===
    if len(lb_rows) != 3:
        err(f"LB row count: got {len(lb_rows)}, expected 3")
    else:
        expected_lb = [
            {"seq": 1, "orres": "0.021", "stresn": "0.021",
             "nrind": "NORMAL", "blfl": "Y",
             "visit": "ADMISSION", "dtc": "2026-03-15T08:10"},
            {"seq": 2, "orres": "0.058", "stresn": "0.058",
             "nrind": "HIGH", "blfl": "",
             "visit": "3 HOURS", "dtc": "2026-03-15T11:10"},
            {"seq": 3, "orres": "0.094", "stresn": "0.094",
             "nrind": "HIGH", "blfl": "",
             "visit": "6 HOURS", "dtc": "2026-03-15T14:10"},
        ]

        # Map check keys → SDTM column names
        COL_MAP = {
            "seq": "LBSEQ", "testcd": "LBTESTCD", "orres": "LBORRES",
            "stresn": "LBSTRESN", "nrind": "LBNRIND", "blfl": "LBBLFL",
            "visit": "VISIT", "dtc": "LBDTC",
        }

        for i, exp in enumerate(expected_lb):
            row = lb_rows[i]
            for k, v in exp.items():
                col = COL_MAP.get(k, k)
                got = row.get(col, "")
                if str(got) != str(v):
                    err(f"LB[{i}].{col}: got '{got}', expected '{v}'")

        # Group ID comes from tBCO assay.assay_name (gold xlsx: TNIULTRA)
        for i in range(3):
            if lb_rows[i]["LBGRPID"] != "TNIULTRA":
                err(f"LB[{i}].LBGRPID: got '{lb_rows[i]['LBGRPID']}', expected 'TNIULTRA'")

        # Check common assay-level fields (row 0 is representative)
        r0 = lb_rows[0]
        common_checks = [
            ("LBTESTCD", "TNNI3"),
            ("LBORRESU", "ng/mL"),
            ("LBSTRESU", "ng/mL"),
            ("LBSPEC", "SERUM"),
            ("LBMETHOD", "IMMUNOASSAY"),
            ("LBCAT", "CHEMISTRY"),
        ]
        # Verify they are present and non-empty; exact value for units/spec
        for col_name, expected in common_checks:
            got = r0.get(col_name, "")
            if not got:
                err(f"LB[0].{col_name} is empty")
            elif expected and str(got) != str(expected):
                err(f"LB[0].{col_name}: got '{got}', expected '{expected}'")

    # === SUPPLB ===
    # 6 assay-level (ASSAYNAM, ASSAYPLT, LBLOD, LBLLOQ, LBULOQ, RBCOID)
    # + 3 CENSOR = 9 rows
    expected_supplb_count = 9
    if len(supplb_rows) != expected_supplb_count:
        err(f"SUPPLB row count: got {len(supplb_rows)}, expected {expected_supplb_count}")
    else:
        qnams = [r["QNAM"] for r in supplb_rows]
        expected_qnams = ["ASSAYNAM", "ASSAYPLT", "LBLOD", "LBLLOQ", "LBULOQ",
                          "RBCOID", "CENSOR", "CENSOR", "CENSOR"]
        for i, eq in enumerate(expected_qnams):
            if i < len(qnams) and qnams[i] != eq:
                err(f"SUPPLB[{i}].QNAM: got {qnams[i]}, expected {eq}")
                break

        # CENSOR values, and IDVARVAL must point at the emitted LBSEQ
        censor_rows = [r for r in supplb_rows if r["QNAM"] == "CENSOR"]
        expected_censors = ["detected_below_lloq", "quantifiable", "quantifiable"]
        for i, (cr, ec) in enumerate(zip(censor_rows, expected_censors)):
            if cr["QVAL"] != ec:
                err(f"CENSOR[{i}].QVAL: got {cr['QVAL']}, expected {ec}")
        lbseqs = [r["LBSEQ"] for r in lb_rows]
        idvarvals = [r["IDVARVAL"] for r in censor_rows]
        if idvarvals != lbseqs:
            err(f"CENSOR IDVARVAL {idvarvals} != LBSEQ {lbseqs}")

        # Assay-level QVAL content
        for r in supplb_rows:
            if r["IDVAR"] == "LBGRPID" and r["IDVARVAL"] != "TNIULTRA":
                err(f"{r['QNAM']}.IDVARVAL: got {r['IDVARVAL']}, expected TNIULTRA")
            if r["QNAM"] == "ASSAYNAM" and r["QVAL"] != "TnI-Ultra":
                err(f"ASSAYNAM.QVAL: got {r['QVAL']}, expected TnI-Ultra")
            elif r["QNAM"] == "ASSAYPLT" and r["QVAL"] != "ADVIA Centaur XP":
                err(f"ASSAYPLT.QVAL: got {r['QVAL']}, expected ADVIA Centaur XP")
            elif r["QNAM"] == "LBLOD" and r["QVAL"] != "0.006":
                err(f"LBLOD.QVAL: got {r['QVAL']}, expected 0.006")
            elif r["QNAM"] == "LBLLOQ" and r["QVAL"] != "0.03":
                err(f"LBLLOQ.QVAL: got {r['QVAL']}, expected 0.03")
            elif r["QNAM"] == "LBULOQ" and r["QVAL"] != "50":
                err(f"LBULOQ.QVAL: got {r['QVAL']}, expected 50")

    # === BM ===
    if len(bm_rows) != 1:
        err(f"BM row count: got {len(bm_rows)}, expected 1")
    else:
        bm = bm_rows[0]
        if not bm.get("BMENTNM", ""):
            err("BM.BMENTNM is empty")
        if not bm.get("BMENTID", ""):
            err("BM.BMENTID is empty")
        if bm.get("BMASSAY") != "TnI-Ultra":
            err(f"BM.BMASSAY: got {bm.get('BMASSAY')}, expected TnI-Ultra")
        if bm.get("BMSRCVL2") != "TnI-Ultra":
            err(f"BM.BMSRCVL2: got {bm.get('BMSRCVL2')}, expected TnI-Ultra")
        if bm.get("BMSRCDOM") != "LB":
            err(f"BM.BMSRCDOM: got {bm.get('BMSRCDOM')}, expected LB")
        if bm.get("BMSRCVAR") != "LBTESTCD":
            err(f"BM.BMSRCVAR: got {bm.get('BMSRCVAR')}, expected LBTESTCD")
        if not bm.get("BMEVID", ""):
            err("BM.BMEVID is empty (expected at least one PMID)")

    # === DM ===
    if len(dm_rows) != 1:
        err(f"DM row count: got {len(dm_rows)}, expected 1")
    else:
        dm = dm_rows[0]
        if dm.get("USUBJID") != "BM-2026-01-001":
            err(f"DM.USUBJID: got {dm.get('USUBJID')}")
        if dm.get("AGE") != 67:
            err(f"DM.AGE: got {dm.get('AGE')}, expected 67")
        if dm.get("AGEU") != "YEARS":
            err(f"DM.AGEU: got {dm.get('AGEU')}, expected YEARS")
        if dm.get("SEX") != "M":
            err(f"DM.SEX: got {dm.get('SEX')}, expected M")

    # --- Summary ---
    output_dir = os.path.join(_HERE, "..", "fixtures", "troponin_I", "_output", "sdtm_self_test")
    os.makedirs(output_dir, exist_ok=True)
    write_tsv(lb_rows, os.path.join(output_dir, "LB.tsv"))
    write_tsv(supplb_rows, os.path.join(output_dir, "SUPPLB.tsv"))
    write_tsv(bm_rows, os.path.join(output_dir, "BM.tsv"))
    write_tsv(dm_rows, os.path.join(output_dir, "DM.tsv"))

    if errors:
        print("\n[SELF-TEST] FAILED:")
        for e in errors:
            print(f"  ✗ {e}")
        sys.exit(1)

    print("\n[SELF-TEST] PASSED — all 4 SDTM datasets verified against Troponin I gold")
    print(f"  LB: {len(lb_rows)} rows, SUPPLB: {len(supplb_rows)} rows, "
          f"BM: {len(bm_rows)} row, DM: {len(dm_rows)} row")
    print(f"  Output: {output_dir}/")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(
        description="Convert a 3-part BCO record set to SDTM tabular datasets."
    )
    parser.add_argument("--tbco", help="tBCO JSON file path")
    parser.add_argument("--rbco", help="rBCO JSON file path")
    parser.add_argument("--bmkb", help="BMKB JSON file path")
    parser.add_argument("--results", help="Results JSON file path")
    parser.add_argument("--dm", help="Demographics JSON file path (optional)")
    parser.add_argument("--output-dir", default="./sdtm",
                        help="Output directory for TSV files")
    parser.add_argument("--evidence", default="",
                        help="Comma-separated biomarker evidence ids, e.g. PMID:19710485 "
                             "(the BMKB record carries no evidence; it comes from the "
                             "study documents)")
    parser.add_argument("--self-test", action="store_true",
                        help="Run built-in self-test and exit")
    args = parser.parse_args()

    if args.self_test:
        _self_test()
        return

    if not args.tbco or not args.rbco or not args.bmkb or not args.results:
        parser.error("--tbco, --rbco, --bmkb, and --results are required (or use --self-test)")

    try:
        code = convert_record_set_to_sdtm(
            args.tbco, args.rbco, args.bmkb,
            args.results, args.dm, args.output_dir,
            evidence=[e.strip() for e in args.evidence.split(",") if e.strip()],
        )
    except ValueError as e:
        print(f"[ERROR] {e}")
        code = 1
    sys.exit(code)


if __name__ == "__main__":
    main()
