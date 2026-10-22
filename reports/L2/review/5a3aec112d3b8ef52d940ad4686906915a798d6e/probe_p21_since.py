"""Probe (review of PR #310): which pins `--since` selects when a pull request changes only the file P21 says records
the seal digest, or only the seal's own recipe. Usage: uv run --frozen python probe_p21_since.py <scratch clone>."""
import sys

sys.path.insert(0, sys.argv[1])
from harness import pins, runner  # noqa: E402

for changed in (["reports/L2/REPORT.md"], ["release/seal.toml"], ["harness/seal.py"]):
    run, _ = runner.select(pins.PINS, changed)
    print(f"changed {changed}: P21 runs = {'P21' in [p.name for p in run]}; pins run = {len(run)}")
