"""Pin and mutant declarations, and registry validation."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Mutant:
    """A seeded fault: a committed file of anchored edits (path relative to the repository root),
    applied only to a disposable copy of the tree (brief 0 A2)."""

    name: str
    edits: str


# A pin witnessing every path: it runs whatever changed (instruction #108 item 1).
ALWAYS = ("**",)


@dataclass(frozen=True)
class Pin:
    """`witnesses`: glob patterns (`**` any run of path segments, `*` and `?` within one) of the repository paths its
    check or its mutants read; a pins run `--since` a green head runs the pin only if a changed path matches one."""

    name: str
    protects: str
    check: Callable[[], bool]
    mutants: tuple[Mutant, ...]
    witnesses: tuple[str, ...]

    def label(self, mutant: Mutant) -> str:
        return f"{self.name}/{mutant.name}"


class RegistryError(Exception):
    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def validate(pins: Sequence[Pin]) -> None:
    """Refuse a registry with a pin lacking mutants or witnesses, a duplicated pin or mutant name,
    or a mutant file that is missing or malformed."""
    from harness import edits

    dup_pins = sorted(n for n, c in Counter(p.name for p in pins).items() if c > 1)
    if dup_pins:
        raise RegistryError("duplicate_pin", ", ".join(dup_pins))
    bare = [p.name for p in pins if not p.mutants]
    if bare:
        raise RegistryError("no_mutants", ", ".join(bare))
    blind = [p.name for p in pins if not p.witnesses]
    if blind:
        raise RegistryError("no_witnesses", ", ".join(blind))
    labels = Counter(p.label(m) for p in pins for m in p.mutants)
    dup_mutants = sorted(f for f, c in labels.items() if c > 1)
    if dup_mutants:
        raise RegistryError("duplicate_mutant", ", ".join(dup_mutants))
    for p in pins:
        for m in p.mutants:
            try:
                edits.load(m.edits)
            except edits.EditError as e:
                raise RegistryError("malformed_edit", f"{p.label(m)}: {e}") from e
