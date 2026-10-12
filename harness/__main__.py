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
    r = sub.add_parser("run", help="run every pin clean, and each mutant with its causal twin")
    r.add_argument("--registry", default="harness", choices=sorted(REGISTRIES))
    r.add_argument("--phase", default="all", choices=["all", "clean", "mutants"])
    r.add_argument("--out", type=Path, default=Path("out/pins"))
    r.add_argument("--config", type=Path, default=None)
    r.add_argument("--scratch-root", type=Path, default=None,
                   help="directory under which each child run's scratch root is created (default: system temp)")
    r.add_argument("--under-edits", metavar="FILE", default=None,
                   help="run the suite in a disposable copy carrying this unregistered mutant file")
    r.add_argument("--since", metavar="SHA", default=None,
                   help="run only the pins witnessing a path changed since this green head; record the rest skipped")
    r.add_argument("--since-run", metavar="ID", type=int, default=None, help="the pins run id of --since, recorded")
    r.add_argument("--repo", type=Path, default=None, help="the repository --since is read in (default: this tree)")
    b = sub.add_parser("base", help="print `--since <sha> --since-run <id>` for the newest usable green base, or nothing")
    b.add_argument("--master", default="origin/master", help="the ref a layer boundary is read against")
    c = sub.add_parser("check", help="child: run one pin's check once")
    c.add_argument("--registry", required=True, choices=sorted(REGISTRIES))
    c.add_argument("--pin", required=True)
    c.add_argument("--role", required=True, choices=["clean", "mutant", "twin"])
    c.add_argument("--invocation-root", type=Path, required=True)
    c.add_argument("--run-dir", type=Path, required=True)
    c.add_argument("--scratch", type=Path, required=True)
    a = ap.parse_args(argv)
    if a.cmd == "run" and a.under_edits:
        return runner.run_under_edits(a.under_edits, a.registry, a.phase, a.out, a.config)
    if a.cmd == "run" and (a.since is None) != (a.since_run is None):
        ap.error("--since and --since-run go together")
    if a.cmd == "run":
        return runner.run(a.registry, a.phase, a.out, a.config, a.scratch_root, a.since, a.since_run,
                          (a.repo or runner.ROOT).resolve())
    if a.cmd == "base":
        return runner.base(runner.ROOT, a.master)
    return runner.check(a.registry, a.pin, a.role, a.invocation_root, a.run_dir, a.scratch)


if __name__ == "__main__":
    sys.exit(main())
