"""`python -m harness.selfrun` (instruction #113 Part A): the session workflows run against the harness they will meet.

For each step of `build.yml` and `review.yml` whose script calls `python -m harness...`, run that command from this
checkout with `--dry-run` appended: the election and the ledger compute and print, no session is launched and nothing
is written, fetched or pushed. A flag the workflow passes and the harness does not accept, a procedure it elects that the
harness does not know, or a workflow whose calls cannot be evaluated here, fails with a nonzero exit; so does a workflow
with no such call, which would make the run vacuous. `pins` runs this on a pull request's head, so the pair a merge
leaves on master agrees. Nothing in this module launches a session: it has no mode other than the dry run."""

from __future__ import annotations

import argparse
import re
import shlex
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from harness.ledger import PROCEDURES
from harness.pin import ROOT

WORKFLOWS = ("build.yml", "review.yml")
CALL = re.compile(r"python -m (harness[\w.]*)\s+([^)\n]*)")
EXPRESSION = re.compile(r"\$\{\{\s*(.*?)\s*\}\}")
RUN_ID = "1"  # the value a dry run gives `github.run_id`: the election needs a seed, and the seed is not under test
PROCEDURE_VARIABLE = re.compile(r'"?\$(?:\{proc\}|proc\b)"?')


class Unevaluable(Exception):
    """A call whose arguments the dry run cannot reproduce here."""


def calls(text: str) -> list[tuple[str, str]]:
    """(module, arguments) of every `python -m harness...` call in the workflow's non-comment lines."""
    return [(m.group(1), m.group(2).strip()) for line in text.splitlines() if not line.lstrip().startswith("#")
            for m in CALL.finditer(line)]


def argvs(args: str, procedures: Sequence[str]) -> list[list[str]]:
    """The argument vectors a call stands for: `${{ github.run_id }}` is `RUN_ID`, the loop variable `$proc` takes each
    procedure the harness knows; any other expression or shell variable raises Unevaluable."""
    def expression(m: re.Match) -> str:
        if m.group(1) != "github.run_id":
            raise Unevaluable(f"expression ${{{{ {m.group(1)} }}}}")
        return RUN_ID

    text = EXPRESSION.sub(expression, args)
    texts = [PROCEDURE_VARIABLE.sub(p, text) for p in procedures] if PROCEDURE_VARIABLE.search(text) else [text]
    for t in texts:
        if "$" in t:
            raise Unevaluable(f"shell variable in {t!r}")
    return [shlex.split(t) for t in texts]


def run(workflows: Path, root: Path) -> int:
    failures = 0
    for name in WORKFLOWS:
        path = workflows / name
        found = calls(path.read_text()) if path.is_file() else []
        if not found:
            print(f"selfrun: FAIL {name}: no step calls harness (or the file is missing); a dry run of nothing witnesses nothing")
            failures += 1
        for module, args in found:
            try:
                vectors = argvs(args, sorted(PROCEDURES))
            except Unevaluable as e:
                print(f"selfrun: FAIL {name}: python -m {module} {args}: cannot evaluate: {e}")
                failures += 1
                continue
            for vector in vectors:
                command = [sys.executable, "-B", "-m", module, *vector, "--dry-run"]
                done = subprocess.run(command, cwd=root, capture_output=True, text=True)
                print(f"selfrun: {'ok  ' if done.returncode == 0 else 'FAIL'} {name}: python -m {module} "
                      f"{shlex.join([*vector, '--dry-run'])} -> exit {done.returncode}")
                if done.returncode != 0:
                    failures += 1
                    print("\n".join(f"    {line}" for line in done.stderr.strip().splitlines()[-5:]))
    print(f"selfrun: {failures} failures")
    return 1 if failures else 0


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m harness.selfrun", description=__doc__.splitlines()[0])
    ap.add_argument("--workflows", type=Path, default=ROOT / ".github" / "workflows")
    ap.add_argument("--root", type=Path, default=ROOT, help="the checkout the commands run from")
    a = ap.parse_args(argv)
    return run(a.workflows, a.root)


if __name__ == "__main__":
    sys.exit(main())
