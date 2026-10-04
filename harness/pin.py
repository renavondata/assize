"""Pin and mutant declarations, and registry validation."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from harness import mutants

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Mutant:
    """A seeded fault. `env`: a code path selected by the flag `<pin>/<name>`.
    `patch`: a committed diff (path relative to the repository root) applied to
    a temporary copy of the repository; the checked code is never edited in place."""

    name: str
    selector: Literal["env", "patch"] = "env"
    patch: str | None = None


@dataclass(frozen=True)
class Pin:
    name: str
    protects: str
    check: Callable[[], bool]
    mutants: tuple[Mutant, ...]

    def flag(self, mutant: Mutant) -> str:
        return f"{self.name}/{mutant.name}"


class RegistryError(Exception):
    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def validate(pins: Sequence[Pin]) -> None:
    """Refuse a registry with a pin lacking mutants, a duplicated pin or mutant
    name, or a malformed mutant selector."""
    if mutants.active("P0e/validation_off"):
        return
    dup_pins = sorted(n for n, c in Counter(p.name for p in pins).items() if c > 1)
    if dup_pins:
        raise RegistryError("duplicate_pin", ", ".join(dup_pins))
    bare = [p.name for p in pins if not p.mutants]
    if bare:
        raise RegistryError("no_mutants", ", ".join(bare))
    flags = Counter(p.flag(m) for p in pins for m in p.mutants)
    dup_mutants = sorted(f for f, c in flags.items() if c > 1)
    if dup_mutants:
        raise RegistryError("duplicate_mutant", ", ".join(dup_mutants))
    for p in pins:
        for m in p.mutants:
            if m.selector == "env" and m.patch is not None:
                raise RegistryError("bad_selector", f"{p.flag(m)}: env mutant carries a patch")
            if m.selector == "patch" and (m.patch is None or not (ROOT / m.patch).is_file()):
                raise RegistryError("bad_selector", f"{p.flag(m)}: patch file missing: {m.patch}")
            if m.selector not in ("env", "patch"):
                raise RegistryError("bad_selector", f"{p.flag(m)}: unknown selector {m.selector!r}")
