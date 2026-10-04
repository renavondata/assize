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


def load(path: Path | None = None) -> Config:
    path = (path or DEFAULT).resolve()
    with path.open("rb") as f:
        data = tomllib.load(f)["harness"]
    return Config(path=path, child_timeout_s=float(data["child_timeout_s"]))
