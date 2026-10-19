#!/usr/bin/env python3
"""finalize_draft.py — turn an agent-authored BCO draft into a valid IEEE 2791 object.

The agent writes the BCO **directly** — reading ``assets/<x>_template.json`` plus the
source documents — instead of round-tripping through an intermediate "input" schema.
This script does the two jobs that must be exact and are not worth re-deriving by hand:

  1. strip the template's ``//_*`` annotation keys (JSON has no comments, so the
     templates carry guidance in ``//_note`` / ``//_help`` keys)
  2. compute the SHA-256 ``etag`` over the canonical JSON

It is the single definition of "a finished BCO". Everything else — deciding values —
is the agent's job.

Usage
-----
    python finalize_draft.py --input draft.json --output tBCO.json
    python finalize_draft.py --input draft.json          # rewrite in place
    python finalize_draft.py --input draft.json --check  # verify etag, write nothing
    python finalize_draft.py --input BMKB.draft.json --output BMKB.json --no-etag
                                                         # strip //_ keys only (BMKB record)
    python finalize_draft.py --self-test

etag definition
---------------
``etag = SHA-256( json.dumps(obj_with_etag_cleared, sort_keys=True, ensure_ascii=False) )``

The ``etag`` field is set to ``""`` **before** hashing, so the digest is not
self-referential and can be recomputed from the file alone. Key order never affects
the result. Re-running finalize on a finished object is a no-op (idempotent).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from typing import Any

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------


def strip_comments(obj: Any) -> Any:
    """Recursively drop keys starting with ``//_`` (template annotations)."""
    if isinstance(obj, dict):
        return {k: strip_comments(v) for k, v in obj.items() if not k.startswith("//_")}
    if isinstance(obj, list):
        return [strip_comments(item) for item in obj]
    return obj


def compute_etag(obj: dict) -> str:
    """SHA-256 of the canonical JSON with the ``etag`` field cleared."""
    canonical = dict(obj)
    canonical["etag"] = ""
    raw = json.dumps(canonical, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def finalize(obj: dict) -> dict:
    """Strip annotations and set a fresh ``etag``. Idempotent."""
    out = strip_comments(obj)
    out["etag"] = compute_etag(out)
    return out


def has_annotations(obj: Any) -> bool:
    """True if any ``//_`` annotation key is left anywhere in *obj*."""
    if isinstance(obj, dict):
        return any(k.startswith("//_") or has_annotations(v) for k, v in obj.items())
    if isinstance(obj, list):
        return any(has_annotations(v) for v in obj)
    return False


def verify_etag(obj: dict) -> bool:
    """True if the object is finalized: no ``//_`` keys and an ``etag`` matching its content."""
    current = obj.get("etag", "")
    return bool(current) and not has_annotations(obj) and current == compute_etag(obj)


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

_GOLD = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "examples", "troponin_I",
)


def _self_test() -> int:
    errors: list[str] = []

    # 1) annotation keys are stripped, nested ones too
    draft = {"a": 1, "//_note": "x", "d": {"//_help": "y", "b": 2}, "": []}
    out = strip_comments(draft)
    if "//_note" in out or "//_help" in out.get("d", {}):
        errors.append("strip_comments left //_ keys in place")

    # 2) etag is 64 hex chars and independent of key order
    o1 = {"object_id": "X", "etag": "", "b": 2, "a": 1}
    o2 = {"a": 1, "b": 2, "etag": "", "object_id": "X"}
    e1, e2 = compute_etag(o1), compute_etag(o2)
    if len(e1) != 64 or any(c not in "0123456789abcdef" for c in e1):
        errors.append(f"etag is not 64-char lowercase hex: {e1!r}")
    if e1 != e2:
        errors.append("etag depends on key order — canonicalization is wrong")

    # 3) etag is not self-referential (clearing it is what makes it stable)
    if compute_etag({"etag": "deadbeef", "a": 1}) != compute_etag({"etag": "", "a": 1}):
        errors.append("etag is self-referential")

    # 4) finalize is idempotent
    once = finalize({"object_id": "X", "//_note": "n", "a": 1})
    twice = finalize(once)
    if once != twice:
        errors.append("finalize is not idempotent")

    # 5) verification round-trips
    if not verify_etag(once):
        errors.append("verify_etag rejects a freshly finalized object")
    if verify_etag({**once, "a": 999}):
        errors.append("verify_etag accepts an object whose content changed")
    if verify_etag({**once, "//_note": "left over"}):
        errors.append("verify_etag accepts an object that still has //_ keys")

    # 6) real gold objects survive the round trip
    for fn in ("Troponin_I_tBCO.json", "Troponin_I_patient1_rBCO.json"):
        p = os.path.join(_GOLD, fn)
        if not os.path.exists(p):
            errors.append(f"gold file missing: {fn}")
            continue
        obj = json.load(open(p))
        fin = finalize(obj)
        if not verify_etag(fin):
            errors.append(f"{fn}: finalized object fails etag verification")
        if any(k.startswith("//_") for k in fin):
            errors.append(f"{fn}: annotation key survived")

    if errors:
        print("[SELF-TEST] FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("[SELF-TEST] PASSED — strips annotations, canonical etag, idempotent, "
          "verifiable, gold objects round-trip")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Finalize an agent-authored BCO draft (strip annotations, set etag)."
    )
    parser.add_argument("--input", help="Draft BCO JSON file")
    parser.add_argument("--output", help="Output path (default: rewrite --input in place)")
    parser.add_argument("--no-etag", action="store_true",
                        help="Only strip //_ annotation keys (for the BMKB record, which has no etag)")
    parser.add_argument("--check", action="store_true",
                        help="Verify the existing etag; write nothing")
    parser.add_argument("--self-test", action="store_true",
                        help="Run built-in self-test and exit")
    args = parser.parse_args()

    if args.self_test:
        sys.exit(_self_test())

    if not args.input:
        parser.error("--input is required (or use --self-test)")

    with open(args.input) as f:
        obj = json.load(f)

    if args.check:
        ok = verify_etag(obj)
        why = " (annotation //_ keys left: run finalize)" if has_annotations(obj) else ""
        print(f"[{'OK' if ok else 'MISMATCH'}] {args.input}{why if not ok else ''}")
        sys.exit(0 if ok else 1)

    out = strip_comments(obj) if args.no_etag else finalize(obj)
    dest = args.output or args.input
    with open(dest, "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
        f.write("\n")
    if args.no_etag:
        print(f"[DONE] stripped annotations -> {dest}")
    else:
        print(f"[DONE] finalized -> {dest}  (etag={out['etag'][:12]}…)")


if __name__ == "__main__":
    main()
