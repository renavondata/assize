"""Orchestrator (`run`) and child check runner (`check`).

Every check runs in its own child process. Clean runs execute in the
invocation tree, which never executes mutated code. Each mutant runs in a
disposable copy carrying its anchored edits, paired with a causal twin: a fresh
copy with no edits. A mutant is KILLED only if it fails and its twin passes.
Results are exported as JSONL rows; each child's transcript is kept beside
them. Nothing is dropped: STALE, NON-CAUSAL and INCONCLUSIVE runs are counted
in the denominator and fail the suite.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import tomllib
import traceback
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path

from harness import config as config_mod
from harness import context, edits, proc, registries
from harness.pin import ROOT, Mutant, Pin, RegistryError
from harness.tree import disposable_copy

EXIT_PASS, EXIT_FAIL, EXIT_ERROR = 0, 1, 2
EXIT_REFUSED = 4
OBSERVED = {EXIT_PASS: "pass", EXIT_FAIL: "fail"}


# --------------------------------------------------------------------- child


def check(registry: str, pin_name: str, role: str, invocation_root: Path, run_dir: Path, scratch: Path) -> int:
    context.invocation_root = invocation_root.resolve()
    context.run_dir = run_dir.resolve()
    context.scratch = scratch.resolve()
    try:
        pin = {p.name: p for p in registries.load(registry)}[pin_name]
    except Exception:
        traceback.print_exc()
        return EXIT_ERROR
    print(f"pin:       {pin.name}")
    print(f"protects:  {pin.protects}")
    print(f"role:      {role}")
    print(f"tree:      {ROOT}")
    print(f"invoked:   {context.invocation_root}")
    print(f"scratch:   {context.scratch}")
    sys.stdout.flush()
    try:
        ok = bool(pin.check())
    except Exception:
        traceback.print_exc()
        print("result:    ERROR (check raised)")
        return EXIT_ERROR
    print(f"result:    {'PASS' if ok else 'FAIL'}")
    return EXIT_PASS if ok else EXIT_FAIL


# -------------------------------------------------------------- orchestrator


def _slug(s: str) -> str:
    return s.replace("/", "__")


class Overlap(RuntimeError):
    """A child was about to start while a descendant of an earlier one was still alive."""


def _spawn(cmd: list[str], cwd: Path, scratch: Path, timeout: float, log) -> tuple[str, int | None]:
    # Children run one at a time (brief 1 A4 item 5): nothing of an earlier run may still be alive.
    live = proc.descendants()
    if any(state not in "ZX" for state in live.values()):
        raise Overlap(f"descendants still alive before spawning a child: {sorted(live)}")
    child = subprocess.Popen(cmd, cwd=cwd, stdout=log, stderr=subprocess.STDOUT, preexec_fn=proc.setup(True),
                             env=proc.child_env(scratch))
    try:
        code = child.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(child.pid, signal.SIGKILL)
        child.wait()
        return "timeout", None
    return OBSERVED.get(code, "error"), code


def _child(registry: str, pin: Pin, role: str, tree: Path, run_dir: Path, scratch: Path, cfg, log
           ) -> tuple[str, int | None]:
    cmd = proc.python("-m", "harness", "check", "--registry", registry, "--pin", pin.name,
           "--role", role, "--invocation-root", str(ROOT), "--run-dir", str(run_dir.resolve()),
           "--scratch", str(scratch))
    log.flush()
    return _spawn(cmd, tree, scratch, cfg.child_timeout_s, log)


@contextmanager
def _scratch(scratch_root: Path | None, cfg, row: dict) -> Iterator[Path]:
    """A scratch root owned by this parent for one child run. After the child exits or is killed, sweep this
    orchestrator's remaining descendants (recording how many were killed as `leaked_processes`), wait (up to
    reap_grace_s) until no live process holds the root, then delete it: a killed child cannot clean up after
    itself, so the parent does."""
    scratch = Path(tempfile.mkdtemp(prefix="assize-scratch-", dir=scratch_root))
    row["scratch"] = str(scratch)
    try:
        yield scratch
    finally:
        row["leaked_processes"] = proc.sweep(cfg.reap_grace_s, cfg.poll_step_s)
        row["scratch_quiescent"] = proc.wait_until(lambda: not proc.holders(scratch), cfg.reap_grace_s,
                                                   cfg.poll_step_s)
        shutil.rmtree(scratch, ignore_errors=True)
        row["scratch_removed"] = not scratch.exists()


def _fresh_dir(path: Path) -> Path:
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True)
    return path


def _row(registry: str, pin: Pin, mutant: Mutant | None, role: str, run_dir: Path) -> dict:
    return {
        "kind": "run",
        "registry": registry,
        "pin": pin.name,
        "mutant": None if mutant is None else pin.label(mutant),
        "role": role,
        "expected": "fail" if role == "mutant" else "pass",
        "transcript": os.path.relpath(run_dir / "transcript.log", Path.cwd()),
        "run_dir": str(run_dir.resolve()),
    }


def _run_clean(registry: str, pin: Pin, out: Path, cfg, scratch_root: Path | None) -> dict:
    run_dir = _fresh_dir(out / "runs" / _slug(pin.name) / "clean")
    row = _row(registry, pin, None, "clean", run_dir) | {"tree": "invocation"}
    t0 = time.monotonic()
    with (run_dir / "transcript.log").open("w") as log, _scratch(scratch_root, cfg, row) as scratch:
        observed, code = _child(registry, pin, "clean", ROOT, run_dir, scratch, cfg, log)
    verdict = "ok" if observed == "pass" else "FAILED"
    row |= {"observed": observed, "exit_code": code, "duration_s": round(time.monotonic() - t0, 3)}
    return row | {"verdict": _leak_override(verdict, row)}


def _run_in_copy(registry: str, pin: Pin, mutant: Mutant, role: str, out: Path, cfg,
                 scratch_root: Path | None) -> dict:
    """role 'mutant': copy plus the mutant's edits. role 'twin': identical fresh copy, no edits."""
    run_dir = _fresh_dir(out / "runs" / _slug(pin.name) / mutant.name / role)
    row = _row(registry, pin, mutant, role, run_dir) | {"edits": mutant.edits}
    mutant_edits = edits.load(mutant.edits)
    row["edits_sha256"] = hashlib.sha256((ROOT / mutant.edits).read_bytes()).hexdigest()
    t0 = time.monotonic()
    with ((run_dir / "transcript.log").open("w") as log, _scratch(scratch_root, cfg, row) as scratch,
          disposable_copy(ROOT, under=scratch) as copy):
        row["tree"] = str(copy)
        log.write(f"copy of {ROOT}\n  at {copy}\n")
        if role == "mutant":
            try:
                edits.apply(copy, mutant_edits)
                log.write(f"applied {len(mutant_edits)} edit(s) from {mutant.edits}\n")
                observed, code = _child(registry, pin, role, copy, run_dir, scratch, cfg, log)
            except edits.Stale as e:
                log.write(f"STALE: {e}\n")
                row["stale_detail"] = str(e)
                observed, code = "stale", None
        else:
            log.write("twin: no edits applied\n")
            observed, code = _child(registry, pin, role, copy, run_dir, scratch, cfg, log)
    row["copy_discarded"] = not Path(row["tree"]).exists()
    return row | {"observed": observed, "exit_code": code, "duration_s": round(time.monotonic() - t0, 3)}


