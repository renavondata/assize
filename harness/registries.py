"""Named pin registries. Loading a registry validates it."""

from __future__ import annotations

import importlib

from harness.pin import Pin, validate

REGISTRIES = {
    "harness": "harness.pins",
    "fixture.basic": "harness.fixtures.basic",
    "fixture.broken": "harness.fixtures.broken",
    "fixture.inconclusive": "harness.fixtures.inconclusive",
    "fixture.noncausal": "harness.fixtures.noncausal",
    "fixture.stale": "harness.fixtures.stale",
    "fixture.leaks": "harness.fixtures.leaks",
    "fixture.no_mutants": "harness.fixtures.no_mutants",
    "fixture.dup_pin": "harness.fixtures.dup_pin",
    "fixture.dup_mutant": "harness.fixtures.dup_mutant",
    "fixture.malformed_edit": "harness.fixtures.malformed_edit",
}


def load(name: str) -> list[Pin]:
    pins = list(importlib.import_module(REGISTRIES[name]).PINS)
    validate(pins)
    return pins
