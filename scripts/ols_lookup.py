#!/usr/bin/env python3
"""ols_lookup.py — look up ontology terms through the EBI OLS4 API.

Accessions come from the OLS web API.
Adapted from https://github.com/cyruschay/ontology_mapper
lexical search with isDefiningOntology=true, CURIEs from ``short_form``,
retries on OLS's intermittent 5xx). Standard library only.

Usage
-----
    # search every OLS-reachable resource for an entity type, best match first
    python scripts/ols_lookup.py search "troponin I, cardiac muscle" --type protein --species human
    # search one ontology
    python scripts/ols_lookup.py search "acute myocardial infarction" --ontology doid
    # verify a CURIE before using it (label, synonyms, obsolete flag)
    python scripts/ols_lookup.py get DOID:9408
    python scripts/ols_lookup.py --self-test

Results print as CURIEs in this skill's style (PR_P19429 -> UPKB:P19429). Pick the
candidate whose label matches the document's entity, check it with ``get``, and
leave the field PLACEHOLDER when nothing matches. Never take the top hit blindly:
a search for "troponin I cardiac" ranks troponin T first.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from biomarker_accessions import RESOURCES, curie_from_ols, ols_resources_for  # noqa: E402

BASE = "https://www.ebi.ac.uk/ols4/api"
TIMEOUT = 45            # a cold OLS query can take a long time before succeeding
RETRIES = 3
FIELDS = "iri,label,short_form,obo_id,synonym,description,ontology_name,is_obsolete"


class OlsError(RuntimeError):
    """Transport or protocol failure after retries."""


def _get(path: str, params: dict) -> dict:
    url = f"{BASE}/{path}?{urllib.parse.urlencode(params)}"
    last: Exception | None = None
    for attempt in range(RETRIES):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json",
                                                       "User-Agent": "biomarker-sdtm-skill"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last = e
            if e.code not in (429, 500, 502, 503, 504):
                break
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            last = e
        time.sleep(1.5 * (attempt + 1))
    raise OlsError(f"OLS request failed ({path}): {last}")


def _text(value):
    """OLS returns some text fields as lists or reification objects."""
    if isinstance(value, list):
        return _text(value[0]) if value else None
    if isinstance(value, dict):
        return value.get("value")
    return value


def _candidate(doc: dict, ontology: str) -> dict:
    short = doc.get("short_form") or ""
    raw = doc.get("obo_id") or short       # PR terms come back with an empty obo_id
    return {
        "curie": curie_from_ols(raw) if raw else "",
        "label": _text(doc.get("label")) or "",
        "synonyms": doc.get("synonym") or [],
        "definition": _text(doc.get("description")),
        "ontology": doc.get("ontology_name", ontology),
        "obsolete": bool(doc.get("is_obsolete")),
        "iri": doc.get("iri", ""),
    }


def parse_search(data: dict, ontology: str) -> list[dict]:
    out = []
    for doc in (data.get("response") or {}).get("docs", []):
        short = doc.get("short_form") or ""
        # Defence in depth: isDefiningOntology should already drop imported classes.
        if short and not short.lower().startswith(ontology.lower()):
            continue
        out.append(_candidate(doc, ontology))
    return out


def search(term: str, ontology: str, rows: int = 10) -> list[dict]:
    data = _get("search", {"q": term, "ontology": ontology, "isDefiningOntology": "true",
                           "rows": rows, "fieldList": FIELDS})
    return parse_search(data, ontology)


def _norm(s: str) -> str:
    return re.sub(r"\s*\([^)]*\)\s*$", "", s or "").strip().lower()


def rank(candidates: list[dict], term: str, species: str | None = None,
         prefixes: tuple[str, ...] = ()) -> list[dict]:
    """Order candidates: not obsolete; exact label (ignoring a trailing '(species)'),
    then synonym match; the entity type's preferred resource; the requested species;
    then OLS order. Duplicate CURIEs are dropped."""
    t = _norm(term)
    order = {p: i for i, p in enumerate(prefixes)}

    def key(ic):
        i, c = ic
        label_hit = _norm(c["label"]) == t
        syn_hit = any(_norm(s) == t for s in c["synonyms"])
        sp_hit = bool(species) and f"({species.lower()})" in c["label"].lower()
        res = order.get(c["curie"].split(":")[0], len(order))
        return (c["obsolete"], not (label_hit or syn_hit), res, not sp_hit if species else False, i)
    seen, out = set(), []
    for _, c in sorted(enumerate(candidates), key=key):
        if c["curie"] not in seen:
            seen.add(c["curie"])
            out.append(c)
    return out


def get(curie: str) -> dict:
    """The current OLS record for a CURIE (UPKB:x is looked up as PR:x)."""
    prefix, local = curie.split(":", 1)
    ontology_prefix = "PR" if prefix.upper() == "UPKB" else prefix.upper()
    ontology = RESOURCES.get(ontology_prefix, (None, ontology_prefix.lower()))[1] or ontology_prefix.lower()
    obo = f"{ontology_prefix}:{local}"
    terms = []
    for params in ({"obo_id": obo}, {"short_form": f"{ontology_prefix}_{local}"},
                   {"iri": f"http://purl.obolibrary.org/obo/{ontology_prefix}_{local}"}):
        try:
            terms = (_get(f"ontologies/{ontology}/terms", params).get("_embedded") or {}).get("terms", [])
        except OlsError:
            terms = []
        if terms:
            break
    if not terms:
        raise OlsError(f"{curie} not found in OLS ontology {ontology}")
    t = terms[0]
    return {"curie": curie, "label": t.get("label", ""), "synonyms": t.get("synonyms") or [],
            "obsolete": bool(t.get("is_obsolete")), "ontology": ontology,
            "definition": _text(t.get("description"))}


# ---------------------------------------------------------------------------
# Self-test (offline: canned OLS responses)
# ---------------------------------------------------------------------------

def _self_test() -> int:
    errors = []
    canned = {"response": {"docs": [
        {"short_form": "PR_P45379", "obo_id": "", "label": "troponin T, cardiac muscle (human)", "synonym": ["TNNT2"]},
        {"short_form": "PR_P19429", "obo_id": "", "label": "troponin I, cardiac muscle (human)", "synonym": ["TNNI3"]},
        {"short_form": "PR_P48787", "obo_id": "", "label": "troponin I, cardiac muscle (mouse)", "synonym": []},
        {"short_form": "GO_0005861", "obo_id": "GO:0005861", "label": "troponin complex"},  # imported
    ]}}
    cands = parse_search(canned, "pr")
    if any(c["curie"].startswith("GO:") for c in cands):
        errors.append("imported class not filtered out")
    ranked = rank(cands, "troponin I, cardiac muscle", species="human", prefixes=("UPKB", "PR", "NCIT"))
    if ranked[0]["curie"] != "UPKB:P19429":
        errors.append(f"ranking put {ranked[0]['curie']} first, expected UPKB:P19429")
    if [c["curie"] for c in ranked[:2]] != ["UPKB:P19429", "PR:P48787".replace("PR:", "UPKB:")]:
        errors.append(f"species ordering wrong: {[c['curie'] for c in ranked]}")
    doid = parse_search({"response": {"docs": [
        {"short_form": "DOID_9408", "obo_id": "DOID:9408", "label": "acute myocardial infarction"},
        {"short_form": "DOID_5844", "obo_id": "DOID:5844", "label": "myocardial infarction"}]}}, "doid")
    if rank(doid, "acute myocardial infarction")[0]["curie"] != "DOID:9408":
        errors.append("exact-label ranking failed for DOID")
    if "--live" in sys.argv:
        try:
            live = rank(search("troponin I, cardiac muscle (human)", "pr", 5), "troponin I, cardiac muscle", "human")
            if live[0]["curie"] != "UPKB:P19429":
                errors.append(f"live: got {live[0]['curie']}")
            if get("DOID:9408")["label"] != "acute myocardial infarction":
                errors.append("live: DOID:9408 label mismatch")
        except OlsError as e:
            errors.append(f"live OLS call failed: {e}")
    if errors:
        print("[SELF-TEST] FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("[SELF-TEST] PASSED — parsing, imported-class filter, PR->UPKB, ranking"
          + (" + live OLS" if "--live" in sys.argv else " (offline; add --live to hit OLS)"))
    return 0


def main() -> int:
    if "--self-test" in sys.argv:
        return _self_test()
    p = argparse.ArgumentParser(description="Look up ontology terms through the OLS4 API.")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search")
    s.add_argument("term")
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--type", help="entity type: searches its OLS-reachable resources in order")
    g.add_argument("--ontology", help="one OLS ontology id, e.g. doid, mondo, ncit, uberon, chebi, cl")
    s.add_argument("--species", help="prefer labels ending '(<species>)', e.g. human")
    s.add_argument("--rows", type=int, default=10)
    s.add_argument("--json", action="store_true")
    v = sub.add_parser("get")
    v.add_argument("curie")
    a = p.parse_args()
    try:
        if a.cmd == "get":
            print(json.dumps(get(a.curie), indent=2))
            return 0
        prefixes: tuple[str, ...] = ()
        if a.type:
            prefixes = ols_resources_for(a.type)
            ontologies = list(dict.fromkeys(RESOURCES[px][1] for px in prefixes))
            if not ontologies:
                print(f"[NONE] no resource for '{a.type}' is on OLS: leave the id PLACEHOLDER and report it")
                return 2
        else:
            ontologies = [a.ontology.lower()]
        queries = [a.term] + ([f"{a.term} ({a.species})"] if a.species else [])
        results = []
        for o in ontologies:
            for q in queries:
                results += search(q, o, a.rows)
        results = rank(results, a.term, a.species, prefixes)
    except (OlsError, ValueError, KeyError) as e:
        print(f"[ERROR] {e}. Tell the user OLS is unreachable; leave the id PLACEHOLDER.")
        return 1
    if a.json:
        print(json.dumps(results, indent=2))
    elif not results:
        print("[NONE] no match: leave the id PLACEHOLDER and report it")
        return 2
    else:
        for c in results:
            flag = " (OBSOLETE)" if c["obsolete"] else ""
            print(f"{c['curie']:<18} {c['label']}{flag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