def _leak_override(verdict: str, *rows: dict) -> str:
    """A run that left a live descendant for the sweep, or whose scratch root was still held after the sweep and
    reap_grace_s, is LEAKED, whatever was observed (brief 0 A3, brief 1 A4 item 5)."""
    if any(r.get("leaked_processes", 0) > 0 or r.get("scratch_quiescent") is False for r in rows):
        return "LEAKED"
    return verdict


def _verdict(mutant_obs: str, twin_obs: str) -> str:
    if mutant_obs == "stale":
        return "STALE"
    if twin_obs != "pass":
        return "NON-CAUSAL"
    if mutant_obs == "fail":
        return "KILLED"
    if mutant_obs == "pass":
        return "SURVIVED"
    return "INCONCLUSIVE"


def _run_mutant(registry: str, pin: Pin, mutant: Mutant, out: Path, cfg,
                scratch_root: Path | None) -> tuple[dict, dict]:
    mrow = _run_in_copy(registry, pin, mutant, "mutant", out, cfg, scratch_root)
    trow = _run_in_copy(registry, pin, mutant, "twin", out, cfg, scratch_root)
    trow["verdict"] = _leak_override("ok" if trow["observed"] == "pass" else "FAILED", trow)
    mrow["twin_observed"] = trow["observed"]
    mrow["verdict"] = _leak_override(_verdict(mrow["observed"], trow["observed"]), mrow, trow)
    return mrow, trow


