"""Probe for the harness's own pins: run a nested orchestrator and read its exported rows.

Assertions read `pins.jsonl` rows only, never stdout text. The nested run's
stdout is kept beside its rows as a transcript. With `edits`, the nested
orchestrator runs in a disposable copy of this tree carrying those edits.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from harness import context, edits as edits_mod, proc
from harness.pin import ROOT
from harness.tree import disposable_copy


@dataclass
class Nested:
    label: str
    exit_code: int | None
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

    def runs(self, role: str) -> list[dict]:
        return [r for r in self.of("run") if r.get("role") == role]

    def run(self, pin: str, mutant: str | None = None, role: str = "clean") -> dict:
        hits = [r for r in self.of("run") if r["pin"] == pin and r["mutant"] == mutant and r["role"] == role]
        return hits[0] if len(hits) == 1 else {}

    def expect(self, cond: bool, what: str) -> None:
        print(f"  [{'ok' if cond else 'FAIL'}] {self.label}: {what}")
        if not cond:
            self.failures.append(what)

    @property
    def ok(self) -> bool:
        return not self.failures


def run_nested(label: str, registry: str, phase: str, *,
               edits: str | None = None, config: Path | None = None, extra: tuple[str, ...] = (),
               prepare: Callable[[Path], None] | None = None) -> Nested:
    """With `edits` or `prepare`, the nested orchestrator runs in a disposable copy: the edits are applied, then
    `prepare(copy)` is called."""
    base = context.run_dir or Path(tempfile.mkdtemp(prefix="assize-nested-"))
    out = base / "nested" / label
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    cmd = proc.python("-m", "harness", "run", "--registry", registry, "--phase", phase, "--out", str(out), *extra)
    if config is not None:
        cmd += ["--config", str(config)]
    if context.scratch is not None:
        cmd += ["--scratch-root", str(context.scratch)]
    stale = None
    with (out / "stdout.log").open("w") as log:
        if edits is None and prepare is None:
            code = subprocess.run(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, preexec_fn=proc.setup(False),
                                  env=proc.child_env()).returncode
        else:
            with disposable_copy(ROOT) as copy:
                try:
                    if edits is not None:
                        edits_mod.apply(copy, edits_mod.load(edits))
                    if prepare is not None:
                        prepare(copy)
                    log.write(f"nested run in copy {copy} carrying {edits or '(no edits)'}"
                              f"{', prepared' if prepare else ''}\n")
                    log.flush()
                    code = subprocess.run(cmd, cwd=copy, stdout=log, stderr=subprocess.STDOUT, preexec_fn=proc.setup(False),
                                  env=proc.child_env()).returncode
                except edits_mod.Stale as e:
                    stale, code = str(e), None
    rows_path = out / "pins.jsonl"
    rows = [json.loads(line) for line in rows_path.read_text().splitlines()] if rows_path.exists() else []
    print(f"nested {label}: registry={registry} phase={phase} edits={edits or '(none)'} "
          f"exit={code} rows={rows_path}")
    n = Nested(label, code, rows, out)
    n.expect(stale is None, f"seeded edits applied ({stale or 'anchors unique'})")
    n.expect(n.summary.get("exit_code") == code, "summary row exit_code equals process exit code")
    return n
