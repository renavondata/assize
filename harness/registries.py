"""Named pin registries. Loading a registry validates it."""

from __future__ import annotations

import importlib
import subprocess
import tomllib
from pathlib import Path

from harness.pin import Pin, RegistryError, validate

REGISTRIES = {
    "harness": "harness.pins",
    "fixture.basic": "harness.fixtures.basic",
    "fixture.broken": "harness.fixtures.broken",
    "fixture.inconclusive": "harness.fixtures.inconclusive",
    "fixture.noncausal": "harness.fixtures.noncausal",
    "fixture.envprobe": "harness.fixtures.envprobe",
    "fixture.orphaner":"harness.fixtures.orphaner",
    "fixture.stale": "harness.fixtures.stale",
    "fixture.leaks": "harness.fixtures.leaks",
    "fixture.escapee": "harness.fixtures.escapee",
    "fixture.daemon": "harness.fixtures.daemon",
    "fixture.litter": "harness.fixtures.litter",
    "fixture.podman_pause": "harness.fixtures.podman_pause",
    "fixture.no_mutants": "harness.fixtures.no_mutants",
    "fixture.dup_pin": "harness.fixtures.dup_pin",
    "fixture.dup_mutant": "harness.fixtures.dup_mutant",
    "fixture.malformed_edit": "harness.fixtures.malformed_edit",
    "fixture.witness": "harness.fixtures.witness",
    "fixture.stamp": "harness.fixtures.stamp",
}


def load(name: str) -> list[Pin]:
    pins = list(importlib.import_module(REGISTRIES[name]).PINS)
    validate(pins)
    return pins


PROPOSER_KEYS = ("kind", "model", "session")


def _proposer_file(path: Path) -> dict:
    with path.open("rb") as f:
        data = tomllib.load(f)
    return {k: data[k] for k in PROPOSER_KEYS}


def proposer_files(root: Path) -> list[Path]:
    """The frozen `harness/proposer.toml`, then every file of `harness/proposer.d/`: each pull request writes its own
    (instruction #135)."""
    return [p for p in [root / "harness" / "proposer.toml", *sorted((root / "harness" / "proposer.d").glob("*.toml"))]
            if p.is_file()]


def proposers(root: Path) -> dict[str, dict]:
    """Every proposer row, by session id. A session appearing in two files is a registry error, not an override."""
    rows = [(p, _proposer_file(p)) for p in proposer_files(root)]
    twice = sorted({r["session"] for _, r in rows if sum(s["session"] == r["session"] for _, s in rows) > 1})
    if twice:
        raise RegistryError("proposer_keyed_twice", ", ".join(twice))
    return {r["session"]: r for _, r in rows}


def proposer(root: Path) -> dict:
    """Who built the harness state: the row of the proposer file the newest commit touching them wrote, else (no git,
    or none touched) the last file in path order."""
    files = proposer_files(root)
    proposers(root)  # a duplicate is an error whichever row is chosen
    touched = subprocess.run(["git", "-C", str(root), "log", "-1", "--name-only", "--format=", "--",
                              "harness/proposer.toml", "harness/proposer.d"], capture_output=True, text=True)
    named = {root / line for line in touched.stdout.split()} if touched.returncode == 0 else set()
    return _proposer_file(next((p for p in reversed(files) if p in named), files[-1]))