TALLY = {"KILLED": "killed", "SURVIVED": "survived", "INCONCLUSIVE": "inconclusive",
         "STALE": "stale", "NON-CAUSAL": "non_causal", "LEAKED": "leaked"}


# ------------------------------------------------------- since a green head

# A change to any of these runs every pin: the harness (each pin's own code and its `edits/` file) and the environment
# every check runs in (instruction #108 item 2).
FORCE_ALL = ("harness/**", "Makefile", "pyproject.toml", "uv.lock")
_GLOB_TOKEN = re.compile(r"\*\*/|\*\*|\*|\?|[^*?]+")
_GLOB_REGEX = {"**/": "(?:.*/)?", "**": ".*", "*": "[^/]*", "?": "[^/]"}


def matches(path: str, glob: str) -> bool:
    """`**` matches any run of path segments (`**/` also none), `*` and `?` match within one segment."""
    regex = "".join(_GLOB_REGEX.get(t, re.escape(t)) for t in _GLOB_TOKEN.findall(glob))
    return re.fullmatch(regex, path) is not None


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                          env=os.environ | {"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"})


def changed_paths(repo: Path, since: str) -> tuple[str, ...]:
    """`git diff --name-only <since>...HEAD`, renames split into their two paths so a path moved away still counts."""
    out = _git(repo, "diff", "--no-renames", "--name-only", f"{since}...HEAD")
    if out.returncode != 0:
        raise RuntimeError(f"changed paths since {since} not read: {out.stderr.strip()}")
    return tuple(out.stdout.split())


def select(pins: Sequence[Pin], changed: Sequence[str]) -> tuple[list[Pin], list[Pin]]:
    """(the pins that run, the pins skipped): a pin runs if a changed path matches one of its witnesses, and every pin
    runs if a changed path matches FORCE_ALL."""
    force = any(matches(path, g) for path in changed for g in FORCE_ALL)

    def runs(pin: Pin) -> bool:
        return force or any(matches(path, w) for path in changed for w in pin.witnesses)

    return [p for p in pins if runs(p)], [p for p in pins if not runs(p)]


def full_report(rows: Sequence[Mapping]) -> bool:
    """A pins report usable as a base: one accepted registry row of phase `all`, every registry pin's clean run ok,
    every registry mutant KILLED, nothing skipped, and a summary exiting 0."""
    registry = [r for r in rows if r.get("kind") == "registry"]
    summary = [r for r in rows if r.get("kind") == "summary"]
    runs = [r for r in rows if r.get("kind") == "run"]
    if len(registry) != 1 or len(summary) != 1:
        return False
    reg, summ = registry[0], summary[0]
    ok = {r.get("pin") for r in runs if r.get("role") == "clean" and r.get("verdict") == "ok"}
    killed = {r.get("mutant") for r in runs if r.get("role") == "mutant" and r.get("verdict") == "KILLED"}
    return (reg.get("status") == "accepted" and reg.get("phase") == "all"
            and set(reg.get("pins", ())) <= ok and set(reg.get("mutants", ())) <= killed
            and not any(r.get("verdict") == "skipped" for r in runs)
            and not summ.get("skipped") and summ.get("exit_code") == 0)


