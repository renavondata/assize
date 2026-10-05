"""Anchored edits: the only mutation mechanism (brief 0 A2).

A mutant is a committed TOML file of one or more `[[edit]]` tables, each with
`path`, `old` and `new`. At application time `old` must occur exactly once in
`path`; otherwise the run is STALE.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from harness.pin import ROOT


@dataclass(frozen=True)
class Edit:
    path: str
    old: str
    new: str


class EditError(Exception):
    """A mutant file is missing or malformed."""


class Stale(Exception):
    """An anchor does not occur exactly once."""


def load(rel: str, root: Path = ROOT) -> tuple[Edit, ...]:
    file = root / rel
    if not file.is_file():
        raise EditError(f"{rel}: file not found")
    try:
        data = tomllib.loads(file.read_text())
    except tomllib.TOMLDecodeError as e:
        raise EditError(f"{rel}: {e}") from e
    tables = data.get("edit")
    if not isinstance(tables, list) or not tables or set(data) != {"edit"}:
        raise EditError(f"{rel}: expected one or more [[edit]] tables and nothing else")
    return tuple(_edit(rel, i, t) for i, t in enumerate(tables))


def _edit(rel: str, i: int, table: object) -> Edit:
    where = f"{rel}: edit {i}"
    if not isinstance(table, dict) or set(table) != {"path", "old", "new"}:
        raise EditError(f"{where}: keys must be exactly path, old, new")
    if not all(isinstance(table[k], str) for k in ("path", "old", "new")):
        raise EditError(f"{where}: path, old and new must be strings")
    path = PurePosixPath(table["path"])
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise EditError(f"{where}: path must be relative and inside the tree")
    if not table["old"] or table["old"] == table["new"]:
        raise EditError(f"{where}: old must be non-empty and differ from new")
    return Edit(str(path), table["old"], table["new"])


def apply(tree: Path, edits: tuple[Edit, ...]) -> None:
    """Apply edits in order to `tree`. Raises Stale on the first anchor that does not occur exactly once."""
    for e in edits:
        target = tree / e.path
        text = target.read_text() if target.is_file() else ""
        count = text.count(e.old)
        if count != 1:
            raise Stale(f"{e.path}: anchor occurs {count} times")
        target.write_text(text.replace(e.old, e.new, 1))
