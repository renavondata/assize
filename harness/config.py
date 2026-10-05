"""Committed harness configuration."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from harness.pin import ROOT

DEFAULT = ROOT / "harness" / "config.toml"


@dataclass(frozen=True)
class Config:
    path: Path
    child_timeout_s: float
    reap_grace_s: float


def _read(path: Path) -> dict:
    with path.open("rb") as f:
        return tomllib.load(f)["harness"]


def load(path: Path | None = None) -> Config:
    """`child_timeout_s` comes from `path`; `reap_grace_s` from `path` if set there, else from the default config."""
    path = (path or DEFAULT).resolve()
    data = _read(path)
    grace = data.get("reap_grace_s", _read(DEFAULT)["reap_grace_s"])
    return Config(path=path, child_timeout_s=float(data["child_timeout_s"]), reap_grace_s=float(grace))