def is_ancestor(repo: Path, sha: str) -> bool:
    return _git(repo, "merge-base", "--is-ancestor", sha, "HEAD").returncode == 0


def choose_base(repo: Path, runs: Iterable[Mapping], report: Callable[[int], Sequence[Mapping] | None]
                ) -> tuple[tuple[str, int] | None, list[str]]:
    """The newest successful pins run (`runs` newest first) whose head is an ancestor of HEAD and whose report is a
    full one (`full_report`); `report(run id)` reads it, None if it cannot. Returns (head sha, run id) or None, and
    why each newer run was refused."""
    refused: list[str] = []
    for r in runs:
        rows = None
        if r.get("conclusion") != "success":
            refused.append(f"run {r.get('id')}: concluded {r.get('conclusion')}")
        elif not is_ancestor(repo, str(r.get("head_sha"))):
            refused.append(f"run {r.get('id')}: head {str(r.get('head_sha'))[:7]} is not an ancestor of HEAD")
        elif (rows := report(int(r["id"]))) is None:
            refused.append(f"run {r.get('id')}: report not read")
        elif not full_report(rows):
            refused.append(f"run {r.get('id')}: report skipped a pin or is not every pin ok and every mutant KILLED")
        else:
            return (str(r["head_sha"]), int(r["id"])), refused
    return None, refused


def boundary(repo: Path, master: str) -> bool:
    """The branch records a layer verdict (adds a `- L<n>` line to the root REPORT.md) or opens a brief (adds a file
    under docs/briefs/): CLAUDE.md A1.3's layer boundary."""
    report = _git(repo, "diff", "--no-renames", "-U0", f"{master}...HEAD", "--", "REPORT.md")
    briefs = _git(repo, "diff", "--no-renames", "--name-only", "--diff-filter=A", f"{master}...HEAD", "--",
                  "docs/briefs/")
    if report.returncode != 0 or briefs.returncode != 0:
        raise RuntimeError(f"diff against {master} not read: {report.stderr.strip()} {briefs.stderr.strip()}")
    return bool(re.search(r"^\+- L\d", report.stdout, re.M)) or bool(briefs.stdout.strip())


def _gh_runs(repo: Path) -> Iterator[dict]:
    out = subprocess.run(["gh", "api", "--paginate", "repos/{owner}/{repo}/actions/workflows/pins.yml/runs?"
                          "status=success&per_page=100", "--jq", ".workflow_runs[] | {id, head_sha, conclusion}"],
                         cwd=repo, capture_output=True, text=True, timeout=300)
    if out.returncode != 0:
        raise RuntimeError(f"pins runs not listed: {out.stderr.strip()}")
    return (json.loads(line) for line in out.stdout.splitlines() if line.strip())


def _gh_report(repo: Path, run_id: int) -> list[dict] | None:
    with tempfile.TemporaryDirectory(prefix="assize-base-") as d:
        got = subprocess.run(["gh", "run", "download", str(run_id), "-n", "pins-report", "-D", d], cwd=repo,
                             capture_output=True, text=True, timeout=300)
        path = Path(d) / "pins.jsonl"
        if got.returncode != 0 or not path.is_file():
            return None
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def base(repo: Path, master: str) -> int:
    """Print `--since <sha> --since-run <id>` for the base `choose_base` finds through the GitHub API, or nothing, so
    every pin runs: on a layer boundary, with no usable base, or when the API cannot be read. Each reason goes to
    stderr (instruction #108 item 3)."""
    try:
        if boundary(repo, master):
            print("base: none: the branch records a layer verdict or opens a brief; every pin runs", file=sys.stderr)
            return 0
        chosen, refused = choose_base(repo, _gh_runs(repo), lambda run_id: _gh_report(repo, run_id))
    except (RuntimeError, OSError, subprocess.SubprocessError, ValueError) as e:
        print(f"base: none: {e}; every pin runs", file=sys.stderr)
        return 0
    for line in refused:
        print(f"base: refused {line}", file=sys.stderr)
    if chosen is None:
        print("base: none: no successful full pins run on an ancestor of HEAD; every pin runs", file=sys.stderr)
        return 0
    print(f"base: run {chosen[1]} on {chosen[0]}", file=sys.stderr)
    print(f"--since {chosen[0]} --since-run {chosen[1]}")
    return 0


