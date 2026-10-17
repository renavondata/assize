"""fixture.envprobe (L2a obligation 29): a clean check that records the environment it was started with, and that of
the `harness run` orchestrating it.

`proc.child_env` is pinned by P0i at its output. This fixture lets a pin read the environment at the spawn sites: the
check's own `os.environ` shows what `runner._spawn` handed it, and its parent's `/proc/<pid>/environ` shows what the
caller of `harness run` (`nested.run_nested`, `runner.run_under_edits`) handed the orchestrator.
"""

from __future__ import annotations

import json
import os

from harness import context
from harness.fixtures.toy import OFF_BY_ONE
from harness.pin import ALWAYS, ROOT, Pin

RECORD = "env.json"
KEYS = ("PYTHONDONTWRITEBYTECODE", "PYTHONPYCACHEPREFIX")


def _parent_environ() -> dict[str, str]:
    raw = open(f"/proc/{os.getppid()}/environ", "rb").read().split(b"\0")
    pairs = (item.decode().partition("=") for item in raw if item)
    return {k: v for k, _, v in pairs}


def check_envprobe() -> bool:
    parent = _parent_environ()
    (context.run_dir / RECORD).write_text(json.dumps({
        "own": {k: os.environ.get(k) for k in KEYS},
        "parent": {k: parent.get(k) for k in KEYS},
        "scratch": str(context.scratch),
        "root_parent": str(ROOT.parent),
    }, sort_keys=True))
    return True


PINS = [Pin("fixture/envprobe", "records its own environment and its orchestrator's (seeded defect)",
            check_envprobe, (OFF_BY_ONE,), ALWAYS)]
