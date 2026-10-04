"""Probe for the harness's own pins: run a nested orchestrator and read its exported rows.

Assertions read `pins.jsonl` rows only, never stdout text. The nested run's
stdout is kept beside its rows as a transcript.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from harness import mutants
from harness.pin import ROOT


@dataclass
class Nested:
    label: str
    exit_code: int
    rows: list[dict]
    out: Path
    failures: list[str] = field(default_factory=list)

    def of(self, kind: str) -> list[dict]:
        return [r for r in self.rows if r.get("kind") == kind]

    @property
    def registry(self) -> dict:
        rows = self.of("registry")
        return rows[0] if len(rows) == 1 else {}

    @property
    def summary(self) -> dict:
        rows = self.of("summary")
        return rows[0] if len(rows) == 1 else {}

    def run(self, pin: str, mutant: str | None = None) -> dict:
        hits = [r for r in self.of("run") if r["pin"] == pin and r["mutant"] == mutant]
        return hits[0] if len(hits) == 1 else {}

    def expect(self, cond: bool, what: str) -> None:
        print(f"  [{'ok' if cond else 'FAIL'}] {self.label}: {what}")
        if not cond:
            self.failures.append(what)

    @property
    def ok(self) -> bool:
        return not self.failures


def run_nested(label: str, registry: str, phase: str, *extra_flags: str,
               config: Path | None = None) -> Nested:
    base = os.environ.get("ASSIZE_RUN_DIR") or tempfile.mkdtemp(prefix="assize-nested-")
    out = Path(base) / "nested" / label
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    env = mutants.with_mutants(os.environ, *extra_flags)
    env.pop("ASSIZE_RUN_DIR", None)
    cmd = [sys.executable, "-m", "harness", "run", "--registry", registry,
           "--phase", phase, "--out", str(out)]
    if config is not None:
        cmd += ["--config", str(config)]
    with (out / "stdout.log").open("w") as log:
        code = subprocess.run(cmd, env=env, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT).returncode
    rows_path = out / "pins.jsonl"
    rows = [json.loads(line) for line in rows_path.read_text().splitlines()] if rows_path.exists() else []
    print(f"nested {label}: registry={registry} phase={phase} "
          f"extra_flags={list(extra_flags) or '(none)'} exit={code} rows={rows_path}")
    n = Nested(label, code, rows, out)
    n.expect(n.summary.get("exit_code") == code, "summary row exit_code equals process exit code")
    return n
