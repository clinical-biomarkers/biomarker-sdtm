#!/usr/bin/env python3
"""censor_state.py — censor zones for biomarker measurements.

Decides which of the four zones a value falls in, and the LBORRES / LBSTRESN
pair each zone produces. Used by both converters. The zone table itself is
documented once, in references/pitfalls.md §1.

Policy (owner decision B02): a result detected below the LLOQ keeps its
numeric value; only results below the LoD or above the ULOQ are reported as
an operator plus limit with a null LBSTRESN.

Usage
-----
    from censor_state import resolve_censor_state, make_sdtm_fields

    state = resolve_censor_state(0.021, 0.006, 0.03, 50.0)   # detected_below_lloq
    lborres, lbstresn = make_sdtm_fields(state, 0.021, 0.006, 0.03, 50.0)

    # a result exactly as the lab reported it, operator included
    censor_state_for_reported("<0.006", 0.006, 0.03, 50.0)   # below_lod

    python scripts/censor_state.py --self-test
"""

from __future__ import annotations

import math
import re
import sys
from typing import Optional

CENSOR_STATES = frozenset({
    "below_lod",
    "detected_below_lloq",
    "quantifiable",
    "above_uloq",
})

#: Accepted synonyms, normalised to the canonical vocabulary.
CENSOR_STATE_ALIASES = {"measurable": "quantifiable"}

#: Zones reported as operator + limit, with LBSTRESN null.
CENSORED_TO_BOUND = {"below_lod": ("<", "lod"), "above_uloq": (">", "uloq")}

_NUM = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"
_BOUND_RE = re.compile(rf"^\s*([<>])\s*=?\s*({_NUM})\s*$")


def fmt_number(v: float) -> str:
    """Render a number the way a lab reports it: 50.0 -> '50', 0.006 -> '0.006'."""
    return format(v, "g") if isinstance(v, float) else str(v)


def normalise_censor_state(censor_state: str) -> str:
    """Map an accepted synonym to its canonical state; reject anything unknown."""
    canonical = CENSOR_STATE_ALIASES.get(censor_state, censor_state)
    if canonical not in CENSOR_STATES:
        raise ValueError(
            f"unknown censor state {censor_state!r}; expected one of "
            f"{sorted(CENSOR_STATES)} (or the synonym {sorted(CENSOR_STATE_ALIASES)})"
        )
    return canonical


def check_limits(lod: Optional[float], lloq: Optional[float],
                 uloq: Optional[float]) -> None:
    """Raise ValueError unless LoD, LLOQ and ULOQ are present, finite and ordered."""
    named = (("LoD", lod), ("LLOQ", lloq), ("ULOQ", uloq))
    missing = [n for n, v in named if v is None]
    if missing:
        raise ValueError(
            f"tBCO analytical_performance {', '.join(missing)} is null; all three "
            f"thresholds (LoD, LLOQ, ULOQ) are needed to resolve a censor state"
        )
    bad = [n for n, v in named if not isinstance(v, (int, float)) or not math.isfinite(v)]
    if bad:
        raise ValueError(f"tBCO analytical_performance {', '.join(bad)} is not a finite number")
    if uloq <= 0:
        raise ValueError(f"ULOQ is {uloq}; a non-positive ULOQ is an unfilled placeholder, "
                         f"not a real limit")
    if not (lod <= lloq <= uloq):
        raise ValueError(f"limits out of order: LoD {lod}, LLOQ {lloq}, ULOQ {uloq} "
                         f"(expected LoD <= LLOQ <= ULOQ)")


# ---------------------------------------------------------------------------
# Forward direction
# ---------------------------------------------------------------------------

def resolve_censor_state(value: float, lod: float, lloq: float, uloq: float) -> str:
    """The censor zone of a measured *value* against the tBCO limits."""
    check_limits(lod, lloq, uloq)
    if value is None or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"cannot resolve a censor state for value {value!r}")
    if value < lod:
        return "below_lod"
    if value < lloq:
        return "detected_below_lloq"
    if value > uloq:
        return "above_uloq"
    return "quantifiable"


