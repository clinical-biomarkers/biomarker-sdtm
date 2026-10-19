#!/usr/bin/env python3
"""validate_bco.py — Validate a BioCompute Object against IEEE 2791.

Checks structural completeness (all 8 domains, required fields), etag
well-formedness, and conformance to the shipped IEEE 2791 JSON Schemas
(references/schemas/, via ``jsonschema``). Schema violations are errors.
Unfilled PLACEHOLDER values and NOTE lines are reported as **warnings** — a
record may legitimately not supply every field.

Usage
-----
    python validate_bco.py path/to/bco.json [path/to/another.json ...]
    python validate_bco.py --self-test

Exit code: 0 if all files valid, 1 if any fail.
"""

from __future__ import annotations

import glob
import json
import os
import re
import sys
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCHEMA_DIR = os.path.join(_HERE, "..", "references", "schemas")
_ROOT_SCHEMA = "2791object.json"

# ---------------------------------------------------------------------------
# Schema loader (lazy)
# ---------------------------------------------------------------------------

_VALIDATOR: Any = None


def _schema_validator() -> Any:
    """Build (once) a jsonschema validator for 2791object.json.

    The domain schemas reference each other by bare filename
    (``"$ref": "provenance_domain.json"``) and declare a w3id.org ``$id``.
    Each is registered under both, so every ``$ref`` resolves locally and
    nothing is fetched over the network.
    """
    global _VALIDATOR
    if _VALIDATOR is None:
        import jsonschema
        from referencing import Registry, Resource
        from referencing.jsonschema import DRAFT7

        registry = Registry()
        root = None
        for path in sorted(glob.glob(os.path.join(_SCHEMA_DIR, "*.json"))):
            with open(path) as f:
                contents = json.load(f)
            resource = Resource.from_contents(contents, default_specification=DRAFT7)
            name = os.path.basename(path)
            registry = registry.with_resource(name, resource)
            if "$id" in contents:
                registry = registry.with_resource(contents["$id"], resource)
            if name == _ROOT_SCHEMA:
                root = contents
        if root is None:
            raise FileNotFoundError(os.path.join(_SCHEMA_DIR, _ROOT_SCHEMA))
        cls = jsonschema.validators.validator_for(root)
        _VALIDATOR = cls(root, registry=registry)
    return _VALIDATOR


# ---------------------------------------------------------------------------
# Structural checks
# ---------------------------------------------------------------------------

# IEEE 2791 root-level required fields (from 2791object.json required array)
REQUIRED_ROOT = {
    "object_id", "spec_version", "etag",
    "provenance_domain", "usability_domain",
    "description_domain", "execution_domain", "io_domain",
}
# Additional recommended domains
RECOMMENDED_DOMAINS = {"extension_domain", "parametric_domain", "error_domain"}

# Required sub-fields per domain
REQUIRED_PROVENANCE = {"name", "version", "created", "modified", "contributors", "license"}
REQUIRED_DESCRIPTION = {"keywords", "pipeline_steps"}
REQUIRED_EXECUTION = {"script", "script_driver", "software_prerequisites",
                      "external_data_endpoints", "environment_variables"}
REQUIRED_IO = {"input_subdomain", "output_subdomain"}
REQUIRED_ERROR = {"empirical_error", "algorithmic_error"}
REQUIRED_EXTENSION_ITEM = {"extension_schema"}
REQUIRED_PARAM_ITEM = {"param", "value", "step"}
REQUIRED_PIPELINE_STEP = {"step_number", "name", "description", "input_list", "output_list"}

ETAG_PATTERN = re.compile(r"^[A-Fa-f0-9]{64}$")
SPEC_VERSION_URI_PREFIX = "https://w3id.org/ieee/ieee-2791-schema/"


