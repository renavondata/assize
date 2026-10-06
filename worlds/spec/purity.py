"""Schema purity (brief 1 section 1; P6): no manifest vocabulary token appears in an interface schema file.

A token is a lower-cased run of letters, digits and underscores, together with its underscore-separated parts,
so `wood_pickaxe` also yields `wood` and `pickaxe`. Schema tokens come from every key and every string value,
descriptions included; manifest vocabulary comes from every name the manifest declares, never its prose.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path

SPEC = Path(__file__).resolve().parent
WORLDS = SPEC.parent
WORD = re.compile(r"[A-Za-z0-9_]+")


def schema_files(spec: Path = SPEC) -> list[Path]:
    return sorted(spec.glob("*.schema.json"))


def manifest_files(worlds: Path = WORLDS) -> list[Path]:
    return sorted(worlds.glob("*/manifest.json"))


def tokens(text: str) -> frozenset[str]:
    words = [w.lower() for w in WORD.findall(text)]
    return frozenset(words) | frozenset(p for w in words for p in w.split("_") if p)


def _strings(node: object) -> Iterator[str]:
    """Every key and every string value in a JSON document."""
    if isinstance(node, Mapping):
        for k, v in node.items():
            yield k
            yield from _strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from _strings(v)
    elif isinstance(node, str):
        yield node


def schema_tokens(schema: object) -> frozenset[str]:
    return frozenset().union(*map(tokens, _strings(schema)))


def _names(manifest: Mapping) -> Iterator[str]:
    """Every name a manifest declares: the World, observation fields and their vocabularies, actions,
    targets and their string support, and utility components. Rationales and descriptions are prose."""
    yield manifest["world"]
    for f in manifest["observation"]:
        yield f["name"]
        yield from f.get("vocabulary", ())
    yield from manifest["actions"]
    for t in manifest["targets"]:
        yield t["name"]
        yield t["field"]
        yield from (s for s in t["support"] if isinstance(s, str))
    yield from manifest["utility"]["components"]


def vocabulary(manifests: Iterable[Mapping]) -> frozenset[str]:
    return frozenset().union(*(tokens(n) for m in manifests for n in _names(m)))


def violations(schemas: Mapping[str, object], vocab: frozenset[str]) -> list[tuple[str, str]]:
    """(schema name, token) for every manifest vocabulary token found in a schema."""
    return sorted((name, tok) for name, schema in schemas.items() for tok in schema_tokens(schema) & vocab)


def load(paths: Iterable[Path]) -> dict[str, object]:
    return {p.name if p.parent == SPEC else f"{p.parent.name}/{p.name}": json.loads(p.read_text()) for p in paths}
