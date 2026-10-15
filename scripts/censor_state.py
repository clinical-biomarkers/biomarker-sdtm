#!/usr/bin/env python3
"""censor_state.py — Censoring logic for biomarker measurements.

Used by both the forward (record set → SDTM) and reverse (SDTM → record set)
transforms.  A standalone, importable module.

Four censoring zones (BEST-aligned, from the Troponin I example):

    below_lod           value < LoD
    detected_below_lloq LoD ≤ value < LLOQ
    quantifiable        LLOQ ≤ value ≤ ULOQ
    above_uloq          value > ULOQ

Usage
-----
    from censor_state import resolve_censor_state, make_sdtm_fields

    state = resolve_censor_state(0.021, 0.006, 0.03, 50.0)
    lborres, lbstressn = make_sdtm_fields(state, 0.021, 0.006, 0.03, 50.0)

Run self-test:
    python censor_state.py
"""

from __future__ import annotations

import re
from typing import Optional

# ---------------------------------------------------------------------------
# Controlled vocabulary
# ---------------------------------------------------------------------------

CENSOR_STATES = frozenset({
    "below_lod",
    "detected_below_lloq",
    "quantifiable",
    "above_uloq",
})

CENSOR_EXPLANATIONS = {
    "below_lod": "Value below the limit of detection",
    "detected_below_lloq": "Detected but below the lower limit of quantification",
    "quantifiable": "Within the quantifiable range",
    "above_uloq": "Above the upper limit of quantification",
}

#: Accepted synonyms, normalised to the canonical vocabulary.
CENSOR_STATE_ALIASES = {"measurable": "quantifiable"}


def normalise_censor_state(censor_state: str) -> str:
    """Map an accepted synonym to its canonical state; reject anything unknown.

    A censored value must never be mistaken for a quantifiable one: silently
    passing an unrecognised state through would emit a numeric LBSTRESN for a
    censored result, which is invalid SDTM.
    """
    canonical = CENSOR_STATE_ALIASES.get(censor_state, censor_state)
    if canonical not in CENSOR_STATES:
        raise ValueError(
            f"unknown censor state {censor_state!r}; expected one of "
            f"{sorted(CENSOR_STATES)} (or the synonym "
            f"{sorted(CENSOR_STATE_ALIASES)})"
        )
    return canonical

# ---------------------------------------------------------------------------
# Public API — Forward direction
# ---------------------------------------------------------------------------


def resolve_censor_state(
    value: float,
    lod: float,
    lloq: float,
    uloq: float,
) -> str:
    """Determine the censoring zone for a measured value.

    Parameters
    ----------
    value : float
        The measured numeric concentration.
    lod, lloq, uloq : float
        Assay analytical-performance thresholds from the tBCO.

    Returns
    -------
    str
        One of ``CENSOR_STATES``.

    Raises
    ------
    ValueError
        If any threshold is missing (NaN or None-like).
    """
    if lod is None or lloq is None or uloq is None:
        raise ValueError(
            "All three analytical-performance thresholds (LoD, LLOQ, ULOQ) "
            "are required to resolve a censor state."
        )

    if value < lod:
        return "below_lod"
    if value < lloq:
        return "detected_below_lloq"
    if value > uloq:
        return "above_uloq"
    return "quantifiable"


def make_sdtm_fields(
    censor_state: str,
    value: float,
    lod: float,
    lloq: float,
    uloq: float,
) -> tuple[str, Optional[float]]:
    """Produce the LBORRES / LBSTRESN pair from a censor state and value.

    Returns
    -------
    (lborres, lbstressn)
        ``lborres`` is a string (e.g. ``"<0.006"``, ``"0.021"``).
        ``lbstressn`` is the numeric value or ``None`` for censored results.
    """
    censor_state = normalise_censor_state(censor_state)

    if censor_state == "below_lod":
        return (f"<{lod}", None)
    if censor_state == "detected_below_lloq":
        return (f"<{lloq}", None)
    if censor_state == "above_uloq":
        return (f">{uloq}", None)

    # quantifiable
    return (str(value), value)


# ---------------------------------------------------------------------------
# Public API — Reverse direction (SDTM → record set)
# ---------------------------------------------------------------------------


