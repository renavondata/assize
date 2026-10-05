"""Per-child context, passed by the orchestrator on the command line (never via the environment)."""

from __future__ import annotations

from pathlib import Path

# Tree from which the orchestrator that spawned this child was invoked.
invocation_root: Path | None = None
# Directory where this child's transcript lives; nested runs write beneath it.
run_dir: Path | None = None
