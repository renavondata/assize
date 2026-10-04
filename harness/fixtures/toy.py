"""Toy code under test, and the toy pin's check."""

from __future__ import annotations

import time

from harness import mutants
from harness.pin import Mutant, Pin


def add(a: int, b: int) -> int:
    if mutants.active("fixture/toy/off_by_one"):
        return a + b + 1
    return a + b


def check_toy() -> bool:
    if mutants.active("fixture/toy/raises"):
        raise RuntimeError("seeded mutant fixture/toy/raises")
    if mutants.active("fixture/toy/hangs"):
        while True:
            time.sleep(1)
    return add(2, 2) == 4


OFF_BY_ONE = Mutant("off_by_one")
OFF_BY_ONE_PATCH = Mutant("off_by_one_patch", selector="patch",
                          patch="harness/fixtures/patches/toy_off_by_one.diff")
RAISES = Mutant("raises")
HANGS = Mutant("hangs")


def toy_pin(*mutant_set: Mutant) -> Pin:
    return Pin("fixture/toy", "toy addition is correct", check_toy, tuple(mutant_set))
