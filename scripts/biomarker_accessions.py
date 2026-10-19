#!/usr/bin/env python3
"""biomarker_accessions.py — entity type -> accession resource, and OLS id -> CURIE.

Clinical documents carry entity *names*, not identifiers. This module holds the
BiomarkerKB resource table (references/bmkb-model.md §7) as code, and marks
which resources the agent can reach through the OLS MCP server, the only
lookup the skill uses (owner decision H04). A resource OLS does not serve is
left unmapped (PLACEHOLDER) rather than guessed.

All entity types are lowercase (owner decision B04); input is normalised.

Usage
-----
    python scripts/biomarker_accessions.py              # print the table
    python scripts/biomarker_accessions.py --self-test

    from biomarker_accessions import accession_resource_for, curie_from_ols
    accession_resource_for("protein")    # -> "UPKB"
    curie_from_ols("PR_P19429")          # -> "UPKB:P19429"
"""

from __future__ import annotations

import re
import sys

# Allowed values of BMKB ``assessed_entity_type`` (lowercase).
ENTITY_TYPES: tuple[str, ...] = (
    "protein", "gene", "dna", "rna", "cell", "lipid",
    "glycan", "metabolite", "element", "image", "condition",
)

# More specific kinds of entity: each has its own resource chain but is written
# as its parent type in ``assessed_entity_type``.
SUBTYPES: dict[str, str] = {
    "peptide": "protein",
    "protein complex": "protein",
    "gene (mutation)": "gene",
    "mirna": "rna",
    "carbohydrate": "glycan",
    "lipoprotein": "lipid",
    "chemical element": "element",
}

# CURIE prefix -> (resource name, OLS ontology id or None when OLS does not serve it)
RESOURCES: dict[str, tuple[str, str | None]] = {
    "UPKB": ("UniProt", "pr"),        # via Protein Ontology: PR_<UniProt acc> -> UPKB:<acc>
    "PDB": ("Protein Data Bank", None),
    "PR": ("Protein Ontology", "pr"),
    "GO": ("Gene Ontology", "go"),
    "NCIT": ("NCI Thesaurus", "ncit"),
    "NCBI": ("NCBI Gene", None),
    "dbSNP": ("NCBI dbSNP", None),
    "HGNC": ("HGNC", None),
    "RNAC": ("RNAcentral", None),
    "MRB": ("miRBase", None),
    "GTC": ("GlyTouCan", None),
    "PCCID": ("PubChem Compound", None),
    "CHEBI": ("ChEBI", "chebi"),
    "CL": ("Cell Ontology", "cl"),
    "DOID": ("Disease Ontology", "doid"),
    "MONDO": ("MONDO", "mondo"),
    "SNOMED": ("SNOMED CT", None),
    "UBERON": ("UBERON", "uberon"),
}

# (sub)type -> CURIE prefixes in order of preference (fall back only when the
# preferred resource has no entry for the entity).
ACCESSION_RESOURCES: dict[str, tuple[str, ...]] = {
    "protein": ("UPKB", "PDB", "PR", "NCIT"),
    "peptide": ("PR",),
    "protein complex": ("PR", "GO"),
    "gene": ("NCBI",),
    "gene (mutation)": ("dbSNP",),
    "dna": ("NCIT",),
    "rna": ("HGNC", "RNAC"),
    "mirna": ("MRB",),
    "glycan": ("GTC", "PCCID"),
    "carbohydrate": ("CHEBI",),
    "metabolite": ("PCCID", "CHEBI"),
    "lipid": ("CHEBI",),
    "lipoprotein": ("CHEBI",),
    "element": ("PCCID", "NCIT"),
    "chemical element": ("PCCID", "NCIT"),
    "cell": ("CL", "NCIT"),
    "image": ("NCIT",),
    "condition": ("DOID", "MONDO", "NCIT", "SNOMED"),
}

# Ontologies permitted for BMKB ``condition.id``.
CONDITION_RESOURCES: tuple[str, ...] = ("DOID", "MONDO", "NCIT", "SNOMED")

_UNIPROT_ACC = re.compile(r"^(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})(?:-\d+)?$")