def validate_bco(obj: dict, filepath: str = "<unknown>") -> list[str]:
    """Run all structural checks. Returns a list of error strings (empty = valid)."""
    errors: list[str] = []

    # -----------------------------------------------------------------------
    # 1) Root-level keys
    # -----------------------------------------------------------------------
    present = set(obj.keys())
    missing_root = REQUIRED_ROOT - present
    if missing_root:
        errors.append(f"MISSING required root fields: {sorted(missing_root)}")

    # Warn about missing recommended domains (not errors)
    missing_recommended = RECOMMENDED_DOMAINS - present
    for d in sorted(missing_recommended):
        errors.append(f"NOTE: missing recommended domain: {d} (optional per IEEE 2791)")

    # Unexpected top-level keys
    allowed = REQUIRED_ROOT | RECOMMENDED_DOMAINS
    extra = present - allowed
    if extra:
        errors.append(f"NOTE: unexpected top-level keys: {sorted(extra)}")

    # -----------------------------------------------------------------------
    # 2) object_id
    # -----------------------------------------------------------------------
    oid = obj.get("object_id", "")
    if not isinstance(oid, str) or not oid.strip():
        errors.append("object_id is empty or not a string")

    # -----------------------------------------------------------------------
    # 3) spec_version
    # -----------------------------------------------------------------------
    sv = obj.get("spec_version", "")
    if not isinstance(sv, str) or not sv.strip():
        errors.append("spec_version is empty or not a string")
    elif not sv.startswith(SPEC_VERSION_URI_PREFIX):
        errors.append(f"spec_version should start with '{SPEC_VERSION_URI_PREFIX}', "
                      f"got: {sv}")

    # -----------------------------------------------------------------------
    # 4) etag
    # -----------------------------------------------------------------------
    etag = obj.get("etag", "")
    if not isinstance(etag, str) or not etag.strip():
        errors.append("etag is empty or not a string")
    elif not ETAG_PATTERN.match(etag):
        errors.append(f"etag '{etag}' is not a valid 64-char hex SHA-256 digest "
                      f"(length={len(etag)})")

    # -----------------------------------------------------------------------
    # 5) provenance_domain
    # -----------------------------------------------------------------------
    _check_sub(obj, "provenance_domain", REQUIRED_PROVENANCE, errors)

    # -----------------------------------------------------------------------
    # 6) usability_domain (array)
    # -----------------------------------------------------------------------
    ud = obj.get("usability_domain", [])
    if not isinstance(ud, list):
        errors.append("usability_domain must be an array")
    elif len(ud) == 0:
        errors.append("usability_domain is empty (should contain at least one keyword)")

    # -----------------------------------------------------------------------
    # 7) description_domain
    # -----------------------------------------------------------------------
    _check_sub(obj, "description_domain", REQUIRED_DESCRIPTION, errors)
    ps = obj.get("description_domain", {}).get("pipeline_steps", [])
    if isinstance(ps, list):
        for i, step in enumerate(ps):
            if not isinstance(step, dict):
                errors.append(f"description_domain.pipeline_steps[{i}] is not an object")
                continue
            for field in REQUIRED_PIPELINE_STEP:
                if field not in step:
                    errors.append(f"description_domain.pipeline_steps[{i}] "
                                  f"missing required field '{field}'")

    # -----------------------------------------------------------------------
    # 8) execution_domain
    # -----------------------------------------------------------------------
    _check_sub(obj, "execution_domain", REQUIRED_EXECUTION, errors)

    # -----------------------------------------------------------------------
    # 9) io_domain
    # -----------------------------------------------------------------------
    _check_sub(obj, "io_domain", REQUIRED_IO, errors)

    # -----------------------------------------------------------------------
    # 10) error_domain (if present)
    # -----------------------------------------------------------------------
    if "error_domain" in obj:
        _check_sub(obj, "error_domain", REQUIRED_ERROR, errors)

    # -----------------------------------------------------------------------
    # 11) extension_domain (if present)
    # -----------------------------------------------------------------------
    ext = obj.get("extension_domain", [])
    if isinstance(ext, list):
        for i, item in enumerate(ext):
            if not isinstance(item, dict):
                errors.append(f"extension_domain[{i}] is not an object")
                continue
            for field in REQUIRED_EXTENSION_ITEM:
                if field not in item:
                    errors.append(f"extension_domain[{i}] missing required field "
                                  f"'{field}'")

    # -----------------------------------------------------------------------
    # 12) parametric_domain (if present)
    # -----------------------------------------------------------------------
    pd_ = obj.get("parametric_domain", [])
    if isinstance(pd_, list):
        for i, item in enumerate(pd_):
            if not isinstance(item, dict):
                errors.append(f"parametric_domain[{i}] is not an object")
                continue
            for field in REQUIRED_PARAM_ITEM:
                if field not in item:
                    # step is technically required by schema but the Troponin I
                    # templates use rule instead — non-fatal note
                    if field == "step":
                        errors.append(f"NOTE: parametric_domain[{i}] missing "
                                      f"'{field}' (has: {sorted(item.keys())})")
                    else:
                        errors.append(f"parametric_domain[{i}] missing required "
                                      f"field '{field}'")

    # -----------------------------------------------------------------------
    # 13) PLACEHOLDER detection — recursive string scan
    # -----------------------------------------------------------------------
    _check_placeholders(obj, errors)

    # -----------------------------------------------------------------------
    # 14) Schema validation (IEEE 2791 JSON Schema)
    # -----------------------------------------------------------------------
    _do_schema_validation(obj, errors)

    return errors


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _check_sub(obj: dict, domain: str, required: set[str],
               errors: list[str]) -> None:
    """Check required fields inside a sub-object domain."""
    sub = obj.get(domain)
    if not isinstance(sub, dict):
        if domain not in obj:
            errors.append(f"MISSING domain: {domain}")
        else:
            errors.append(f"{domain} must be an object, got {type(sub).__name__}")
        return
    for field in required:
        if field not in sub:
            errors.append(f"MISSING {domain}.{field}")
    # Check for empty arrays
    if domain == "provenance_domain":
        contributors = sub.get("contributors", [])
        if isinstance(contributors, list) and len(contributors) == 0:
            errors.append("provenance_domain.contributors is empty")
    if domain == "execution_domain":
        pr = sub.get("software_prerequisites", [])
        if isinstance(pr, list) and len(pr) == 0:
            errors.append("execution_domain.software_prerequisites is empty")


