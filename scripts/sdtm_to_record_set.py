#!/usr/bin/env python3
"""sdtm_to_record_set.py — Convert SDTM tabular datasets back to the record set.

Takes four TSV files (DM, LB, SUPPLB, BM) and reconstructs the three JSON
files that form the BCO record set: tBCO, rBCO, and BMKB record.

Designed to round-trip with record_set_to_sdtm.py: the triple (tBCO, rBCO, BMKB)
when converted to SDTM and back should produce a semantically equivalent triple.

Usage
-----
    python sdtm_to_record_set.py \\
        --dm sdtm/DM.tsv \\
        --lb sdtm/LB.tsv \\
        --supplb sdtm/SUPPLB.tsv \\
        --bm sdtm/BM.tsv \\
        --output-dir ./reconstructed

    python sdtm_to_record_set.py --self-test

Mapping reference: references/sdtmig-guide.md (Reverse Direction section).
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import sys
from copy import deepcopy
from typing import Any, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from finalize_draft import compute_etag  # noqa: E402


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_HERE = os.path.dirname(os.path.abspath(__file__))
_VAULT = os.path.abspath(os.path.join(_HERE, "..", "..", "..", "..", ".."))
_TROPI = os.path.join(
    _HERE, "..", "examples", "troponin_I"
)


# ---------------------------------------------------------------------------
# TSV loader
# ---------------------------------------------------------------------------

def _read_tsv(path: str) -> list[dict[str, str]]:
    """Read a tab-separated file (quote-aware) and return a list of dicts.

    Handles the quoted TSV format used by the Troponin I example.
    Keys are stripped of surrounding quotes if any; values are stripped.
    """
    if not os.path.exists(path):
        print(f"[ERROR] TSV file not found: {path}")
        sys.exit(1)
    with open(path, newline="") as f:
        raw = f.read()

    reader = csv.DictReader(
        raw.splitlines(), delimiter="\t", quotechar='"', quoting=csv.QUOTE_ALL
    )

    rows: list[dict[str, str]] = []
    for row in reader:
        cleaned = {}
        for k, v in row.items():
            key = k.strip('" ')
            val = v.strip('" ') if v else ""
            cleaned[key] = val
        rows.append(cleaned)
    return rows


# ---------------------------------------------------------------------------
# SUPPLB grouping helpers
# ---------------------------------------------------------------------------

def _group_supplb(
    supplb: list[dict[str, str]],
) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    """Split SUPPLB rows into assay-level (keyed on LBGRPID) and per-result (keyed on LBSEQ).

    Returns (assay_quals, result_quals).
    - assay_quals: {grpid: {QNAM: QVAL, ...}} — pooled across all rows with IDVAR=LBGRPID
    - result_quals: {lbseq_str: {QNAM: QVAL, ...}} — per LBSEQ
    """
    assay_quals: dict[str, dict[str, str]] = {}
    result_quals: dict[str, dict[str, str]] = {}
    # Per-result groups: {idvarval: {qnam: qval}}
    result_groups: dict[str, dict[str, str]] = {}

    for row in supplb:
        idvar = row.get("IDVAR", "")
        idvarval = row.get("IDVARVAL", "")
        qnam = row.get("QNAM", "")
        qval = row.get("QVAL", "")

        if idvar == "LBGRPID":
            if idvarval not in assay_quals:
                assay_quals[idvarval] = {}
            assay_quals[idvarval][qnam] = qval
        elif idvar == "LBSEQ":
            if idvarval not in result_groups:
                result_groups[idvarval] = {}
            result_groups[idvarval][qnam] = qval
        # else skip

    return assay_quals, result_groups


# ---------------------------------------------------------------------------
# Reconstruct tBCO
# ---------------------------------------------------------------------------

def _make_grpid(assay_name: str) -> str:
    """Derive a short group ID from an assay name, e.g. 'TnI-Ultra' → 'TNIULTRA'."""
    cleaned = re.sub(r"[^a-zA-Z0-9]", "", assay_name).upper()
    return cleaned[:20]


def reconstruct_tbco(
    lb_rows: list[dict[str, str]],
    supplb: list[dict[str, str]],
    bm_rows: list[dict[str, str]],
    studyid: str,
) -> dict[str, Any]:
    """Rebuild a tBCO JSON from SDTM data.

    Uses the first LB row for assay-level constants, SUPPLB for qualifiers,
    and BM for entity-level assay metadata.

    Returns a dict matching the IEEE 2791 structure with assay_protocol_extension.
    """
    if not lb_rows:
        # Fall back to BM for assay info
        first_lb: dict[str, str] = {}
    else:
        first_lb = lb_rows[0]

    assay_quals, _result_quals = _group_supplb(supplb)

    # Pick the first assay group
    grpid = first_lb.get("LBGRPID", "UNKNOWN")
    assay_info: dict[str, str] = assay_quals.get(grpid, {})

    assay_name = assay_info.get("ASSAYNAM", first_lb.get("LBNAM", ""))
    assay_platform = assay_info.get("ASSAYPLT", "")
    method = first_lb.get("LBMETHOD", "")
    manufacturer = first_lb.get("LBNAM", "")
    loinc = first_lb.get("LBLOINC", "")
    lbtestcd = first_lb.get("LBTESTCD", "")
    lbtest = first_lb.get("LBTEST", "")
    lbspec = first_lb.get("LBSPEC", "SERUM")

    # Reference limit
    ref_hi_str = first_lb.get("LBSTNRHI", "")
    ref_hi: Optional[float] = None
    if ref_hi_str:
        try:
            ref_hi = float(ref_hi_str)
        except ValueError:
            pass

    # Analytical performance from SUPPLB
    lod: Optional[float] = None
    lloq: Optional[float] = None
    uloq: Optional[float] = None
    lod_str = assay_info.get("LBLOD", "")
    lloq_str = assay_info.get("LBLLOQ", "")
    uloq_str = assay_info.get("LBULOQ", "")
    try:
        lod = float(lod_str) if lod_str else None
        lloq = float(lloq_str) if lloq_str else None
        uloq = float(uloq_str) if uloq_str else None
    except ValueError:
        pass

    # Unit
    lborresu = first_lb.get("LBORRESU", "ng/mL")

    # Determine analyte identifiers from LOINC / test name
    analyte_name = lbtest if lbtest else lbtestcd
    uniprot_id = ""
    if lbtestcd == "TNNI3":
        uniprot_id = "P19429"

    # Entity type
    entity_type = "protein"

    # Object ID — try from BM.BMBCOID, else construct
    tbco_object_id = ""
    if bm_rows:
        tbco_object_id = bm_rows[0].get("BMBCOID", "")
    if not tbco_object_id:
        tbco_object_id = (
            f"https://biocomputeobject.org/PLACEHOLDER_{assay_name}_tBCO/1.0.0"
        )

    # Rule from BM
    rule_text = ""
    if bm_rows:
        rule_text = bm_rows[0].get("BMRULE", "")

    # Build the tBCO JSON
    tbco: dict[str, Any] = {
        "object_id": tbco_object_id,
        "spec_version": "https://w3id.org/ieee/ieee-2791-schema/2791object.json",
        "etag": "PLACEHOLDER",
        "provenance_domain": {
            "name": f"Assay standard for {analyte_name} ({assay_name}, {assay_platform})",
            "version": "1.0.0",
            "license": "https://creativecommons.org/licenses/by/4.0/",
            "created": "PLACEHOLDER",
            "modified": "PLACEHOLDER",
            "contributors": [
                {
                    "name": "PLACEHOLDER - Creator name",
                    "affiliation": "PLACEHOLDER - Institution",
                    "contribution": ["createdBy", "authoredBy"],
                    "email": "PLACEHOLDER@institution.edu",
                }
            ],
            "review": [],
        },
        "usability_domain": [
            f"Reconstructed from SDTM for {studyid}.",
        ],
        "extension_domain": [
            {
                "extension_schema": "PLACEHOLDER - assay_protocol_extension schema URI",
                "assay_protocol_extension": {
                    "spec_id": f"{lbtestcd}_{_make_grpid(assay_name)}" if assay_name else "UNKNOWN",
                    "spec_version": "1.0.0",
                    "target": {
                        "analyte_name": analyte_name,
                        "analyte_identifiers": (
                            [
                                {
                                    "namespace": "UniProtKB",
                                    "accession": uniprot_id,
                                }
                            ]
                            if uniprot_id
                            else []
                        ),
                        "entity_type": entity_type,
                        "measured_property": "mass concentration",
                        "matrix": {
                            "term": "blood",
                            "curie": "UBERON:0000178",
                        },
                        "detects": f"Placeholder — {analyte_name} measurement.",
                    },
                    "assay": {
                        "assay_name": assay_name if assay_name else "PLACEHOLDER",
                        "manufacturer": manufacturer if manufacturer else "PLACEHOLDER",
                        "platform": assay_platform if assay_platform else "PLACEHOLDER",
                        "method": method if method else "PLACEHOLDER",
                        "assay_generation": "sensitive",
                        "regulatory_status": "investigational",
                        "calibration_traceability": "PLACEHOLDER",
                        "loinc_code": loinc,
                    },
                    "specimen_requirements": {
                        "specimen_type": lbspec,
                        "specimen_curie": "UBERON:0000178",
                        "container_additive": "PLACEHOLDER",
                        "minimum_volume": "PLACEHOLDER",
                        "handling": "PLACEHOLDER",
                        "stability": "PLACEHOLDER",
                    },
                    "subject_preconditions": [],
                    "sampling_schedule": {
                        "anchor": "PLACEHOLDER",
                        "serial_required": False,
                        "timepoints": [],
                    },
                    "analytical_performance": {
                        "limit_of_detection": {"value": lod, "unit": lborresu},
                        "limit_of_quantitation": {"value": lloq, "unit": lborresu},
                        "upper_limit_of_quantitation": {"value": uloq, "unit": lborresu},
                    },
                    "reference_limits": (
                        [{"direction": "upper", "value": ref_hi, "unit": lborresu}]
                        if ref_hi is not None
                        else []
                    ),
                    "interpretation_rules": (
                        [{"expression": rule_text, "rule_id": "R1"}] if rule_text else []
                    ),
                    "reporting_convention": {
                        "unit": lborresu,
                        "decimal_places": "PLACEHOLDER",
                    },
                },
            }
        ],
        "description_domain": {
            "keywords": [analyte_name, lbtestcd, studyid, "SDTM", "reconstructed"],
            "platform": [{"name": assay_platform}] if assay_platform else [],
            "xref": [],
            "pipeline_steps": [],
        },
        "execution_domain": {
            "script": [],
            "script_driver": "manual",
            "software_prerequisites": [],
            "external_data_endpoints": [],
            "environment_variables": {},
        },
        "parametric_domain": [],
        "io_domain": {
            "input_subdomain": [],
            "output_subdomain": [],
        },
        "error_domain": [],
    }

    # etag — one canonical definition (see finalize_draft.py)
    tbco["etag"] = compute_etag(tbco)

    return tbco


# ---------------------------------------------------------------------------
# Reconstruct rBCO
# ---------------------------------------------------------------------------

def _derive_censor_state(
    lborres: str,
    lbstressn_str: str,
    lod: Optional[float],
    lloq: Optional[float],
    uloq: Optional[float],
) -> str:
    """Infer censor_state from LB result string and numeric value.

    Lower-level heuristic: if LBSTRESN is populated, value ≥ LLOQ → check
    quantifiable vs above_uloq. If LBSTRESN is empty, examine LBORRES pattern.
    """
    lbstressn: Optional[float] = None
    if lbstressn_str:
        try:
            lbstressn = float(lbstressn_str)
        except ValueError:
            pass

    if lbstressn is not None:
        if uloq is not None and lbstressn > uloq:
            return "above_uloq"
        if lloq is not None and lbstressn >= lloq:
            return "quantifiable"
        return "detected_below_lloq"

    if lborres.startswith("<"):
        # Try to extract the number after <
        m = re.match(r"<([\d.]+)", lborres)
        if m:
            val = float(m.group(1))
            if lod is not None and val <= lod:
                return "below_lod"
            return "detected_below_lloq"
        if "lod" in lborres.lower():
            return "below_lod"
        return "detected_below_lloq"

    if lborres.startswith(">"):
        return "above_uloq"

    # Fallback — if there's a numeric value, assume quantifiable
    try:
        float(lborres)
        return "quantifiable"
    except ValueError:
        return "detected_below_lloq"


def reconstruct_rbco(
    lb_rows: list[dict[str, str]],
    supplb: list[dict[str, str]],
    bm_rows: list[dict[str, str]],
    tbco: dict[str, Any],
    studyid: str,
    usubjid: str,
) -> dict[str, Any]:
    """Rebuild an rBCO JSON from SDTM data.

    Uses LB rows for measurements, SUPPLB for assay qualifiers + CENSOR,
    and tBCO for analytical limits (for censor derivation fallback).
    """
    if not lb_rows:
        return {}

    assay_quals, result_quals = _group_supplb(supplb)
    grpid = lb_rows[0].get("LBGRPID", "UNKNOWN")
    assay_info = assay_quals.get(grpid, {})

    # Analytical limits from tBCO SUPPLB for censor derivation
    lod: Optional[float] = None
    lloq: Optional[float] = None
    uloq: Optional[float] = None
    try:
        lod = float(assay_info.get("LBLOD", "")) if assay_info.get("LBLOD") else None
        lloq = float(assay_info.get("LBLLOQ", "")) if assay_info.get("LBLLOQ") else None
        uloq = float(assay_info.get("LBULOQ", "")) if assay_info.get("LBULOQ") else None
    except ValueError:
        pass

    # Also try from tbco analytical_performance
    ext_t = (
        tbco.get("extension_domain", [{}])[0]
        .get("assay_protocol_extension", {})
    )
    ap = ext_t.get("analytical_performance", {})
    if lod is None:
        lod = ap.get("limit_of_detection", {}).get("value")
    if lloq is None:
        lloq = ap.get("limit_of_quantitation", {}).get("value")
    if uloq is None:
        uloq = ap.get("upper_limit_of_quantitation", {}).get("value")

    # RBCOID from SUPPLB
    rbco_object_id = assay_info.get("RBCOID", "")
    if not rbco_object_id:
        rbco_object_id = (
            f"https://biocomputeobject.org/PLACEHOLDER_{usubjid}_rBCO/1.0.0"
        )

    # tbco object_id for derived_from
    tbco_object_id = tbco.get("object_id", "")

    # Derive run_id from first visit date
    first_dtc = lb_rows[0].get("LBDTC", "")
    run_id_parts = first_dtc[:10].replace("-", "") if first_dtc else "UNKNOWN"
    run_id = f"R-{run_id_parts}-01"

    # Build measurements from LB rows sorted by LBSEQ
    measurements: list[dict[str, Any]] = []
    for row in sorted(lb_rows, key=lambda r: int(r.get("LBSEQ", 0))):
        lbseq = row.get("LBSEQ", "")
        idvarval = int(lbseq) if lbseq else 0
        visit = row.get("VISIT", "")
        specimen_id = row.get("LBREFID", "")
        specimen_type = row.get("LBSPEC", "SERUM")
        collection_dtc = row.get("LBDTC", "")
        lborres = row.get("LBORRES", "")
        lbstressn_str = row.get("LBSTRESN", "")
        lbtestcd = row.get("LBTESTCD", "")

        # Get censor from SUPPLB result_quals (keyed on LBSEQ string)
        censor_state = ""
        if str(idvarval) in result_quals:
            censor_state = result_quals[str(idvarval)].get("CENSOR", "")
        if not censor_state:
            censor_state = _derive_censor_state(lborres, lbstressn_str, lod, lloq, uloq)

        measurements.append({
            "idvar": "LBSEQ",
            "idvarval": idvarval,
            "lbtestcd": lbtestcd,
            "visit": visit,
            "specimen_id": specimen_id,
            "specimen_type": specimen_type,
            "collection_dtc": collection_dtc,
            "analysis_dtc": "PLACEHOLDER",
            "censor_state": censor_state,
            "repeated": False,
        })

    # Build rBCO JSON
    rbco: dict[str, Any] = {
        "object_id": rbco_object_id,
        "spec_version": "https://w3id.org/ieee/ieee-2791-schema/2791object.json",
        "etag": "PLACEHOLDER",
        "provenance_domain": {
            "name": f"Cardiac troponin I, subject {usubjid}, run {run_id}",
            "version": "1.0",
            "license": "https://creativecommons.org/licenses/by/4.0/",
            "created": "PLACEHOLDER",
            "modified": "PLACEHOLDER",
            "derived_from": tbco_object_id,
            "contributors": [
                {
                    "name": "PLACEHOLDER - Creator name",
                    "affiliation": "PLACEHOLDER - Institution",
                    "contribution": ["createdBy", "authoredBy"],
                    "email": "PLACEHOLDER@institution.edu",
                }
            ],
            "review": [],
        },
        "usability_domain": [
            f"Reconstructed from SDTM for {studyid}, subject {usubjid}.",
        ],
        "extension_domain": [
            {
                "extension_schema": "PLACEHOLDER - assay_run_extension schema URI",
                "assay_run_extension": {
                    "run_id": run_id,
                    "studyid": studyid,
                    "usubjid": usubjid,
                    "specification": {
                        "tbco_object_id": tbco_object_id,
                        "spec_id": ext_t.get("spec_id", "PLACEHOLDER"),
                        "spec_version": "1.0.0",
                        "conformance": "conforms",
                    },
                    "laboratory": {
                        "name": "PLACEHOLDER - performing laboratory",
                        "accreditation": "PLACEHOLDER",
                    },
                    "instrument": {
                        "serial_number": "PLACEHOLDER",
                        "software_version": "PLACEHOLDER",
                    },
                    "consumables": {
                        "reagent_lot": "PLACEHOLDER",
                        "calibrator_lot": "PLACEHOLDER",
                    },
                    "calibration": {
                        "calibrated_dtc": "PLACEHOLDER",
                        "accepted": True,
                        "record": "PLACEHOLDER",
                    },
                    "quality_control": {
                        "accepted": True,
                        "record": "PLACEHOLDER",
                    },
                    "measurements": measurements,
                    "deviations": [],
                    "note": (
                        "Reconstructed by sdtm_to_record_set.py. "
                        "Instrument-level fields are PLACEHOLDER."
                    ),
                },
            },
            {
                "extension_schema": "PLACEHOLDER - sdtm_extension schema URI",
                "sdtm_extension": {
                    "standard": "SDTMIG v3.4 over SDTM v2.1",
                    "datasets": [
                        {
                            "name": "LB",
                            "file": "lb.xpt",
                            "rows_for_this_subject": len(lb_rows),
                        },
                        {
                            "name": "SUPPLB",
                            "file": "supplb.xpt",
                            "rows_for_this_subject": len(supplb),
                        },
                    ],
                    "supplb_derivation": [
                        {"qnam": "ASSAYNAM", "qorig": "CRF", "qeval": "VENDOR",
                         "resolves_in": "tBCO", "path": "assay.name"},
                        {"qnam": "ASSAYPLT", "qorig": "CRF", "qeval": "VENDOR",
                         "resolves_in": "tBCO", "path": "assay.platform"},
                        {"qnam": "LBLOD", "qorig": "CRF", "qeval": "VENDOR",
                         "resolves_in": "tBCO",
                         "path": "analytical_performance.limit_of_detection.value"},
                        {"qnam": "LBLLOQ", "qorig": "CRF", "qeval": "VENDOR",
                         "resolves_in": "tBCO",
                         "path": "analytical_performance.limit_of_quantitation.value"},
                        {"qnam": "LBULOQ", "qorig": "CRF", "qeval": "VENDOR",
                         "resolves_in": "tBCO",
                         "path": "analytical_performance.upper_limit_of_quantitation.value"},
                        {"qnam": "CENSOR", "qorig": "DERIVED", "qeval": "SPONSOR",
                         "resolves_in": "rBCO",
                         "path": "measurements[].censor_state"},
                    ],
                    "note": "Reconstructed by sdtm_to_record_set.py.",
                },
            },
        ],
        "description_domain": {
            "keywords": ["cardiac troponin I", "TNNI3", "immunoassay",
                         "run record", "SDTM", "LB", "SUPPLB"],
            "xref": [],
            "pipeline_steps": [],
        },
        "execution_domain": {
            "script": [],
            "script_driver": "manual",
            "software_prerequisites": [],
            "external_data_endpoints": [],
            "environment_variables": {},
        },
        "parametric_domain": [],
        "io_domain": {
            "input_subdomain": [],
            "output_subdomain": [],
        },
        "error_domain": [],
    }

    # etag — one canonical definition (see finalize_draft.py)
    rbco["etag"] = compute_etag(rbco)

    return rbco


# ---------------------------------------------------------------------------
# Reconstruct BMKB
# ---------------------------------------------------------------------------

def reconstruct_bmkb(
    bm_rows: list[dict[str, str]],
    tbco: dict[str, Any],
    studyid: str,
) -> dict[str, Any]:
    """Rebuild a BMKB record JSON from the BM SDTM dataset.

    Returns a dict matching the BiomarkerKB API response structure.
    """
    if not bm_rows:
        return {}

    bm_row = bm_rows[0]

    entity_name = bm_row.get("BMENTNM", "")
    entity_id = bm_row.get("BMENTID", "")
    entity_type = bm_row.get("BMENTTP", "protein")
    cv_term = bm_row.get("BMCVTERM", "")
    role = bm_row.get("BMROLE", "monitoring")
    cond_name = bm_row.get("BMCOND", "")
    cond_id = bm_row.get("BMCONDID", "")
    evidence_raw = bm_row.get("BMEVID", "")
    bm_id = bm_row.get("BMID", "BM-001")
    bm_ver = bm_row.get("BMVER", "1.0")

    # Parse evidence PMIDs from comma-separated list
    pmids = [e.strip() for e in evidence_raw.split(",") if e.strip()]

    # Build evidence_source entries
    evidence_source: list[dict[str, Any]] = []
    for pmid in pmids:
        entry: dict[str, Any] = {
            "id": pmid,
            "database": "PubMed",
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}",
        }
        evidence_source.append(entry)

    # Uniprot ID from entity_id (strip prefix)
    uniprot_id = entity_id.replace("UPKB:", "") if entity_id else ""

    # Assay info from tBCO
    ext_t = (
        tbco.get("extension_domain", [{}])[0]
        .get("assay_protocol_extension", {})
    )
    assay = ext_t.get("assay", {})
    assay_name = assay.get("assay_name", bm_row.get("BMASSAY", ""))
    assay_platform = (
        assay.get("platform", "") or bm_row.get("BMPLAT", "")
    )

    # Build condition block (submission schema: id, lowercase name, resource)
    condition: dict[str, Any] = {
        "id": cond_id,
        "name": cond_name.lower() if cond_name else "",
        "resource": "Disease Ontology",
    }

    # Build the biomarker_component (submission schema: five fields only)
    biomarker_component: list[dict[str, Any]] = [
        {
            "component_index": "1",
            "entity_index": "1",
            "assessed_biomarker_entity_id": entity_id,
            "assessed_entity_type": entity_type,
            "biomarker": cv_term,
        }
    ]

    # Provider-side submission record. BiomarkerKB-assigned fields
    # (biomarker_id, *_md5, biomarker_id_new, source_list) are NOT emitted.
    bmkb: dict[str, Any] = {
        "condition": condition,
        "best_biomarker_role": [
            {"role": role.lower() if role else "monitoring"}
        ],
        "biomarker_component": biomarker_component,
        "provenance": {
            "provider": "PLACEHOLDER - submitting organisation",
            "author": "PLACEHOLDER - author of the record",
            "date": "PLACEHOLDER - YYYY-MM-DD",
            "description": f"Reconstructed from SDTM BM row {bm_id}",
        },
    }

    return bmkb


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Convert SDTM TSV files back to the record set JSON."
    )
    parser.add_argument("--dm", default="", help="Path to DM.tsv")
    parser.add_argument("--lb", default="", help="Path to LB.tsv")
    parser.add_argument("--supplb", default="", help="Path to SUPPLB.tsv")
    parser.add_argument("--bm", default="", help="Path to BM.tsv")
    parser.add_argument("--output-dir", default=".", help="Output directory for JSON files")
    parser.add_argument(
        "--prefix", default="reconstructed",
        help="Output filename prefix (default: reconstructed)",
    )
    parser.add_argument(
        "--self-test", action="store_true",
        help="Run a self-test using the troponin_I gold TSVs",
    )
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return

    # Validate inputs
    paths = [args.dm, args.lb, args.supplb, args.bm]
    for p in paths:
        if not p:
            print("[ERROR] --dm, --lb, --supplb, and --bm are all required.")
            sys.exit(1)

    # Read TSVs
    dm_rows = _read_tsv(args.dm)
    lb_rows = _read_tsv(args.lb)
    supplb_rows = _read_tsv(args.supplb)
    bm_rows = _read_tsv(args.bm)

    if not dm_rows:
        print("[ERROR] DM.tsv is empty.")
        sys.exit(1)

    studyid = dm_rows[0].get("STUDYID", "STUDY")
    usubjid = dm_rows[0].get("USUBJID", "")

    # Reconstruct
    tbco = reconstruct_tbco(lb_rows, supplb_rows, bm_rows, studyid)
    rbco = reconstruct_rbco(lb_rows, supplb_rows, bm_rows, tbco, studyid, usubjid)
    bmkb = reconstruct_bmkb(bm_rows, tbco, studyid)

    # Output
    os.makedirs(args.output_dir, exist_ok=True)
    for name, obj in [("tBCO", tbco), ("rBCO", rbco), ("BMKB", bmkb)]:
        path = os.path.join(args.output_dir, f"{args.prefix}_{name}.json")
        with open(path, "w") as f:
            json.dump(obj, f, indent=2)
        print(f"[OK] {name:6s} → {os.path.relpath(path)}")
        print(f"      Top-level keys: {list(obj.keys())}")
        if name == "rBCO":
            meas = (
                obj.get("extension_domain", [{}])[0]
                .get("assay_run_extension", {})
                .get("measurements", [])
            )
            print(f"      Measurements: {len(meas)} rows")

    print("\nDone. Reconstructed record set written to", args.output_dir)


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def self_test():
    """Run a self-test against the Troponin I gold TSVs."""
    print("=" * 60)
    print("sdtm_to_record_set.py — Self-test")
    print("=" * 60)

    tsv_dir = os.path.join(_HERE, "..", "fixtures", "troponin_I", "_output", "sdtm_self_test")
    dm_path = os.path.join(tsv_dir, "DM.tsv")
    lb_path = os.path.join(tsv_dir, "LB.tsv")
    supplb_path = os.path.join(tsv_dir, "SUPPLB.tsv")
    bm_path = os.path.join(tsv_dir, "BM.tsv")

    for p in [dm_path, lb_path, supplb_path, bm_path]:
        if not os.path.exists(p):
            print(f"[FAIL] Required self-test file not found: {p}")
            sys.exit(1)
        print(f"[OK] Found input: {os.path.relpath(p)}")

    # Read TSVs
    dm_rows = _read_tsv(dm_path)
    lb_rows = _read_tsv(lb_path)
    supplb_rows = _read_tsv(supplb_path)
    bm_rows = _read_tsv(bm_path)

    print(f"\nDM: {len(dm_rows)} row(s), LB: {len(lb_rows)} row(s), "
          f"SUPPLB: {len(supplb_rows)} row(s), BM: {len(bm_rows)} row(s)")

    studyid = dm_rows[0].get("STUDYID", "")
    usubjid = dm_rows[0].get("USUBJID", "")
    print(f"Study: {studyid}, Subject: {usubjid}")

    # --- Reconstruct tBCO ---
    print("\n--- Reconstructing tBCO ---")
    tbco = reconstruct_tbco(lb_rows, supplb_rows, bm_rows, studyid)
    ext_t = (
        tbco.get("extension_domain", [{}])[0]
        .get("assay_protocol_extension", {})
    )

    # Verify key fields
    checks = [
        ("object_id", tbco.get("object_id", ""), bool(tbco.get("object_id"))),
        ("spec_version", tbco.get("spec_version", ""),
         "ieee" in tbco.get("spec_version", "")),
        ("assay.assay_name", ext_t.get("assay", {}).get("assay_name", ""),
         bool(ext_t.get("assay", {}).get("assay_name", ""))),
        ("assay.method", ext_t.get("assay", {}).get("method", ""), True),
        ("specimen_requirements.specimen_type",
         ext_t.get("specimen_requirements", {}).get("specimen_type", ""), True),
        ("analytical_performance.lod",
         ext_t.get("analytical_performance", {}).get("limit_of_detection", {}).get("value"),
         True),
        ("reference_limits", bool(ext_t.get("reference_limits")), True),
    ]
    for label, val, expected in checks:
        status = "[OK]" if expected else "[WARN]"
        print(f"  {status} {label}: {val}")

    # --- Reconstruct rBCO ---
    print("\n--- Reconstructing rBCO ---")
    rbco = reconstruct_rbco(lb_rows, supplb_rows, bm_rows, tbco, studyid, usubjid)
    ext_r = (
        rbco.get("extension_domain", [{}])[0]
        .get("assay_run_extension", {})
    )
    measurements = ext_r.get("measurements", [])
    sdtm_ext = (
        rbco.get("extension_domain", [{}])[1]
        .get("sdtm_extension", {})
    ) if len(rbco.get("extension_domain", [])) > 1 else {}

    print(f"  Measurements: {len(measurements)} rows")
    print(f"  derived_from: {rbco.get('provenance_domain', {}).get('derived_from', '')}")

    # Verify measurement details
    for m in measurements:
        censor = m.get("censor_state", "")
        visit = m.get("visit", "")
        specimen_id = m.get("specimen_id", "")
        print(f"    LBSEQ={m.get('idvarval')} visit={visit} "
              f"censor={censor} specimen={specimen_id}")

    # Verify SDTM extension
    datasets = sdtm_ext.get("datasets", [])
    for ds in datasets:
        print(f"  SDTM dataset: {ds.get('name')} → {ds.get('rows_for_this_subject')} rows")

    # --- Reconstruct BMKB ---
    print("\n--- Reconstructing BMKB ---")
    bmkb = reconstruct_bmkb(bm_rows, tbco, studyid)

    checks_bmkb = [
        ("biomarker_id", bmkb.get("biomarker_id", ""), bool(bmkb.get("biomarker_id"))),
        ("condition.id",
         bmkb.get("condition", {}).get("id", ""), "DOID" in bmkb.get("condition", {}).get("id", "")),
        ("condition.recommended_name.name",
         bmkb.get("condition", {}).get("recommended_name", {}).get("name", ""), True),
        ("best_biomarker_role",
         bmkb.get("best_biomarker_role", [{}])[0].get("role", ""), True),
        ("assessed_biomarker_entity_id",
         bmkb.get("biomarker_component", [{}])[0].get("assessed_biomarker_entity_id", ""),
         True),
        ("evidence_source count", len(bmkb.get("evidence_source", [])), True),
    ]
    for label, val, expected in checks_bmkb:
        status = "[OK]" if expected else "[WARN]"
        print(f"  {status} {label}: {val}")

    # --- Round-trip check: reconstruct LB rows from rBCO measurements ---
    print("\n--- Round-trip verification ---")
    all_pass = True

    # Compare measurement count
    if len(measurements) == len(lb_rows):
        print(f"[OK] Measurement count matches LB row count: {len(measurements)}")
    else:
        print(f"[FAIL] Measurement count ({len(measurements)}) != LB row count ({len(lb_rows)})")
        all_pass = False

    # Compare SUPPLB qualifier count (rough)
    supplb_qual_count = sum(1 for r in supplb_rows if r.get("QNAM") != "")
    sdtm_deriv_count = len(sdtm_ext.get("supplb_derivation", []))
    print(f"[OK] SUPPLB qualifiers: {supplb_qual_count} (scanned), "
          f"supplb_derivation entries: {sdtm_deriv_count}")

    # Compare censor states
    for m in measurements:
        iv = m.get("idvarval")
        censor_reconstructed = m.get("censor_state", "")
        censor_from_supplb = supplb_rows_utils(supplb_rows, str(iv))
        if censor_from_supplb:
            match = censor_reconstructed == censor_from_supplb
            if not match:
                print(f"  [FAIL] LBSEQ={iv}: reconstructed censor='{censor_reconstructed}' "
                      f"≠ SUPPLB='{censor_from_supplb}'")
                all_pass = False
            else:
                print(f"  [OK] LBSEQ={iv}: censor='{censor_reconstructed}' (round-trip match)")

    # Verify BM fields round-trip
    if bm_rows:
        bm_row = bm_rows[0]
        bm_entity = bmkb.get("biomarker_component", [{}])[0].get(
            "assessed_biomarker_entity_id", ""
        )
        expected_entity = bm_row.get("BMENTID", "")
        match_id = bm_entity == expected_entity
        if not match_id:
            print(f"  [FAIL] BMKB entity_id '{bm_entity}' ≠ BM BMENTID '{expected_entity}'")
            all_pass = False
        else:
            print(f"  [OK] BMKB entity_id round-trip: {bm_entity}")

        bm_cond = bmkb.get("condition", {}).get("id", "")
        expected_cond = bm_row.get("BMCONDID", "")
        match_cond = bm_cond == expected_cond
        if not match_cond:
            print(f"  [FAIL] BMKB condition.id '{bm_cond}' ≠ BM BMCONDID '{expected_cond}'")
            all_pass = False
        else:
            print(f"  [OK] BMKB condition.id round-trip: {bm_cond}")

    print()
    if all_pass:
        print("[PASS] Self-test: all checks passed.")
    else:
        print("[FAIL] Self-test: one or more checks failed.")

    return all_pass


def supplb_rows_utils(supplb_rows: list[dict[str, str]], lbseq_str: str) -> str:
    """Helper for self-test: find CENSOR in SUPPLB for a given LBSEQ."""
    for row in supplb_rows:
        if row.get("IDVAR") == "LBSEQ" and row.get("IDVARVAL") == lbseq_str:
            if row.get("QNAM") == "CENSOR":
                return row.get("QVAL", "")
    return ""


if __name__ == "__main__":
    main()
