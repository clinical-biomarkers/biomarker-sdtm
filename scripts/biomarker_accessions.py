#!/usr/bin/env python3
"""biomarker_accessions.py — entity type -> accession resource (bmkb-model.md §7).

Clinical documents carry entity *names*, not identifiers. This module is the
lookup table from the BiomarkerKB data-submission wiki, exposed as code so the
agent does not have to reproduce it from the reference doc on every run.

Usage
-----
    from biomarker_accessions import accession_resource_for, ENTITY_TYPES

    accession_resource_for("protein")   # -> "UniProt (UPKB)"
    accession_resource_for("glycan")    # -> "GlyTouCan (GTC)"

    python biomarker_accessions.py              # print the whole table
    python biomarker_accessions.py --self-test
"""

from __future__ import annotations

import sys

# Allowed values of ``assessed_entity_type`` (lowercase).
ENTITY_TYPES: tuple[str, ...] = (
    "protein", "gene", "DNA", "RNA", "cell", "lipid",
    "glycan", "metabolite", "element", "image", "condition",
)

# entity type -> resources, in order of preference (fall back only if the
# preferred resource has no entry for the entity).
ACCESSION_RESOURCES: dict[str, tuple[str, ...]] = {
    "protein": ("UniProt (UPKB)", "PDB", "PRO", "NCIt"),
    "peptide": ("PRO",),
    "protein complex": ("PRO", "GO"),
    "gene": ("NCBI",),
    "gene (mutation)": ("NCBI dbSNP",),
    "DNA": ("NCIt",),
    "RNA": ("HGNC", "RNA Central (RNAC)"),
    "miRNA": ("miRBase (MRB)",),
    "glycan": ("GlyTouCan (GTC)", "PubChem"),
    "carbohydrate": ("ChEBI",),
    "metabolite": ("PubChem (PCCID)", "ChEBI"),
    "lipoprotein": ("ChEBI",),
    "chemical element": ("PubChem (PCCID)", "NCIt"),
    "cell": ("CO", "NCIt"),
}

# Ontologies permitted for a condition id.
CONDITION_RESOURCES: tuple[str, ...] = ("DOID", "MONDO", "SNOMED", "NCIt")


def accession_resource_for(entity_type: str) -> str:
    """Preferred accession resource for *entity_type*.

    Raises ValueError for an unknown or mis-cased entity type — the type must be
    lowercase and drawn from the allowed set.
    """
    if entity_type != entity_type.lower():
        raise ValueError(f"assessed_entity_type must be lowercase: {entity_type!r}")
    resources = ACCESSION_RESOURCES.get(entity_type)
    if resources is None:
        raise ValueError(
            f"unknown entity type {entity_type!r}; expected one of {sorted(ENTITY_TYPES)}"
        )
    return resources[0]


def _print_table() -> None:
    print("entity type -> accession resource(s), in order of preference\n")
    for etype in sorted(ACCESSION_RESOURCES):
        mark = " " if etype in ENTITY_TYPES else "*"
        chain = "  →  ".join(ACCESSION_RESOURCES[etype])
        print(f" {mark} {etype:<18} {chain}")
    print("\n* also accepted as an assessed_entity_type variant")
    print(f"\ncondition id ontology: {' / '.join(CONDITION_RESOURCES)}")


def _self_test() -> int:
    errors = []
    if accession_resource_for("protein") != "UniProt (UPKB)":
        errors.append("protein should map to UniProt (UPKB)")
    if accession_resource_for("glycan") != "GlyTouCan (GTC)":
        errors.append("glycan should map to GlyTouCan (GTC)")
    if accession_resource_for("metabolite") != "PubChem (PCCID)":
        errors.append("metabolite should map to PubChem (PCCID)")
    for bad in ("Protein", "PROTEIN"):
        try:
            accession_resource_for(bad)
            errors.append(f"should reject non-lowercase input: {bad!r}")
        except ValueError:
            pass
    try:
        accession_resource_for("unicorn")
        errors.append("should reject an unknown entity type")
    except ValueError:
        pass
    if errors:
        print("[SELF-TEST] FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("[SELF-TEST] PASSED — lookup, preference order, case and unknown-type guards")
    return 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    _print_table()
