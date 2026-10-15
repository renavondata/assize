"""Review of PR #204: run P29 and P3 (the pins this PR adds or edits) through the same `runner.run` path as `make pins`,
the registry filtered to those two. Usage: uv run --frozen python /tmp/rv204-driver/p29-driver.py OUT"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
import harness.pins as pins  # noqa: E402
from harness import runner  # noqa: E402

pins.PINS = [p for p in pins.PINS if p.name in {"P29", "P3"}]
sys.exit(runner.run("harness", "all", Path(sys.argv[1]), None))