def derive_censor_state_from_sdtm(
    lborres: str,
    lbstressn_str: str,
    lod: Optional[float] = None,
    lloq: Optional[float] = None,
    uloq: Optional[float] = None,
) -> str:
    """Infer censor_state from SDTM LB fields (reverse transform).

    Heuristic (matches ``sdtm_to_record_set.py``):

    1. If LBSTRESN is populated → check thresholds (quantifiable / above_uloq).
    2. If LBSTRESN is empty → examine LBORRES pattern (``<N``, ``>N``, text).
    3. Fallback: try to parse LBORRES as a number.

    Parameters
    ----------
    lborres : str
        Original result (e.g. ``"0.021"``, ``"<0.006"``).
    lbstressn_str : str
        Numeric result as a string (may be empty).
    lod, lloq, uloq : float or None
        Analytical thresholds (optional; improve accuracy when provided).

    Returns
    -------
    str
        One of ``CENSOR_STATES``.
    """
    lbstressn: Optional[float] = None
    if lbstressn_str:
        try:
            lbstressn = float(lbstressn_str)
        except ValueError:
            pass

    # --- LBSTRESN is populated → numeric value exists ---
    if lbstressn is not None:
        if uloq is not None and lbstressn > uloq:
            return "above_uloq"
        if lloq is not None and lbstressn >= lloq:
            return "quantifiable"
        return "detected_below_lloq"

    # --- LBSTRESN is empty → examine LBORRES ---
    if lborres.startswith("<"):
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

    # Fallback — try parsing as a number
    try:
        float(lborres)
        return "quantifiable"
    except ValueError:
        return "detected_below_lloq"


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _self_test() -> None:
    """Exercise all four censoring zones in both directions."""
    print("=" * 60)
    print("  censor_state.py — Self-test")
    print("=" * 60)

    errors: list[str] = []

    # Troponin I reference thresholds
    LOD = 0.006
    LLOQ = 0.03
    ULOQ = 50.0

    test_cases = [
        # (value, expected_state, expected_lborres_starts)
        (0.004, "below_lod", "<0.006"),
        (0.021, "detected_below_lloq", "<0.03"),
        (0.058, "quantifiable", "0.058"),
        (100.0, "above_uloq", ">50.0"),
        (0.03, "quantifiable", "0.03"),  # boundary: == LLOQ
        (50.0, "quantifiable", "50.0"),   # boundary: == ULOQ
    ]

    # --- Forward test ---
    for value, expected_state, expected_lborres_start in test_cases:
        state = resolve_censor_state(value, LOD, LLOQ, ULOQ)
        if state != expected_state:
            errors.append(
                f"resolve({value}): got '{state}', expected '{expected_state}'"
            )

        lborres, lbstressn = make_sdtm_fields(state, value, LOD, LLOQ, ULOQ)
        if not lborres.startswith(expected_lborres_start):
            errors.append(
                f"make_sdtm_fields('{state}', {value}): "
                f"got LBORRES='{lborres}', expected starts with '{expected_lborres_start}'"
            )

        # Check null LBSTRESN for censored states
        if state in ("below_lod", "detected_below_lloq", "above_uloq"):
            if lbstressn is not None:
                errors.append(
                    f"make_sdtm_fields('{state}', {value}): "
                    f"LBSTRESN should be None, got {lbstressn}"
                )
        else:
            if lbstressn is None:
                errors.append(
                    f"make_sdtm_fields('{state}', {value}): "
                    f"LBSTRESN should not be None"
                )

    # --- Reverse test ---
    reverse_cases = [
        ("<0.006", "", LOD, LLOQ, ULOQ, "below_lod"),
        ("<0.03", "", LOD, LLOQ, ULOQ, "detected_below_lloq"),
        ("0.058", "0.058", LOD, LLOQ, ULOQ, "quantifiable"),
        (">50", "", LOD, LLOQ, ULOQ, "above_uloq"),
        # Without thresholds, fallback logic rounds conservatively
        ("<0.006", "", None, None, None, "detected_below_lloq"),
        ("<0.03", "", None, None, None, "detected_below_lloq"),
    ]

    for lborres, lbstressn_str, lod, lloq, uloq, expected_state in reverse_cases:
        state = derive_censor_state_from_sdtm(lborres, lbstressn_str, lod, lloq, uloq)
        if state != expected_state:
            errors.append(
                f"derive({lborres!r}, {lbstressn_str!r}): "
                f"got '{state}', expected '{expected_state}'"
            )

    # --- Report ---
    if errors:
        print("\nFAILED:")
        for e in errors:
            print(f"  - {e}")
        print(f"\n{len(errors)} error(s)")
        import sys
        sys.exit(1)

    print(f"\n  All {len(test_cases) + len(reverse_cases)} checks PASSED")
    print("  Censor states: below_lod, detected_below_lloq, quantifiable, above_uloq")
    print("  Both forward and reverse directions verified.")
    print("=" * 60)


if __name__ == "__main__":
    _self_test()
