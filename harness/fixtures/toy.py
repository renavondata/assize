"""Toy code under test, and the toy pin's check."""

from __future__ import annotations

from harness.pin import Mutant, Pin


def add(a: int, b: int) -> int:
    return a + b


def check_toy() -> bool:
    return add(2, 2) == 4


def _edits(name: str) -> str:
    return f"harness/fixtures/edits/{name}.toml"


OFF_BY_ONE = Mutant("off_by_one", _edits("toy_off_by_one"))
INVERTED = Mutant("inverted", _edits("toy_inverted"))
RAISES = Mutant("raises", _edits("toy_raises"))
HANGS = Mutant("hangs", _edits("toy_hangs"))
ABSENT = Mutant("absent", _edits("stale_absent"))
TWICE = Mutant("twice", _edits("stale_twice"))
MALFORMED = Mutant("malformed", _edits("malformed"))
LEAKS_AND_HANGS = Mutant("leaks_and_hangs", _edits("toy_leaks_and_hangs"))


def toy_pin(*mutant_set: Mutant) -> Pin:
    return Pin("fixture/toy", "toy addition is correct", check_toy, tuple(mutant_set))