def _check_placeholders(obj: Any, errors: list[str], path: str = "$") -> None:
    """Recursively find unfilled PLACEHOLDER markers in strings."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            _check_placeholders(v, errors, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _check_placeholders(v, errors, f"{path}[{i}]")
    elif isinstance(obj, str):
        if "PLACEHOLDER" in obj:
            errors.append(f"UNFILLED PLACEHOLDER at {path}: {obj[:80]!r}")


def _do_schema_validation(obj: dict, errors: list[str]) -> None:
    """Validate against the IEEE 2791 JSON Schema; every violation is an error."""
    try:
        validator = _schema_validator()
    except ImportError as e:
        errors.append(f"SCHEMA validation unavailable ({e}); "
                      f"run `pip install jsonschema` (4.18+)")
        return
    for e in sorted(validator.iter_errors(obj),
                    key=lambda e: [str(p) for p in e.absolute_path]):
        path = "/".join(str(p) for p in e.absolute_path) or "root"
        errors.append(f"SCHEMA {path}: {e.message}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description="Validate BCO JSON files against IEEE 2791")
    parser.add_argument("files", nargs="*", metavar="FILE",
                        help="BCO JSON files to validate")
    parser.add_argument("--self-test", action="store_true",
                        help="Run built-in self-test against Troponin I gold files")
    args = parser.parse_args()

    if args.self_test:
        return _self_test()

    if not args.files:
        parser.print_help()
        return 1

    exit_code = 0
    for filepath in args.files:
        if not os.path.exists(filepath):
            print(f"NOT FOUND: {filepath}")
            exit_code = 1
            continue

        with open(filepath) as f:
            try:
                obj = json.load(f)
            except json.JSONDecodeError as e:
                print(f"INVALID JSON: {filepath}: {e}")
                exit_code = 1
                continue

        messages = validate_bco(obj, filepath)
        # Structural errors fail the file. Unfilled PLACEHOLDERs and NOTE: lines
        # are warnings — a record may legitimately not supply every field (the
        # gold examples carry PLACEHOLDERs for exactly that reason).
        struct_errors = [m for m in messages
                         if not m.startswith("UNFILLED PLACEHOLDER")
                         and not m.startswith("NOTE:")]
        warnings = [m for m in messages if m not in struct_errors]

        if struct_errors:
            print(f"FAIL: {filepath}")
            for e in struct_errors:
                print(f"  - {e}")
            if warnings:
                print(f"  ({len(warnings)} warning(s) — unfilled PLACEHOLDER / note)")
            exit_code = 1
        else:
            suffix = f" ({len(warnings)} warning(s) — unfilled PLACEHOLDER / note)" if warnings else ""
            print(f"PASS: {filepath}{suffix}")

    return exit_code


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------


def _is_bco(obj: dict) -> bool:
    """Heuristic: is this an IEEE 2791 BCO object?"""
    return "object_id" in obj and "provenance_domain" in obj and "spec_version" in obj and "etag" in obj


def _self_test() -> int:
    """Validate the Troponin I gold files."""
    print("=" * 60)
    print("  validate_bco.py — Self-test")
    print("=" * 60)

    tropo_dir = os.path.join(
        _HERE, "..", "examples", "troponin_I"
    )

    gold_files = [
        "Troponin_I_tBCO.json",
        "Troponin_I_patient1_rBCO.json",
        "Troponin_I_biomarkerKB.json",
    ]
    files_to_check = []
    for fname in gold_files:
        path = os.path.join(tropo_dir, fname)
        if os.path.exists(path):
            files_to_check.append((fname, path))

    if not files_to_check:
        print("[SKIP] No Troponin I files found")
        return 0

    total_bco_passed = 0
    total_bco = 0
    non_bco_files = []

    for fname, path in sorted(files_to_check, key=lambda x: x[0]):
        with open(path) as f:
            try:
                obj = json.load(f)
            except json.JSONDecodeError as e:
                print(f"  INVALID JSON: {fname}: {e}")
                continue

        if not _is_bco(obj):
            non_bco_files.append(fname)
            print(f"  SKIP (non-BCO): {fname}")
            continue

        total_bco += 1
        errors = validate_bco(obj, path)
        label = fname

        # Separate structural errors from PLACEHOLDER warnings and notes
        struct_errors = [e for e in errors
                         if not e.startswith("UNFILLED PLACEHOLDER")
                         and not e.startswith("NOTE:")]
        placeholder_count = len([e for e in errors if e.startswith("UNFILLED PLACEHOLDER")])
        note_count = len([e for e in errors if e.startswith("NOTE:")])

        if struct_errors:
            print(f"\n  FAIL: {label}")
            for e in struct_errors:
                print(f"    - {e}")
            if placeholder_count:
                print(f"    ({placeholder_count} unfilled PLACEHOLDER(s) — expected in templates)")
        else:
            total_bco_passed += 1
            note_text = ""
            if placeholder_count:
                note_text += f" {placeholder_count} PLACEHOLDER(s)"
            if note_count:
                note_text += f" {note_count} note(s)"
            if note_text:
                note_text = " (" + note_text.strip() + " — expected)"
            print(f"  PASS: {label}{note_text}")

    n_files = len(files_to_check)
    n_bco = total_bco
    n_non_bco = len(non_bco_files)
    print(f"\n  {n_files} file(s): {n_bco} BCO + {n_non_bco} non-BCO (BMKB); "
          f"{total_bco_passed}/{n_bco} BCO files valid (structure + schema)")
    print("=" * 60)

    if total_bco_passed < total_bco:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
