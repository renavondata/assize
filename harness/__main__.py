"""CLI: `python -m harness run ...` (orchestrator) and `python -m harness check ...` (child)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from harness import runner
from harness.registries import REGISTRIES


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m harness")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run every pin clean and under each of its mutants")
    r.add_argument("--registry", default="harness", choices=sorted(REGISTRIES))
    r.add_argument("--phase", default="all", choices=["all", "clean", "mutants"])
    r.add_argument("--out", type=Path, default=Path("out/pins"))
    r.add_argument("--config", type=Path, default=None)
    c = sub.add_parser("check", help="child: run one pin's check once")
    c.add_argument("--registry", required=True, choices=sorted(REGISTRIES))
    c.add_argument("--pin", required=True)
    g = c.add_mutually_exclusive_group(required=True)
    g.add_argument("--clean", action="store_true")
    g.add_argument("--mutant")
    a = ap.parse_args(argv)
    if a.cmd == "run":
        return runner.run(a.registry, a.phase, a.out, a.config)
    return runner.check(a.registry, a.pin, a.mutant, a.clean)


if __name__ == "__main__":
    sys.exit(main())