def make_sdtm_fields(censor_state: str, value: Optional[float], lod: Optional[float],
                     lloq: Optional[float], uloq: Optional[float]) -> tuple[str, Optional[float]]:
    """The (LBORRES, LBSTRESN) pair for a censor state.

    ``below_lod`` and ``above_uloq`` give ``"<LoD"`` / ``">ULOQ"`` and null.
    ``detected_below_lloq`` and ``quantifiable`` give the value itself; with no
    value, ``detected_below_lloq`` falls back to ``"<LLOQ"`` and null.
    """
    censor_state = normalise_censor_state(censor_state)
    limits = {"lod": lod, "lloq": lloq, "uloq": uloq}

    if censor_state in CENSORED_TO_BOUND:
        op, key = CENSORED_TO_BOUND[censor_state]
        if limits[key] is None:
            raise ValueError(f"censor state {censor_state!r} needs the {key.upper()}, "
                             f"which is null in the tBCO analytical_performance")
        return (f"{op}{fmt_number(limits[key])}", None)

    if value is not None:
        return (fmt_number(value), value)
    if censor_state == "detected_below_lloq":
        if lloq is None:
            raise ValueError("detected_below_lloq with no value needs the LLOQ, which is null")
        return (f"<{fmt_number(lloq)}", None)
    raise ValueError("a quantifiable result needs a value")


def parse_reported(raw: str) -> tuple[Optional[str], Optional[float]]:
    """Split a result as reported: '<0.006' -> ('<', 0.006); '0.021' -> (None, 0.021).

    Returns (None, None) for text that is neither a number nor a bound.
    """
    raw = (raw or "").strip()
    m = _BOUND_RE.match(raw)
    if m:
        return m.group(1), float(m.group(2))
    try:
        return None, float(raw)
    except ValueError:
        return None, None


def censor_state_for_reported(raw: str, lod: float, lloq: float, uloq: float) -> str:
    """The censor zone of a result as the lab reported it: '0.021', '<0.006', '>50'.

    A number goes through resolve_censor_state(). A '<' bound at or below the LoD
    is below_lod; a '<' bound above the LoD (e.g. '<0.03') is detected_below_lloq;
    any '>' bound is above_uloq. Text that is neither raises ValueError.
    """
    check_limits(lod, lloq, uloq)
    op, number = parse_reported(raw)
    if number is None:
        raise ValueError(f"result {raw!r} is neither a number nor '<x' / '>x'")
    if op is None:
        return resolve_censor_state(number, lod, lloq, uloq)
    if op == ">":
        return "above_uloq"
    return "below_lod" if number <= lod else "detected_below_lloq"


# ---------------------------------------------------------------------------
# Reverse direction (SDTM → record set)
# ---------------------------------------------------------------------------

