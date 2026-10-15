"""Reviewer driver: run only P10 through the same `runner.run` path `make pins` uses, in the scratch copy that is cwd.
The registry is loaded and validated whole, then filtered to P10 in this parent process; children look pins up by name."""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.getcwd())  # the scratch copy is cwd; its `harness` package is the one run, as `python -m` would

from harness import registries, runner  # noqa: E402

_load = registries.load


def only_p10(name: str):
    return [p for p in _load(name) if p.name == "P10"]


registries.load = only_p10
out = Path(sys.argv[1])
scratch = Path(sys.argv[2])
scratch.mkdir(parents=True, exist_ok=True)
sys.exit(runner.run("harness", "all", out, None, scratch))