def normalise_type(entity_type: str) -> str:
    """Lowercase and trim; raise ValueError for a type outside the table."""
    t = (entity_type or "").strip().lower()
    if t not in ACCESSION_RESOURCES:
        raise ValueError(f"unknown entity type {entity_type!r}; expected one of "
                         f"{list(ENTITY_TYPES)} or a sub-type {sorted(SUBTYPES)}")
    return t


def record_type(entity_type: str) -> str:
    """The value to write in ``assessed_entity_type`` (sub-types map to their parent)."""
    t = normalise_type(entity_type)
    return SUBTYPES.get(t, t)


def accession_resources(entity_type: str) -> tuple[str, ...]:
    """All CURIE prefixes for *entity_type*, in order of preference."""
    return ACCESSION_RESOURCES[normalise_type(entity_type)]


def accession_resource_for(entity_type: str) -> str:
    """Preferred CURIE prefix for *entity_type*."""
    return accession_resources(entity_type)[0]


def ols_resources_for(entity_type: str) -> tuple[str, ...]:
    """The preferred-order prefixes the OLS MCP server can resolve for *entity_type*."""
    return tuple(p for p in accession_resources(entity_type) if RESOURCES[p][1])


def curie_from_ols(term_id: str) -> str:
    """Turn an OLS short form or IRI into this skill's CURIE.

    ``PR_P19429`` (a Protein Ontology term named by its UniProt accession)
    becomes ``UPKB:P19429``; any other ``PREFIX_LOCAL`` / ``PREFIX:LOCAL``
    becomes ``PREFIX:LOCAL`` with the prefix uppercased.
    """
    s = term_id.strip().rsplit("/", 1)[-1]
    m = re.match(r"^([A-Za-z]+)[_:](.+)$", s)
    if not m:
        raise ValueError(f"not an ontology term id: {term_id!r}")
    prefix, local = m.group(1).upper(), m.group(2)
    if prefix == "PR" and _UNIPROT_ACC.match(local):
        return f"UPKB:{local}"
    return f"{prefix}:{local}"


def _print_table() -> None:
    print("entity type -> CURIE prefix chain (preferred first); * = reachable via OLS\n")
    for t in ENTITY_TYPES + tuple(sorted(SUBTYPES)):
        chain = "  ->  ".join(p + ("*" if RESOURCES[p][1] else "") for p in ACCESSION_RESOURCES[t])
        label = t if t in ENTITY_TYPES else f"{t} (write as {SUBTYPES[t]})"
        print(f"  {label:<32} {chain}")
    print("\nLook up only through the OLS MCP server. A resource without * is not on OLS:")
    print("leave the accession PLACEHOLDER and list it in the hand-over report.")
    print("OLS PR_<UniProt accession> terms convert to UPKB:<accession> (curie_from_ols).")


def _self_test() -> int:
    errors = []

    def check(label: str, got, expected) -> None:
        if got != expected:
            errors.append(f"{label}: got {got!r}, expected {expected!r}")

    check("protein", accession_resource_for("protein"), "UPKB")
    check("case-insensitive DNA", accession_resource_for("DNA"), "NCIT")
    check("miRNA sub-type", accession_resource_for("miRNA"), "MRB")
    check("miRNA record type", record_type("miRNA"), "rna")
    check("glycan OLS chain", ols_resources_for("glycan"), ())
    check("protein OLS chain", ols_resources_for("protein"), ("UPKB", "PR", "NCIT"))
    check("PR -> UPKB", curie_from_ols("PR_P19429"), "UPKB:P19429")
    check("PR non-UniProt", curie_from_ols("PR_000004803"), "PR:000004803")
    check("GO", curie_from_ols("http://purl.obolibrary.org/obo/GO_0005861"), "GO:0005861")
    check("NCIt", curie_from_ols("NCIT_C16612"), "NCIT:C16612")
    for t in ENTITY_TYPES:
        if t not in ACCESSION_RESOURCES:
            errors.append(f"allowed type without a resource chain: {t}")
        if t != t.lower():
            errors.append(f"entity type not lowercase: {t}")
    for t, parent in SUBTYPES.items():
        if parent not in ENTITY_TYPES:
            errors.append(f"sub-type {t} maps to a disallowed type {parent}")
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
    print("[SELF-TEST] PASSED — lowercase types, every type has a chain, sub-types, OLS CURIEs")
    return 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    _print_table()