def derive_censor_state_from_sdtm(lborres: str, lbstresn_str: str,
                                  lod: Optional[float] = None, lloq: Optional[float] = None,
                                  uloq: Optional[float] = None) -> str:
    """Infer the censor state from LB fields when SUPPLB carries no CENSOR row."""
    value: Optional[float] = None
    if lbstresn_str not in (None, ""):
        try:
            value = float(lbstresn_str)
        except ValueError:
            value = None
    if value is None:
        op, value_from_orres = parse_reported(lborres)
        if op == ">":
            return "above_uloq"
        if op == "<":
            if lod is not None and value_from_orres is not None and value_from_orres <= lod:
                return "below_lod"
            if lod is None and lloq is None and "lod" in (lborres or "").lower():
                return "below_lod"
            return "detected_below_lloq"
        value = value_from_orres
        if value is None:
            return "below_lod" if "lod" in (lborres or "").lower() else "detected_below_lloq"

    if lod is not None and value < lod:
        return "below_lod"
    if lloq is not None and value < lloq:
        return "detected_below_lloq"
    if uloq is not None and value > uloq:
        return "above_uloq"
    return "quantifiable"


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _self_test() -> int:
    errors: list[str] = []
    LOD, LLOQ, ULOQ = 0.006, 0.03, 50.0

    forward = [
        # value, state, LBORRES, LBSTRESN
        (0.004, "below_lod", "<0.006", None),
        (0.021, "detected_below_lloq", "0.021", 0.021),   # B02: keeps its value
        (0.03, "quantifiable", "0.03", 0.03),              # == LLOQ
        (0.058, "quantifiable", "0.058", 0.058),
        (50.0, "quantifiable", "50", 50.0),                # == ULOQ
        (100.0, "above_uloq", ">50", None),
    ]
    for value, state, orres, stresn in forward:
        got = resolve_censor_state(value, LOD, LLOQ, ULOQ)
        if got != state:
            errors.append(f"resolve({value}) = {got}, expected {state}")
        pair = make_sdtm_fields(state, value, LOD, LLOQ, ULOQ)
        if pair != (orres, stresn):
            errors.append(f"make_sdtm_fields({state}, {value}) = {pair}, expected {(orres, stresn)}")

    if make_sdtm_fields("detected_below_lloq", None, LOD, LLOQ, ULOQ) != ("<0.03", None):
        errors.append("detected_below_lloq with no value should give '<LLOQ'")
    if make_sdtm_fields("measurable", 1.0, LOD, LLOQ, ULOQ) != ("1", 1.0):
        errors.append("synonym 'measurable' not accepted")

    must_raise = [
        ("unknown state", lambda: make_sdtm_fields("not_detected", 1.0, LOD, LLOQ, ULOQ)),
        ("null limit", lambda: resolve_censor_state(1.0, None, LLOQ, ULOQ)),
        ("NaN value", lambda: resolve_censor_state(float("nan"), LOD, LLOQ, ULOQ)),
        ("NaN limit", lambda: resolve_censor_state(1.0, float("nan"), LLOQ, ULOQ)),
        ("unordered limits", lambda: resolve_censor_state(1.0, 0.05, 0.03, 50.0)),
        ("0.0 placeholders", lambda: resolve_censor_state(0.01, 0.0, 0.0, 0.0)),
        ("below_lod, null LoD", lambda: make_sdtm_fields("below_lod", None, None, LLOQ, ULOQ)),
    ]
    for label, fn in must_raise:
        try:
            fn()
            errors.append(f"should raise: {label}")
        except ValueError:
            pass

    for raw, expected in (("0.021", "detected_below_lloq"), ("<0.006", "below_lod"),
                          ("< 0.006", "below_lod"), ("<0.03", "detected_below_lloq"),
                          (">50", "above_uloq"), ("0.058", "quantifiable")):
        got = censor_state_for_reported(raw, LOD, LLOQ, ULOQ)
        if got != expected:
            errors.append(f"censor_state_for_reported({raw!r}) = {got}, expected {expected}")
    try:
        censor_state_for_reported("NEGATIVE", LOD, LLOQ, ULOQ)
        errors.append("censor_state_for_reported should reject text")
    except ValueError:
        pass

    reverse = [
        ("<0.006", "", LOD, LLOQ, ULOQ, "below_lod"),
        ("< 0.006", "", LOD, LLOQ, ULOQ, "below_lod"),
        ("<6e-3", "", LOD, LLOQ, ULOQ, "below_lod"),
        ("<0.03", "", LOD, LLOQ, ULOQ, "detected_below_lloq"),
        ("0.021", "0.021", LOD, LLOQ, ULOQ, "detected_below_lloq"),
        ("0.004", "0.004", LOD, LLOQ, ULOQ, "below_lod"),
        ("0.058", "0.058", LOD, LLOQ, ULOQ, "quantifiable"),
        (">50", "", LOD, LLOQ, ULOQ, "above_uloq"),
        ("0.058", "", None, None, None, "quantifiable"),
    ]
    for orres, stresn, lod, lloq, uloq, expected in reverse:
        got = derive_censor_state_from_sdtm(orres, stresn, lod, lloq, uloq)
        if got != expected:
            errors.append(f"derive({orres!r}, {stresn!r}) = {got}, expected {expected}")

    if errors:
        print("[SELF-TEST] FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    n = len(forward) * 2 + 2 + len(must_raise) + len(reverse) + 7
    print(f"[SELF-TEST] PASSED — {n} checks (forward, guards, reverse)")
    return 0


if __name__ == "__main__":
    sys.exit(_self_test())