def _proposer() -> dict:
    with (ROOT / "harness" / "proposer.toml").open("rb") as f:
        data = tomllib.load(f)
    return {k: data[k] for k in ("kind", "model", "session")}


def run(registry: str, phase: str, out: Path, config_path: Path | None, scratch_root: Path | None = None,
        since: str | None = None, since_run: int | None = None, repo: Path = ROOT) -> int:
    """With `since`, run only the pins `select` picks from the paths changed in `repo` since that sha, and record each
    other pin as skipped, citing `since` and its pins run `since_run`; without it, every pin."""
    proc.set_subreaper()
    cfg = config_mod.load(config_path)
    out.mkdir(parents=True, exist_ok=True)
    rows_path = out / "pins.jsonl"
    with rows_path.open("w") as sink:

        def emit(row: dict) -> None:
            sink.write(json.dumps(row, sort_keys=True) + "\n")
            sink.flush()

        head = {
            "kind": "registry",
            "registry": registry,
            "phase": phase,
            "config": os.path.relpath(cfg.path, ROOT),
            "child_timeout_s": cfg.child_timeout_s,
            "reap_grace_s": cfg.reap_grace_s,
            "invocation_root": str(ROOT),
            "python": sys.version.split()[0],
            "proposer": _proposer(),
        }
        try:
            pins = registries.load(registry)
        except RegistryError as e:
            emit(head | {"status": "refused", "code": e.code, "detail": e.detail})
            emit({"kind": "summary", "registry": registry, "exit_code": EXIT_REFUSED})
            print(f"REGISTRY REFUSED: {registry}: {e}")
            return EXIT_REFUSED
        changed = None if since is None else changed_paths(repo, since)
        ran, skipped = (pins, []) if changed is None else select(pins, changed)
        emit(head | {"status": "accepted", "pins": [p.name for p in pins],
                     "mutants": [p.label(m) for p in pins for m in p.mutants],
                     "since": since, "since_run": since_run, "changed": changed,
                     "skipped": [p.name for p in skipped]})
        print(f"registry {registry}: {len(pins)} pins, "
              f"{sum(len(p.mutants) for p in pins)} mutants; phase={phase}; "
              f"child_timeout_s={cfg.child_timeout_s} ({os.path.relpath(cfg.path, ROOT)})")

        counts = dict(clean_total=0, clean_ok=0, clean_failed=0,
                      mutants_total=0, killed=0, survived=0, inconclusive=0, stale=0, non_causal=0, leaked=0,
                      twins_total=0, twins_ok=0, twins_failed=0, skipped=0, skipped_mutants=0)

        # A skipped pin is recorded, never counted as ok and never dropped (instruction #108 item 2).
        for pin in skipped:
            emit({"kind": "run", "registry": registry, "pin": pin.name, "mutant": None, "role": "skipped",
                  "verdict": "skipped", "since": since, "since_run": since_run, "witnesses": list(pin.witnesses),
                  "mutants": [pin.label(m) for m in pin.mutants]})
            print(f"[skip  ] {pin.name}: no changed path matches {list(pin.witnesses)} since {since} (run {since_run})")
            counts["skipped"] += 1
            counts["skipped_mutants"] += len(pin.mutants)

        if phase in ("all", "clean"):
            for pin in ran:
                row = _run_clean(registry, pin, out, cfg, scratch_root)
                emit(row)
                print(f"[clean ] {pin.name}: observed {row['observed']} -> {row['verdict']} "
                      f"({row['duration_s']}s) {row['transcript']}")
                counts["clean_total"] += 1
                counts["clean_ok" if row["verdict"] == "ok" else "clean_failed"] += 1
                counts["leaked"] += row["verdict"] == "LEAKED"
                if row["verdict"] != "ok":
                    print(f"CLEAN FAILED: {pin.name} (observed {row['observed']})")

        if phase in ("all", "mutants"):
            for pin, mutant in [(p, m) for p in ran for m in p.mutants]:
                mrow, trow = _run_mutant(registry, pin, mutant, out, cfg, scratch_root)
                emit(mrow)
                emit(trow)
                label = pin.label(mutant)
                verdict = mrow["verdict"]
                print(f"[mutant] {label}: mutant {mrow['observed']}, twin {trow['observed']} -> {verdict} "
                      f"({mrow['duration_s']}s + {trow['duration_s']}s) {mrow['transcript']}")
                counts["mutants_total"] += 1
                counts[TALLY[verdict]] += 1
                counts["twins_total"] += 1
                counts["twins_ok" if trow["verdict"] == "ok" else "twins_failed"] += 1
                if verdict != "KILLED":
                    print(f"MUTANT {verdict}: {label}")

        bad = sum(counts[k] for k in ("clean_failed", "survived", "inconclusive", "stale", "non_causal", "leaked"))
        code = 0 if bad == 0 else 1
        emit({"kind": "summary", "registry": registry, "phase": phase, **counts, "since": since,
              "since_run": since_run, "exit_code": code})
    n = counts["mutants_total"]
    print(f"clean: {counts['clean_ok']}/{counts['clean_total']} passed, "
          f"{counts['clean_failed']}/{counts['clean_total']} failed")
    print(f"mutants: {counts['killed']}/{n} killed, {counts['survived']}/{n} survived, "
          f"{counts['inconclusive']}/{n} inconclusive, {counts['stale']}/{n} stale, "
          f"{counts['non_causal']}/{n} non-causal, {counts['leaked']} leaked (clean and mutant)")
    print(f"twins: {counts['twins_ok']}/{counts['twins_total']} passed")
    print(f"skipped: {counts['skipped']}/{len(pins)} pins, {counts['skipped_mutants']} mutants"
          + ("" if since is None else f" since {since[:7]} (run {since_run})"))
    print(f"report: {os.path.relpath(rows_path, Path.cwd())}")
    print("PINS PASSED" if code == 0 else "PINS FAILED")
    return code


def run_under_edits(edits_file: str, registry: str, phase: str, out: Path, config_path: Path | None) -> int:
    """Run the whole suite inside a disposable copy carrying `edits_file` (an unregistered mutant).
    The invocation tree is not modified."""
    mutant_edits = edits.load(edits_file)
    with disposable_copy(ROOT) as copy:
        print(f"UNDER EDITS: {edits_file} "
              f"(sha256 {hashlib.sha256((ROOT / edits_file).read_bytes()).hexdigest()})")
        try:
            edits.apply(copy, mutant_edits)
        except edits.Stale as e:
            print(f"STALE: {e}")
            return EXIT_ERROR
        print(f"copy: {copy}")
        sys.stdout.flush()
        cmd = proc.python("-m", "harness", "run", "--registry", registry, "--phase", phase,
                          "--out", str(out.resolve()))
        if config_path is not None:
            cmd += ["--config", str(config_path.resolve())]
        return subprocess.run(cmd, cwd=copy, preexec_fn=proc.setup(False),
                              env=proc.child_env(copy.parent)).returncode
