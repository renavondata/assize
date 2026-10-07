"""The harness's own pins (L0, brief 0 A2). Each kills its named mutant, an anchored edit to the harness,
and each kill is causal: the mutant run fails and its unedited twin passes."""

from __future__ import annotations

import json
import math
import os
import py_compile
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

from harness import claims, config, context, edits, proc, scan, tree
from harness.fixtures import daemon, escapee, leaky
from harness.nested import run_nested
from harness.pin import ROOT, Mutant, Pin


def _all(*runs) -> bool:
    return all(r.ok for r in runs)


def _edits(name: str) -> str:
    return f"harness/edits/{name}.toml"


def p0_survivors_reported() -> bool:
    """With every child check forced to succeed, the suite reports every fixture mutant SURVIVED and exits non-zero."""
    before = tree.digest(ROOT)
    ctrl = run_nested("control", "fixture.basic", "mutants")
    ctrl.expect(tree.digest(ROOT) == before, "invocation tree's harness/ unchanged by the mutant runs (trusted base)")
    muts, twins = ctrl.runs("mutant"), ctrl.runs("twin")
    ctrl.expect(ctrl.exit_code == 0, "control exits 0")
    ctrl.expect(len(muts) == len(twins) == 2 == ctrl.summary.get("mutants_total"), "control: 2 mutants, 2 twins")
    ctrl.expect(all(r.get("verdict") == "KILLED" for r in muts), "control: every mutant KILLED")
    ctrl.expect(all(r.get("observed") == "pass" for r in twins), "control: every twin passed")
    root = ctrl.registry.get("invocation_root")
    ctrl.expect(all(r.get("tree") not in (None, root) and r.get("copy_discarded") is True for r in muts + twins),
                "control: every mutant and twin ran in a discarded copy, not the invocation tree")

    inj = run_nested("checks_always_pass", "fixture.basic", "mutants", edits=_edits("P0_checks_always_pass"))
    muts = inj.runs("mutant")
    inj.expect(inj.exit_code not in (0, None), "every check forced to succeed: suite exits non-zero")
    inj.expect(len(muts) == 2 and inj.summary.get("survived") == 2 == inj.summary.get("mutants_total"),
               "every fixture mutant reported SURVIVED (2/2)")
    inj.expect(all(r.get("verdict") == "SURVIVED" and r.get("observed") == "pass" for r in muts),
               "every mutant row: observed pass, verdict SURVIVED")
    return _all(ctrl, inj)


def p0b_no_switches() -> bool:
    """No environment read of a mutant or test variable, and no mutant-switch module, anywhere in the tree."""
    found, scanned = scan.violations(ROOT)
    print(f"scanned {scanned} code files under {ROOT} (top-level exclusions: {sorted(tree.TOP_LEVEL_EXCLUDE)})")
    for v in found:
        print(f"  VIOLATION {v}")
    print(f"  [{'ok' if scanned > 0 else 'FAIL'}] scan is non-vacuous")
    print(f"  [{'ok' if not found else 'FAIL'}] no switch found ({len(found)} violations)")
    return scanned > 0 and not found


def p0c_clean_failure() -> bool:
    """A failing clean check is recorded FAILED and fails the suite."""
    n = run_nested("clean", "fixture.broken", "clean")
    row = n.run("fixture/broken")
    n.expect(row.get("observed") == "fail" and row.get("verdict") == "FAILED", "fixture/broken recorded FAILED")
    n.expect(n.run("fixture/toy").get("verdict") == "ok", "fixture/toy recorded ok")
    n.expect(n.summary.get("clean_total") == 2 and n.summary.get("clean_failed") == 1, "denominator: 1/2 failed")
    n.expect(n.exit_code not in (0, None), "suite exits non-zero")
    return n.ok


def p0d_inconclusive() -> bool:
    """Raising and hanging mutants are recorded INCONCLUSIVE, counted, and fail the suite."""
    n = run_nested("inconclusive", "fixture.inconclusive", "mutants",
                   config=ROOT / "harness" / "fixtures" / "fast.toml")
    raises = n.run("fixture/toy", "fixture/toy/raises", "mutant")
    hangs = n.run("fixture/toy", "fixture/toy/hangs", "mutant")
    n.expect(raises.get("observed") == "error" and raises.get("verdict") == "INCONCLUSIVE",
             "raises: observed error, INCONCLUSIVE")
    n.expect(hangs.get("observed") == "timeout" and hangs.get("verdict") == "INCONCLUSIVE",
             "hangs: observed timeout, INCONCLUSIVE")
    n.expect(raises.get("twin_observed") == "pass" and hangs.get("twin_observed") == "pass", "both twins passed")
    n.expect(n.registry.get("config") == "harness/fixtures/fast.toml", "timeout taken from committed config")
    n.expect(hangs.get("duration_s", 0) >= n.registry.get("child_timeout_s", float("inf")),
             "hang ran at least the configured timeout")
    s = n.summary
    n.expect(s.get("mutants_total") == 3 and s.get("inconclusive") == 2 and s.get("killed") == 1,
             "denominator: 3 mutants, 2 inconclusive, 1 killed")
    n.expect(n.exit_code not in (0, None), "suite exits non-zero")
    return n.ok


def p0e_registry_validation() -> bool:
    """Registries with a mutant-less pin, a duplicated name, or a malformed edit file are refused."""
    runs = []
    for registry, code in (("fixture.no_mutants", "no_mutants"),
                           ("fixture.dup_pin", "duplicate_pin"),
                           ("fixture.dup_mutant", "duplicate_mutant"),
                           ("fixture.malformed_edit", "malformed_edit")):
        n = run_nested(registry.split(".", 1)[1], registry, "all")
        n.expect(n.registry.get("status") == "refused" and n.registry.get("code") == code,
                 f"{registry} refused with {code}")
        n.expect(not n.of("run"), "no pin was run")
        n.expect(n.exit_code not in (0, None), "suite exits non-zero")
        runs.append(n)
    ctrl = run_nested("accepted", "fixture.basic", "clean")
    ctrl.expect(ctrl.registry.get("status") == "accepted", "control: fixture.basic accepted")
    return _all(*runs, ctrl)


def p0f_non_causal() -> bool:
    """A check that fails outside the invocation tree is recorded NON-CAUSAL, with a non-zero exit."""
    n = run_nested("noncausal", "fixture.noncausal", "all")
    clean = n.run("fixture/outside")
    mut = n.run("fixture/outside", "fixture/outside/off_by_one", "mutant")
    twin = n.run("fixture/outside", "fixture/outside/off_by_one", "twin")
    n.expect(clean.get("verdict") == "ok", "clean run in the invocation tree passes")
    n.expect(mut.get("observed") == "fail" and twin.get("observed") == "fail",
             "mutant run and its twin both fail in their copies")
    n.expect(mut.get("verdict") == "NON-CAUSAL", "mutant recorded NON-CAUSAL, not KILLED")
    n.expect(n.summary.get("non_causal") == 1 == n.summary.get("mutants_total"), "denominator: 1/1 non-causal")
    n.expect(n.exit_code not in (0, None), "suite exits non-zero")
    return n.ok


def p0g_stale() -> bool:
    """Absent and duplicated anchors are recorded STALE, counted, and fail the suite."""
    n = run_nested("stale", "fixture.stale", "mutants")
    absent = n.run("fixture/toy", "fixture/toy/absent", "mutant")
    twice = n.run("fixture/toy", "fixture/toy/twice", "mutant")
    n.expect(absent.get("verdict") == "STALE" and "occurs 0 times" in absent.get("stale_detail", ""),
             "absent anchor: STALE (0 occurrences)")
    n.expect(twice.get("verdict") == "STALE" and "occurs 2 times" in twice.get("stale_detail", ""),
             "duplicated anchor: STALE (2 occurrences)")
    n.expect(n.run("fixture/toy", "fixture/toy/off_by_one", "mutant").get("verdict") == "KILLED",
             "control mutant KILLED")
    s = n.summary
    n.expect(s.get("mutants_total") == 3 and s.get("stale") == 2 and s.get("killed") == 1,
             "denominator: 3 mutants, 2 stale, 1 killed")
    n.expect(n.exit_code not in (0, None), "suite exits non-zero")
    return n.ok


P0H_SCOPE = ("after every child run, before its scratch root is deleted, every descendant of the orchestrator (a "
             "child subreaper) is dead: a cooperating grandchild dies by the parent-death signal and is not counted; "
             "a non-cooperating grandchild and a double-forked daemon are killed by the sweep, counted in "
             "leaked_processes, and make the run LEAKED. Out of scope: a process that never descends from the "
             "orchestrator (e.g. a container under the runtime's own shim; P10), and the outermost orchestrator "
             "being SIGKILLed.")


def _kill(pid: int | None, marker: str) -> None:
    """Leave the machine clean whatever the verdict."""
    if pid is not None and proc.alive(pid, marker):
        os.kill(pid, signal.SIGKILL)


def _pid(path: Path) -> int | None:
    return int(path.read_text()) if path.is_file() else None


def p0h_timeouts_leave_nothing() -> bool:
    """Witnessed scope: see P0H_SCOPE (brief 0 A3 item 3, brief 1 A4 item 5)."""
    cfg = config.load()
    n = run_nested("leaks", "fixture.leaks", "mutants", config=ROOT / "harness" / "fixtures" / "fast.toml")
    row = n.run("fixture/toy", "fixture/toy/leaks_and_hangs", "mutant")
    n.expect(row.get("observed") == "timeout" and row.get("verdict") == "INCONCLUSIVE",
             "cooperating grandchild: observed timeout, INCONCLUSIVE")
    n.expect(row.get("leaked_processes") == 0, "cooperating grandchild: died by the death signal, leaked_processes 0")
    n.expect(row.get("twin_observed") == "pass", "its twin passed")
    run_dir = Path(row.get("run_dir", "/nonexistent"))
    pid = _pid(run_dir / leaky.PID_FILE)
    copy_file = run_dir / leaky.COPY_FILE
    n.expect(pid is not None and copy_file.is_file(), "the check recorded its grandchild PID and nested copy")
    nested_copy = Path(copy_file.read_text()) if copy_file.is_file() else None
    scratch = Path(row.get("scratch", "/nonexistent"))

    gone = pid is not None and proc.wait_until(lambda: not proc.alive(pid, leaky.MARKER), cfg.reap_grace_s,
                                                cfg.poll_step_s)
    n.expect(gone, f"grandchild {pid} (ignores SIGTERM) no longer alive")
    n.expect(not proc.holders(scratch), "no live process holds the run's scratch root")
    n.expect(row.get("scratch_quiescent") is True, "parent saw the scratch root quiescent before deleting it")
    n.expect(nested_copy is not None and not nested_copy.exists(), f"nested copy {nested_copy} removed")
    n.expect(row.get("scratch_removed") is True and not scratch.exists(), f"scratch root {scratch} removed")
    _kill(pid, leaky.MARKER)
    shutil.rmtree(scratch, ignore_errors=True)
    return all((n.ok, p0h_escapee(), p0h_daemon()))


def p0h_escapee() -> bool:
    """A non-cooperating grandchild (new session, no death signal, SIGTERM ignored, hanging) is swept and LEAKED."""
    e = run_nested("escapee", "fixture.escapee", "clean", config=escapee.FAST)
    row = e.run("fixture/escapee")
    pid = _pid(Path(row.get("run_dir", "/nonexistent")) / escapee.PID_FILE)
    alive_after = pid is not None and proc.alive(pid, escapee.MARKER)
    e.expect(pid is not None, f"grandchild PID recorded ({pid})")
    e.expect(not alive_after, "grandchild dead when the nested run returns (killed by the sweep)")
    e.expect(row.get("observed") == "timeout", "child observed timeout")
    e.expect(row.get("leaked_processes", 0) >= 1, f"leaked_processes >= 1 ({row.get('leaked_processes')})")
    e.expect(row.get("verdict") == "LEAKED", "verdict LEAKED")
    e.expect(e.summary.get("leaked") == 1, "summary leaked = 1")
    e.expect(e.exit_code not in (0, None) and e.exit_code == e.summary.get("exit_code"),
             "exit non-zero and equal to the summary's")
    scratch = Path(row.get("scratch", "/nonexistent"))
    e.expect(row.get("scratch_removed") is True and not scratch.exists(), f"scratch root {scratch} removed")
    _kill(pid, escapee.MARKER)
    shutil.rmtree(scratch, ignore_errors=True)
    return e.ok


def p0h_daemon() -> bool:
    """A double-forked daemon left by a clean check that returns True is reparented to the orchestrator, swept and
    LEAKED."""
    d = run_nested("daemon", "fixture.daemon", "clean", config=escapee.FAST)
    row = d.run("fixture/daemon")
    pid = _pid(Path(row.get("run_dir", "/nonexistent")) / daemon.PID_FILE)
    alive_after = pid is not None and proc.alive(pid, daemon.MARKER)
    d.expect(pid is not None, f"PID recorded ({pid})")
    d.expect(not alive_after, "dead when the nested run returns (reparented to the subreaper and swept)")
    d.expect(row.get("observed") == "pass", "the check itself returned True")
    d.expect(row.get("leaked_processes", 0) >= 1, f"leaked_processes >= 1 ({row.get('leaked_processes')})")
    d.expect(row.get("verdict") == "LEAKED", "verdict LEAKED")
    d.expect(d.summary.get("leaked") == 1 and d.summary.get("clean_failed") == 1,
             "summary leaked = 1, clean_failed = 1")
    d.expect(d.exit_code not in (0, None), "suite exits non-zero")
    _kill(pid, daemon.MARKER)
    return d.ok


STAMP_OLD, STAMP_NEW = "VALUE = 4\n", "VALUE = 5\n"
STAMP_READ = "import sys; from pkg import stamp; print(stamp.VALUE, sys.flags.dont_write_bytecode)"


def _stamp_import(tree_root: Path, env: dict[str, str]) -> str:
    out = subprocess.run(proc.python("-c", STAMP_READ), cwd=tree_root, env=env,
                         capture_output=True, text=True, preexec_fn=proc.setup(False))
    return out.stdout.strip() or out.stderr.strip()


def _without_prefix(env: dict[str, str]) -> dict[str, str]:
    return {k: v for k, v in env.items() if k != "PYTHONPYCACHEPREFIX"}


def _same_second_edit(tree_root: Path, stamp_s: int) -> None:
    """A same-length edit to pkg/stamp.py that lands in the second the cached bytecode recorded."""
    edits.apply(tree_root, (edits.Edit("pkg/stamp.py", STAMP_OLD, STAMP_NEW),))
    os.utime(tree_root / "pkg" / "stamp.py", (stamp_s, stamp_s))


def p0i_no_stale_bytecode() -> bool:
    """A mutant edit that keeps the source's byte length and lands in the second recorded by a bytecode cache
    takes effect in a disposable copy: no `__pycache__` is copied at any depth (brief 1 A5), and a copy that keeps
    the stale in-tree `__pycache__` still runs the edited source because child Pythons read bytecode only under
    PYTHONPYCACHEPREFIX (brief 1 A6)."""
    work = Path(tempfile.mkdtemp(prefix="assize-p0i-", dir=context.scratch))
    src_root = work / "src"
    src = src_root / "pkg" / "stamp.py"
    src.parent.mkdir(parents=True)
    src.write_text(STAMP_OLD)
    stamp_s = int(src.stat().st_mtime)
    os.utime(src, (stamp_s, stamp_s))
    # The in-tree cache path, built by hand: this check itself runs under PYTHONPYCACHEPREFIX, which
    # importlib.util.cache_from_source would honour.
    pyc = src.parent / "__pycache__" / f"stamp.{sys.implementation.cache_tag}.pyc"
    py_compile.compile(str(src), cfile=str(pyc), doraise=True,
                       invalidation_mode=py_compile.PycInvalidationMode.TIMESTAMP)
    ok = True

    def expect(cond: bool, what: str) -> None:
        nonlocal ok
        print(f"  [{'ok' if cond else 'FAIL'}] {what}")
        ok = ok and cond

    expect(pyc.is_file() and len(STAMP_OLD) == len(STAMP_NEW),
           f"fixture: compiled {pyc.relative_to(work)}; edit keeps byte length {len(STAMP_OLD)}")
    control = work / "control"
    shutil.copytree(src_root, control)
    _same_second_edit(control, stamp_s)
    got = _stamp_import(control, _without_prefix(proc.child_env(work)))
    expect(got == "4 1", f"control: a plain copy keeping the cache, run without a cache prefix, reads stale bytecode "
                         f"({got!r}, want '4 1')")
    env = proc.child_env(work)
    stale_kept = (control / "pkg" / "__pycache__").is_dir()
    got = _stamp_import(control, env)
    expect(stale_kept and got == "5 1",
           f"prefix: the same copy, stale __pycache__ kept ({stale_kept}), run by child_env "
           f"(PYTHONPYCACHEPREFIX={env.get('PYTHONPYCACHEPREFIX')}), runs the edited source ({got!r}, want '5 1')")
    with tree.disposable_copy(src_root, under=work) as copy:
        caches = sorted(str(c.relative_to(copy)) for c in copy.rglob("__pycache__"))
        expect(not caches, f"disposable copy holds no __pycache__ at any depth ({caches})")
        _same_second_edit(copy, stamp_s)
        got = _stamp_import(copy, proc.child_env(work))
        expect(got == "5 1", f"disposable copy runs the edited source, child writes no bytecode ({got!r}, want '5 1')")
    shutil.rmtree(work, ignore_errors=True)
    return ok


HOST_FACTS = ROOT / "scripts" / "host_facts.sh"
REQUIRED_FACTS = ("uptime", "cpuset", "runner-version", "podman-info")
STUB = "#!/bin/sh\n{body}\n"
STUB_OK = {"uptime": 'echo " 12:00:00 up 1 day,  load average: 0.10, 0.20, 0.30"',
           "podman": '[ "$1" = info ] && echo "crun 2 systemd rootless=true" || echo "podman version 5.0.0"'}
STUB_FAIL = {"uptime": "exit 1", "podman": '[ "$1" = info ] && exit 125 || echo "podman version 5.0.0"'}


def _host_facts(work: Path, case: str, lacking: str | None) -> tuple[int, str]:
    """Run host_facts.sh against stubbed probes, with the one fact named by `lacking` failing."""
    root = work / case
    stubs, runner, out = root / "bin", root / "runner", root / "out"
    for d in (stubs, runner):
        d.mkdir(parents=True)
    for name in STUB_OK:
        stub = stubs / name
        fails = (lacking, name) in (("uptime", "uptime"), ("podman-info", "podman"))
        stub.write_text(STUB.format(body=(STUB_FAIL if fails else STUB_OK)[name]))
        stub.chmod(0o755)
    cpuset = root / "cpuset.cpus.effective"
    if lacking != "cpuset":
        cpuset.write_text("0-3\n")
    if lacking != "runner-version":
        (runner / ".runner").write_text('{"agentName": "stub"}')
    env = os.environ | {"PATH": f"{stubs}:{os.environ['PATH']}"}
    r = subprocess.run(["bash", str(HOST_FACTS), str(out), str(cpuset), str(runner)], env=env,
                       capture_output=True, text=True, timeout=60, preexec_fn=proc.setup(False))
    facts = out / "facts.txt"
    return r.returncode, facts.read_text() if facts.is_file() else ""


def p0j_host_facts_complete() -> bool:
    """host_facts.sh records load averages, the runner's cpuset, the runner version and the podman runtime line,
    and exits non-zero naming the fact when any one of them is missing: such facts are not a measurement
    (brief 1 A4 item 8)."""
    work = Path(tempfile.mkdtemp(prefix="assize-p0j-", dir=context.scratch))
    ok = True

    def expect(cond: bool, what: str) -> None:
        nonlocal ok
        print(f"  [{'ok' if cond else 'FAIL'}] {what}")
        ok = ok and cond

    code, facts = _host_facts(work, "complete", None)
    expect(code == 0, f"every fact present: exit 0 (got {code})")
    expect(all(f"### {name}\n" in facts for name in REQUIRED_FACTS), f"facts record {REQUIRED_FACTS}")
    expect("load average: 0.10" in facts and "0-3" in facts and "agentName" in facts
           and "crun 2 systemd rootless=true" in facts, "facts carry each probe's output")
    expect("NOT A MEASUREMENT" not in facts, "complete facts are not refused")
    for name in REQUIRED_FACTS:
        code, facts = _host_facts(work, f"lacks-{name}", name)
        refusal = next((line for line in facts.splitlines() if line.startswith("NOT A MEASUREMENT")), "")
        expect(code not in (0, None), f"{name} missing: exit non-zero (got {code})")
        expect(name in refusal.split(), f"{name} missing: refusal names it ({refusal!r})")
    shutil.rmtree(work, ignore_errors=True)
    return ok


def _expecter():
    """An `expect` that prints each assertion and remembers whether all held."""
    failures: list[str] = []

    def expect(cond: bool, what: str) -> None:
        print(f"  [{'ok' if cond else 'FAIL'}] {what}")
        if not cond:
            failures.append(what)

    return expect, lambda: not failures


def _codes(findings) -> set[tuple[str, str]]:
    return {(f.where, f.code) for f in findings}


def _real_root() -> Path:
    """The invocation tree: reports/ and .git are never copied, so the real ledgers, STATUS files and branch are
    read there by clean runs, mutants and twins alike."""
    return context.invocation_root or ROOT


# Rows of reports/L0/forecasts.jsonl written before CLAUDE.md A1.6 was enforced: the two resolutions named in brief 1
# A4 item 7a's witness. Ledgers are never edited, so these stay; any other L0 finding fails the pin.
L0_PRE_RULE = {("row 4", "missing_key"), ("row 5", "missing_key")}
LEDGER_PROPOSER = {"kind": "reviewer", "model": "m", "session": "s"}


def _ledger_fixture() -> tuple[dict, dict]:
    claim, ts = "pins green on the first CI run", "2026-01-01T00:00:00Z"
    forecast = {"id": claims.forecast_id(claim, ts), "ts": ts, "proposer": LEDGER_PROPOSER | {"kind": "builder"},
                "sha_before": "0" * 40, "claim": claim, "p": 0.8, "resolves_by": "first run"}
    resolution = {"id": forecast["id"], "ts": "2026-01-02T00:00:00Z", "proposer": LEDGER_PROPOSER, "outcome": True}
    return forecast, resolution


def _ledger(*rows: dict) -> list[str]:
    return [json.dumps(r) for r in rows]


def p0k_forecast_ledger() -> bool:
    """A forecasts.jsonl resolution row lacking id, ts, proposer or outcome, matching no earlier forecast, or not
    proposed by the Reviewer is rejected (brief 1 A4 item 7a, CLAUDE.md A1.6); every real ledger is validated."""
    expect, ok = _expecter()
    forecast, resolution = _ledger_fixture()
    got = claims.ledger_findings(_ledger(forecast, resolution))
    expect(not got, f"well-formed forecast and Reviewer resolution accepted ({[str(f) for f in got]})")
    for key in ("id", "ts", "proposer", "outcome"):  # stated by 7a, independently of the checker
        got = claims.ledger_findings(_ledger(forecast, {k: v for k, v in resolution.items() if k != key}))
        expect(("row 2", "missing_key") in _codes(got) and any(key in f.detail for f in got),
               f"resolution lacking {key} rejected ({[str(f) for f in got]})")
    cases = (("orphan", resolution | {"id": "000000000000"}, "orphan"),
             ("builder-proposed", resolution | {"proposer": LEDGER_PROPOSER | {"kind": "builder"}}, "not_reviewer"),
             ("L0 shape (resolves, evidence)", {"resolves": forecast["id"], "ts": resolution["ts"], "outcome": True,
                                                "evidence": "url"}, "missing_key"))
    for label, row, code in cases:
        got = claims.ledger_findings(_ledger(forecast, row))
        expect(("row 2", code) in _codes(got), f"{label} resolution rejected with {code} ({[str(f) for f in got]})")
    got = claims.ledger_findings(_ledger(resolution, forecast))
    expect(("row 1", "orphan") in _codes(got), "a resolution before its forecast matches no earlier forecast")
    got = claims.ledger_findings(_ledger(forecast | {"id": "ffffffffffff"}))
    expect(("row 1", "bad_id") in _codes(got), "a forecast whose id is not sha256(claim + ts)[:12] rejected")

    ledgers = sorted(_real_root().glob("reports/L*/forecasts.jsonl"))
    expect(bool(ledgers), f"real ledgers found: {[str(p.relative_to(_real_root())) for p in ledgers]}")
    for path in ledgers:
        lines = path.read_text().splitlines()
        got = claims.ledger_findings(lines)
        allowed = L0_PRE_RULE if path.parent.name == "L0" else set()
        for f in got:
            print(f"    {path.parent.name}: {f}")
        expect(_codes(got) == allowed if allowed else not got,
               f"{path.relative_to(_real_root())}: {len(lines)} rows, {len(got)} findings; "
               f"expected exactly {sorted(allowed) or 'none'}")
    return ok()


RUN = {"path": claims.PINS_WORKFLOW, "conclusion": "success"}
HEAD_SHA, OLDER_SHA = "a" * 40, "b" * 40
CI_RUNS = {1: RUN | {"id": 1, "head_sha": HEAD_SHA}, 2: RUN | {"id": 2, "head_sha": OLDER_SHA},
           3: RUN | {"id": 3, "head_sha": HEAD_SHA, "conclusion": "failure"},
           4: RUN | {"id": 4, "head_sha": HEAD_SHA, "path": ".github/workflows/measure.yml"}}


def _status(cites: str, verdict: str = "SESSION DONE", sha: str = HEAD_SHA[:7]) -> str:
    return f"# STATUS — L1 — 2026-01-01 — {sha} — PR #1\nVERDICT: {verdict}\ndid: {cites}\n"


def p0l_ci_claims() -> bool:
    """A STATUS or layer verdict line whose cited `pins` run ran on another sha than the one it names, or did not
    conclude success, is rejected (brief 1 A4 item 7b); every real STATUS and verdict line from L1 is checked."""
    expect, ok = _expecter()
    a, b = HEAD_SHA[:7], OLDER_SHA[:7]
    cases = (("cites a successful pins run on its own sha", _status(f"pins CI run 1 on {a}: success"), set()),
             ("cites a run on an older sha", _status(f"pins CI run 2 on {b}: success"), {"head_mismatch"}),
             ("cites a failed run", _status(f"pins CI run 3 on {a}"), {"not_success"}),
             ("STOPPED, cites a failed run on its own sha", _status(f"pins CI run 3 on {a}", "STOPPED: x"), set()),
             ("cites no run", _status("pins green"), {"uncited"}),
             ("cites an unrecorded run", _status(f"pins CI run 9 on {a}"), {"unrecorded"}),
             ("cites a measure run", _status(f"pins CI run 4 on {a}"), {"not_pins"}),
             ("cites a run under the wrong sha", _status(f"pins CI run 1 on {b}"), {"citation_mismatch"}))
    for label, text, want in cases:
        got = {f.code for f in claims.status_findings("fixture", text, CI_RUNS)}
        expect(got == want, f"STATUS {label}: findings {sorted(got)}, want {sorted(want)}")
    report = (f"- L0 — **PASSED** (pins.yml green)\n- L1 — **SEALED** (pins CI run 1 on {a})\n"
              f"- L1 — **SEALED** (pins CI run 2 on {a})\n- L1 — **SEALED** (pins green)\n")
    got = _codes(claims.report_findings("REPORT", report, CI_RUNS, 1))
    expect(got == {("REPORT:3", "citation_mismatch"), ("REPORT:3", "head_mismatch"), ("REPORT:4", "uncited")},
           f"REPORT: L0 line out of scope, good L1 line accepted, mismatched and uncited L1 lines rejected ({got})")

    root = _real_root()
    runs = claims.load_runs(root)
    statuses = sorted(p for p in root.glob("reports/L*/STATUS.md") if int(p.parent.name[1:]) >= 1)
    expect(bool(statuses), f"real STATUS files from L1: {[str(p.relative_to(root)) for p in statuses]}; "
                           f"{len(runs)} committed run records")
    for path in statuses:
        got = claims.status_findings(str(path.relative_to(root)), path.read_text(), runs)
        expect(not got, f"{path.relative_to(root)}: cites {claims.CITATION.findall(path.read_text())}; "
                        f"findings {[str(f) for f in got]}")
    text = (root / "REPORT.md").read_text()
    lines = [m for m in claims.VERDICT_LINE.finditer(text) if int(m.group(1)) >= 1]
    got = claims.report_findings("REPORT.md", text, runs, 1)
    expect(not got, f"REPORT.md: {len(lines)} verdict lines from L1; findings {[str(f) for f in got]}")
    return ok()


TRAILER_FIXTURE = (  # (label, path written, Proposer trailer lines, finding codes wanted)
    ("builder, ordinary path", "harness/x.py", ("builder m s",), set()),
    ("no trailer", "docs/x.md", (), {"no_proposer"}),
    ("builder only, CLAUDE.md", "CLAUDE.md", ("builder m s",), {"entrenched_without_guy"}),
    ("guy then builder, CLAUDE.md", "CLAUDE.md", ("guy", "builder m s"), set()),
    ("builder then guy, .github/", ".github/x.yml", ("builder m s", "guy"), set()),
    ("malformed party", "docs/y.md", ("builder m",), {"bad_party"}),
)
EXEMPTION_FIXTURE = (  # (label, path, party stated only in the body, party exempted or None, parties, findings wanted)
    ("body-only Proposer, not exempted", "docs/z.md", "reviewer m s", None, (), {"no_proposer"}),
    ("body-only Proposer, exempted", "docs/z.md", "reviewer m s", "reviewer m s", ("reviewer m s",), set()),
    ("body-only Proposer, another party exempted", "docs/z.md", "reviewer m s", "reviewer m t", (), {"no_proposer"}),
)
FIXTURE_GIT = {"GIT_AUTHOR_NAME": "f", "GIT_AUTHOR_EMAIL": "f@f", "GIT_COMMITTER_NAME": "f",
               "GIT_COMMITTER_EMAIL": "f@f"}


def _trailer_repo(repo: Path) -> tuple[list[str], dict[str, str]]:
    """A fixture repository: a base commit, one commit per TRAILER_FIXTURE case, then one per EXEMPTION_FIXTURE case,
    whose `Proposer:` line a blank line separates from a following `Co-Authored-By:`, so git parses no trailer.
    Returns their shas and the exemptions the EXEMPTION_FIXTURE cases name."""
    env = os.environ | claims.GIT_ENV | FIXTURE_GIT

    def git(*args: str) -> str:
        return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True,
                              env=env).stdout.strip()

    def commit(path: str, message: str, n: int) -> str:
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"{n}\n")
        git("add", "-A")
        git("commit", "-q", "-m", f"case {n}\n\nbody\n\n{message}")
        return git("rev-parse", "HEAD")

    def trailered(trailers: tuple[str, ...]) -> str:
        return "".join(f"Proposer: {t}\n" for t in trailers)

    repo.mkdir(parents=True)
    git("init", "-q", "-b", "master")
    commit("CODEOWNERS", trailered(("guy",)), 0)
    shas = [commit(path, trailered(trailers), n) for n, (_, path, trailers, _) in enumerate(TRAILER_FIXTURE, 1)]
    unparsed = [commit(path, f"Proposer: {party}\n\nCo-Authored-By: f <f@f>\n", n)
                for n, (_, path, party, *_) in enumerate(EXEMPTION_FIXTURE, len(shas) + 1)]
    exemptions = {sha: exempt for sha, (_, _, _, exempt, *_) in zip(unparsed, EXEMPTION_FIXTURE) if exempt}
    return shas + unparsed, exemptions


def _branch_base(root: Path) -> str | None:
    for ref in ("origin/master", "master"):
        try:
            return claims._git(root, "merge-base", "HEAD", ref).strip()
        except subprocess.CalledProcessError:
            continue
    return None


def p0m_commit_proposers() -> bool:
    """Every commit on the branch carries well-formed `Proposer:` trailers; one touching an entrenched path
    (CODEOWNERS) without a `guy` party is rejected; every party line is read (brief 1 A4 item 7c, A5 F2). A body-only
    `Proposer:` line counts only for a commit claims.PROPOSER_EXEMPTIONS lists, and only as the party it names
    (review aa993f4 F1)."""
    expect, ok = _expecter()
    patterns = claims.codeowners_patterns((ROOT / "CODEOWNERS").read_text())
    expect("CLAUDE.md" in patterns and ".github/" in patterns, f"entrenched paths from CODEOWNERS: {patterns}")
    work = Path(tempfile.mkdtemp(prefix="assize-p0m-", dir=context.scratch))
    shas, exemptions = _trailer_repo(work / "repo")
    commits = claims.branch_commits(work / "repo", "master~" + str(len(shas)), exemptions=exemptions)
    expect([c.sha for c in commits] == shas, f"fixture: {len(commits)} branch commits read, want {len(shas)}")
    cases = [(label, trailers, want) for label, _, trailers, want in TRAILER_FIXTURE] + \
            [(label, trailers, want) for label, _, _, _, trailers, want in EXEMPTION_FIXTURE]
    for (label, trailers, want), c in zip(cases, commits):
        got = {f.code for f in claims.commit_findings(c, patterns)}
        expect(got == want and c.parties == trailers,
               f"{label}: parties reported {list(c.parties)}, findings {sorted(got)}; want {list(trailers)}, "
               f"{sorted(want)}")
    shutil.rmtree(work, ignore_errors=True)

    root = _real_root()
    shallow = claims._git(root, "rev-parse", "--is-shallow-repository").strip() == "true"
    base = _branch_base(root)
    if base is None and shallow:
        print(f"  [skip] real branch at {root}: shallow clone without master, base unresolvable; not checked in "
              f"this run (checked by every make pins in a full clone)")
        return ok()
    expect(base is not None, f"real branch: base resolved ({base})")
    real = claims.branch_commits(root, base) if base else []
    found = [f for c in real for f in claims.commit_findings(c, patterns)]
    for c in real:
        print(f"    {c.sha[:12]} parties {list(c.parties)}")
    expect(not found, f"real branch {base and base[:12]}..HEAD: {len(real)} commits; findings "
                      f"{[str(f) for f in found]}")
    return ok()


PURITY_FIXTURE = (  # (label, schema, tokens wanted) against a fixture manifest's vocabulary
    ("clean", {"type": "object", "description": "a generic field"}, set()),
    ("as a key", {"properties": {"semantic": {}}}, {"semantic"}),
    ("as a value", {"enum": ["wood_pickaxe"]}, {"wood_pickaxe", "wood", "pickaxe"}),
    ("inside a description", {"description": "counts the Wood held"}, {"wood"}),
    ("as an underscore part", {"const": "max_wood"}, {"wood"}),
)
PURITY_MANIFEST = {"world": "fx", "observation": [{"name": "semantic", "vocabulary": ["grass"]}],
                   "actions": ["noop"], "targets": [{"name": "wood_pickaxe", "field": "semantic", "support": [0, 1]}],
                   "utility": {"components": []}}


def p6_schema_purity() -> bool:
    """No manifest vocabulary token appears in any interface schema file; the schemas are valid JSON Schema carrying
    schema_version, every manifest conforms to the manifest schema, and the step messages they define carry no seed
    (brief 1 section 1)."""
    import jsonschema
    import referencing
    from worlds.spec import purity

    expect, ok = _expecter()
    vocab = purity.vocabulary([PURITY_MANIFEST])
    for label, schema, want in PURITY_FIXTURE:
        got = {tok for _, tok in purity.violations({"fx": schema}, vocab)}
        expect(got == want, f"fixture token {label}: found {sorted(got)}, want {sorted(want)}")

    schemas = purity.load(purity.schema_files())
    manifests = purity.load(purity.manifest_files())
    expect(sorted(schemas) == ["manifest.schema.json", "rpc.schema.json"], f"schema files: {sorted(schemas)}")
    expect(bool(manifests), f"manifests: {sorted(manifests)}")
    for name, s in schemas.items():
        try:
            jsonschema.Draft202012Validator.check_schema(s)
            valid = True
        except jsonschema.SchemaError as e:
            valid, name = False, f"{name} ({e.message})"
        expect(valid and s.get("schema_version") == "1.0.0", f"{name}: valid 2020-12 schema, schema_version 1.0.0")
    registry = referencing.Registry().with_resources(
        (s["$id"], referencing.Resource.from_contents(s)) for s in schemas.values())
    manifest_v = jsonschema.Draft202012Validator(schemas["manifest.schema.json"], registry=registry)
    rpc_v = jsonschema.Draft202012Validator(schemas["rpc.schema.json"], registry=registry)
    for name, m in manifests.items():
        errors = [e.message for e in manifest_v.iter_errors(m)]
        expect(not errors, f"{name} conforms to manifest.schema.json ({errors[:2]})")
    m = next(iter(manifests.values()))
    bare = m | {"observation": [{k: v for k, v in f.items() if k != "vocabulary"} for f in m["observation"]]}
    expect(not manifest_v.is_valid(bare), "manifest.schema.json rejects a categorical field with no vocabulary")

    obs = {f["name"]: 0 for f in m["observation"]}
    step = {"jsonrpc": "2.0", "id": 1, "method": "step", "params": {"t": 0, "observation": obs, "legal_actions": [0]}}
    messages = (
        ("begin_episode with the manifest", {"jsonrpc": "2.0", "id": 0, "method": "begin_episode",
                                             "params": {"schema_version": "1.0.0", "manifest": m}}, True),
        ("step", step, True),
        ("step carrying a seed", step | {"params": step["params"] | {"seed": 7}}, False),
        ("begin_episode carrying a seed", {"jsonrpc": "2.0", "id": 0, "method": "begin_episode",
                                           "params": {"schema_version": "1.0.0", "manifest": m, "seed": 7}}, False),
        ("reply with a prediction", {"jsonrpc": "2.0", "id": 1, "result": {
            "action": 0, "prediction": {t["name"]: [1 / len(t["support"])] * len(t["support"]) for t in m["targets"]}}},
         True),
        ("end_episode", {"jsonrpc": "2.0", "id": 2, "method": "end_episode",
                         "params": {"termination": "crash", "utility": 0}}, True),
    )
    for label, msg, want in messages:
        expect(rpc_v.is_valid(msg) == want, f"rpc.schema.json {'accepts' if want else 'rejects'} {label}")

    vocab = purity.vocabulary(manifests.values())
    found = purity.violations(schemas, vocab)
    expect(len(vocab) > 0 and not found,
           f"real schemas: {len(vocab)} vocabulary tokens from {sorted(manifests)}; found in schemas: {found}")
    return ok()


# P11's child (brief 1 section 3, A7): for each seed, play the committed action stream twice and print the trajectory
# hashes, the utility, the unlocked set, every manifest departure of every emitted observation, and every step at
# which a chunk container departs from the package's own object list (after reset and after every step). A World that
# raises is reported per seed as data, with what was checked before the raise, so P11 fails on it rather than erroring.
TRAJECTORY_RUN = """
import json, random, sys
from worlds.crafter import binding
m = binding.manifest()

def play(seed, rec):
    rng = random.Random(seed)
    actions = [rng.randrange(len(m["actions"])) for _ in range(int(sys.argv[2]))]
    rec.update(violations=[], chunk_departures=[], chunk_departure_count=0)

    def check(ep):
        rec["violations"] = sorted(set(rec["violations"]) | set(binding.violations(ep.observation, m["observation"])))
        found = binding.chunk_departures(ep._env)
        rec["chunk_departures"] = (rec["chunk_departures"] + [(ep.t, d) for d in found])[:5]
        rec["chunk_departure_count"] += len(found)

    ep = binding.Episode(seed, m)
    check(ep)
    for a in actions:
        if ep.done:
            break
        ep.step(a)
        check(ep)
    rec.update(steps=ep.t, utility=ep.utility, achievements=ep.achievements)
    rec["hashes"] = [binding.trajectory(seed, actions, m)[0] for _ in range(2)]

def attempt(seed):
    rec = {}
    try:
        play(seed, rec)
    except Exception as e:
        rec["error"] = f"{type(e).__name__}: {e}"
    return rec

print(json.dumps({seed: attempt(seed) for seed in json.loads(sys.argv[1])}))
"""
TRAJECTORY_SEEDS = (1, 2, 3)
TRAJECTORY_STEPS = 400
# The trajectory hash of seed TRAJECTORY_SEEDS[0] under its committed action stream, recorded before any scored run
# (L1 review a814d28 F4): a different interpreter, numpy or crafter that changes the World fails P11.
TRAJECTORY_GOLDEN = "f65aed28a596149bb27abda1e82bd2416adb5b22c9131ac7c73a692f3e5f7785"


def _trajectories(*hash_seeds: str) -> list[dict]:
    """TRAJECTORY_RUN in one fresh interpreter per `hash_seeds`, each salting string hashing by its seed. The
    interpreters run concurrently, which halves P11's wall time (L1 STATUS obligation: `make pins` near 10 minutes);
    they share nothing but the tree."""
    children = [subprocess.Popen(proc.python("-c", TRAJECTORY_RUN, json.dumps(TRAJECTORY_SEEDS), str(TRAJECTORY_STEPS)),
                                 cwd=ROOT, env=proc.child_env() | {"PYTHONHASHSEED": h}, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True, preexec_fn=proc.setup(False))
                for h in hash_seeds]
    outs = [(c, *c.communicate()) for c in children]
    for c, _, err in outs:
        if c.returncode:
            raise RuntimeError(f"trajectory child exited {c.returncode}: {err.strip()[-500:]}")
    return [json.loads(out) for _, out, _ in outs]


def p11_crafter_determinism() -> bool:
    """The same seed and action sequence give an identical trajectory hash, twice in one process and across two
    processes with differently salted string hashing, equal for the first seed to the committed golden hash; distinct
    seeds give distinct hashes, so the hash is not constant; every observation the binding emits conforms to the
    manifest; every chunk container holds exactly its live objects; utility is the count of distinct achievements
    (brief 1 section 3, A7)."""
    from worlds.crafter import binding

    expect, ok = _expecter()
    a, b = _trajectories("1", "2")
    components = binding.manifest()["utility"]["components"]
    for seed in map(str, TRAJECTORY_SEEDS):
        expect(a[seed]["violations"] == [], f"seed {seed}: observations conform to the manifest "
                                            f"({a[seed]['violations'][:3]})")
        expect(a[seed]["chunk_departure_count"] == 0,
               f"seed {seed}: every chunk container holds exactly its live objects after reset and every step "
               f"({a[seed]['chunk_departure_count']} departures; first {a[seed]['chunk_departures'][:2]})")
        errors = [r[seed]["error"] for r in (a, b) if "error" in r[seed]]
        expect(not errors, f"seed {seed}: the World plays the action stream without raising ({errors[:1]})")
        if errors:
            continue
        hashes = a[seed]["hashes"] + b[seed]["hashes"]
        expect(len(set(hashes)) == 1, f"seed {seed}: 4 trajectory hashes, 2 per process, {len(set(hashes))} distinct "
                                      f"({a[seed]['steps']} steps; {hashes[0][:16]})")
        ach = a[seed]["achievements"]
        expect(a[seed]["utility"] == len(ach) and set(ach) <= set(components),
               f"seed {seed}: utility {a[seed]['utility']} = |{ach}|, each a declared component")
    golden = a[str(TRAJECTORY_SEEDS[0])].get("hashes", [""])[0]
    expect(golden == TRAJECTORY_GOLDEN, f"seed {TRAJECTORY_SEEDS[0]}: trajectory hash {golden[:16]} is the committed "
                                        f"golden {TRAJECTORY_GOLDEN[:16]}")
    firsts = {a[str(s)].get("hashes", [""])[0] for s in TRAJECTORY_SEEDS}
    expect(len(firsts) == len(TRAJECTORY_SEEDS), f"{len(TRAJECTORY_SEEDS)} seeds give {len(firsts)} distinct hashes")
    hafner = (([set()], 0.0), ([set(components)] * 2, 100.0),
              ([{components[0]}, set()], math.exp(math.log(51) / len(components)) - 1))
    for sets, want in hafner:
        got = binding.hafner_score(sets, components)
        expect(math.isclose(got, want, abs_tol=1e-9), f"Hafner score of {len(sets)} episodes: {got:.6f}, want {want:.6f}")
    return ok()



# P2's probe, run inside a candidate container (brief 1 section 2, P2): it tries to read each judge path it is given,
# to reach the network over IPv4 and IPv6, TCP and UDP, and to write the root file system, and reports each OS errno.
# A control shows the probe is not failing blindly: a file of the image is readable. EROFS and ENETUNREACH name their
# cause, so they need none. It also reports the network interfaces and the cgroup limits the container sees.
PEEK = """
import errno, json, os, socket, sys

def attempt(f):
    try:
        f()
        return "ok"
    except OSError as e:
        return errno.errorcode.get(e.errno, "timeout" if isinstance(e, TimeoutError) else str(e))

def read(p):
    if os.path.isdir(p):
        os.listdir(p)
    else:
        open(p, "rb").read(1)

def write(p):
    with open(p, "w") as f:
        f.write("peek")

def connect(family, kind, addr):
    def go():
        with socket.socket(family, kind) as s:
            s.settimeout(2)
            s.connect(addr)
    return go

def cgroup(name):
    try:
        return open("/sys/fs/cgroup/" + name).read().strip()
    except OSError as e:
        return errno.errorcode.get(e.errno, str(e))

print(json.dumps({
    "read": {p: attempt(lambda p=p: read(p)) for p in json.loads(sys.argv[1])},
    "read_control": attempt(lambda: read("/etc/os-release")),
    "net": {"udp4": attempt(connect(socket.AF_INET, socket.SOCK_DGRAM, ("192.0.2.1", 9))),
            "tcp4": attempt(connect(socket.AF_INET, socket.SOCK_STREAM, ("192.0.2.1", 9))),
            "udp6": attempt(connect(socket.AF_INET6, socket.SOCK_DGRAM, ("2001:db8::1", 9))),
            "tcp6": attempt(connect(socket.AF_INET6, socket.SOCK_STREAM, ("2001:db8::1", 9)))},
    "interfaces": sorted(os.listdir("/sys/class/net")),
    "write_root": attempt(lambda: write("/assize-peek")),
    "cgroup": {n: cgroup(n) for n in ("cpu.max", "memory.max", "memory.swap.max", "pids.max")},
}))
"""
# The errnos by which the OS denies a path: absent from the container's mount namespace, or not permitted.
PATH_DENIALS = frozenset({"ENOENT", "EACCES", "EPERM"})


def p2_peek() -> bool:
    """Under every genuine OCI runtime present (Docker, or rootless Podman with the cpu, memory and pids controllers
    delegated), a candidate container cannot read the judge's paths, has no network interface but loopback and cannot
    reach any address, cannot write its root file system, and sees the cgroup limits of the judge's committed config.
    Each denial is an errno from the OS, not a refusal by convention. At least one runtime must be witnessed; the
    transcript names which (brief 1 section 2, A1 item 2)."""
    from judge import runtime

    expect, ok = _expecter()
    lim = runtime.limits()
    image = runtime.candidate_config()["base_image"]
    paths = [str(p) for p in (ROOT, runtime.CONFIG.parent, runtime.CONFIG, Path(runtime.__file__), context.scratch)]
    expect(all(Path(p).exists() for p in paths), f"every probed judge path exists on the judge's side: {paths}")
    engines = [runtime.engine(rt) for rt in runtime.RUNTIMES]
    for e in engines:
        print(f"  runtime {e.runtime.name}: {'USABLE' if e.usable else 'not usable'}: {e.identity}")
    usable = [e for e in engines if e.usable]
    expect(bool(usable), f"at least one runtime witnessed ({[e.runtime.name for e in usable]})")
    want_cgroup = {"cpu.max": f"{round(lim.cpus * 100000)} 100000", "memory.max": str(lim.memory_mib * 2**20),
                   "memory.swap.max": "0", "pids.max": str(lim.pids)}
    for e in usable:
        rt = e.runtime
        runtime.pull(rt, image)
        name = f"assize-p2-{os.getpid()}-{rt.name}"
        argv = runtime.run_argv(rt, image, lim, name, ["python", "-I", "-c", PEEK, json.dumps(paths)])
        print(f"  {rt.name}$ {' '.join(argv[:-2])} <PEEK> <paths>")
        try:
            out = subprocess.run(argv, capture_output=True, text=True)
        finally:
            subprocess.run(runtime.remove_argv(rt, name), capture_output=True)
        try:
            r = json.loads(out.stdout)
        except json.JSONDecodeError:
            expect(False, f"{rt.name}: the probe ran and reported (exit {out.returncode}; {out.stderr.strip()[-300:]})")
            continue
        print(f"  {rt.name} probe: {json.dumps(r)}")
        n = rt.name
        expect(out.returncode == 0, f"{n}: probe exited 0 ({out.returncode})")
        for p, got in r["read"].items():
            expect(got in PATH_DENIALS, f"{n}: reading {p} denied by the OS ({got})")
        expect(r["read_control"] == "ok", f"{n}: control: a file of the image is readable ({r['read_control']})")
        for kind, got in r["net"].items():
            expect(got == "ENETUNREACH", f"{n}: {kind} connect has no route ({got})")
        expect(r["interfaces"] == ["lo"], f"{n}: the only network interface is loopback ({r['interfaces']})")
        expect(r["write_root"] == "EROFS", f"{n}: writing the root file system is refused read-only ({r['write_root']})")
        for k, v in want_cgroup.items():
            expect(r["cgroup"][k] == v, f"{n}: {k} is {r['cgroup'][k]!r}, from config {v!r}")
    return ok()

# P3 and P10 play the Crafter World cut to a few steps, so that each case costs seconds: the loop is the judge's own,
# and the World's length is the only thing the fixture changes (brief 1 section 2).
LOOP_STEPS = 5


def _short_crafter(n: int):
    from worlds.crafter import binding

    for seed in range(1, n + 1):
        ep = binding.Episode(seed)
        ep._env._length = LOOP_STEPS
        yield ep


def _candidates(rt) -> set[str]:
    from judge import episodes

    return set(episodes.listed_prefix(rt, "assize-candidate-"))


def _usable_runtimes(expect):
    """Every usable runtime, each named in the transcript, with the base image present; at least one is required."""
    from judge import runtime

    engines = [runtime.engine(rt) for rt in runtime.RUNTIMES]
    for e in engines:
        print(f"  runtime {e.runtime.name}: {'USABLE' if e.usable else 'not usable'}: {e.identity}")
    usable = [e.runtime for e in engines if e.usable]
    expect(bool(usable), f"at least one runtime witnessed ({[rt.name for rt in usable]})")
    image = runtime.candidate_config()["base_image"]
    for rt in usable:
        runtime.pull(rt, image)
    return usable, image


def _removing_strays(rt, before: set[str]) -> list[str]:
    """Force-remove every candidate container that appeared since `before`, so that a failing case leaves nothing
    behind, and return their names."""
    from judge import runtime

    strays = sorted(_candidates(rt) - before)
    for name in strays:
        subprocess.run(runtime.remove_argv(rt, name), capture_output=True)
    return strays


def _each_runtime(usable, case, expect) -> None:
    """Run `case(rt, expect, say)` for every usable runtime at once, each in its own thread, and print each runtime's
    transcript whole, in runtime order. Distinct runtimes are distinct engines with their own containers (`_docker`
    admits only a Docker server), so the cases cannot see each other's containers; CPU time measured from a cgroup does
    not depend on what else runs. Running them together keeps `pins` CI, where Docker and Podman are both usable,
    within its job timeout. An exception in a case is re-raised after every transcript is printed."""
    from concurrent.futures import ThreadPoolExecutor

    def one(rt):
        lines: list[str] = []
        failures: list[str] = []

        def say(*parts) -> None:
            lines.append(" ".join(str(x) for x in parts))

        def exp(cond: bool, what: str) -> None:
            say(f"  [{'ok' if cond else 'FAIL'}] {what}")
            if not cond:
                failures.append(what)

        try:
            case(rt, exp, say)
            return lines, failures, None
        except BaseException as e:  # noqa: BLE001 - re-raised below, after the transcripts
            return lines, failures, e

    with ThreadPoolExecutor(max_workers=max(len(usable), 1)) as pool:
        results = list(pool.map(one, usable))
    for rt, (lines, failures, raised) in zip(usable, results):
        for line in lines:
            print(line)
        expect(not failures and raised is None, f"{rt.name}: every assertion above held ({len(failures)} failed)")
    for _, _, raised in results:
        if raised is not None:
            raise raised


def p3_survivorship() -> bool:
    """Every episode is recorded with its termination code, failures included: under every usable runtime, a fixture
    candidate that crashes, garbles its reply, plays an illegal action, stalls a step or overruns the episode yields
    exactly one record per requested episode, in order, each with that failure's code; a polite candidate's episodes
    end as the World ends them. No candidate container is left listed (brief 1 section 2)."""
    import dataclasses

    from harness.fixtures import candidates
    from judge import episodes
    from worlds.crafter import binding

    expect, ok = _expecter()
    t = episodes.timeouts()
    print(f"  timeouts from judge/config.toml: {t}")
    # Each failure ends its episode on the first step except `slow`, whose every reply takes 0.5 s: an episode deadline
    # of 1.2 s ends it at step 2 or 3 while each step stays within step_s. `stubborn` never replies; a 2 s step
    # deadline bounds the pin's wall time, and step_s from config is the judge's, untouched.
    cases = (("polite", 2, t, "truncated"), ("crash", 3, t, "crash"), ("garbled", 2, t, "invalid_reply"),
             ("illegal", 2, t, "illegal_action"), ("slow", 2, dataclasses.replace(t, episode_s=1.2), "episode_timeout"),
             ("stubborn", 2, dataclasses.replace(t, step_s=2.0), "step_timeout"))
    usable, image = _usable_runtimes(expect)
    def case(rt, expect, say):
        before = _candidates(rt)
        for behaviour, n, tt, want in cases:
            records = episodes.run(rt, image, _short_crafter(n), binding.manifest(),
                                   command=candidates.command(behaviour), t=tt)
            say(f"  {rt.name} {behaviour}: {json.dumps(records)}")
            expect(len(records) == n and [r["episode"] for r in records] == list(range(n)),
                   f"{rt.name} {behaviour}: {len(records)} of {n} requested episodes recorded, in order")
            expect(all(r["termination"] == want for r in records),
                   f"{rt.name} {behaviour}: every termination is {want} ({[r['termination'] for r in records]})")
            if want == "truncated":
                expect(all(r["steps"] == LOOP_STEPS for r in records),
                       f"{rt.name} {behaviour}: every episode ran its {LOOP_STEPS} steps")
        strays = _removing_strays(rt, before)
        expect(not strays, f"{rt.name}: no candidate container listed after the cases ({strays})")

    _each_runtime(usable, case, expect)
    return ok()


def p4_measured_compute() -> bool:
    """Under every usable runtime, the judge's measured compute comes from the container's cgroup, never from the
    candidate: a fixture that busy-loops a known CPU time per step and self-reports zero on stderr is measured at least
    that known time in each of two episodes in one container, and less than two episodes' worth, so each episode is
    charged its own; its wall-clock is at least the known time; its peak memory at least the block it filled and freed
    between samples; nothing of it unmeasured. A fixture that busy-loops and then crashes is recorded crash, with its
    known CPU time either measured or covered by the configured CPUs times its unmeasured stretch (brief 1 section 2)."""
    from harness.fixtures import candidates
    from judge import episodes, runtime
    from worlds.crafter import binding

    expect, ok = _expecter()
    lim = runtime.limits()
    known = LOOP_STEPS * candidates.BUSY_S
    block = candidates.BUSY_MIB << 20
    print(f"  known: {known} CPU s per busy episode ({LOOP_STEPS} steps of {candidates.BUSY_S} s); "
          f"{block} bytes filled and freed per step; limits {lim}")
    usable, image = _usable_runtimes(expect)
    def case(rt, expect, say):
        before = _candidates(rt)
        records = episodes.run(rt, image, _short_crafter(2), binding.manifest(), command=candidates.command("busy"))
        say(f"  {rt.name} busy: {json.dumps(records)}")
        expect([(r["termination"], r["steps"]) for r in records] == [("truncated", LOOP_STEPS)] * 2,
               f"{rt.name} busy: two episodes of {LOOP_STEPS} steps, ended by the World")
        for r in records:
            used, n = r.get("compute", {}), f"{rt.name} busy episode {r['episode']}"
            expect(known <= used.get("cpu_s", -1) < 2 * known,
                   f"{n}: measured CPU {used.get('cpu_s')} s is at least the known {known} s and less than two "
                   f"episodes' {2 * known} s")
            expect(used.get("wall_s", -1) >= known, f"{n}: wall-clock {used.get('wall_s')} s is at least {known} s")
            expect(used.get("peak_memory_bytes", -1) >= block,
                   f"{n}: peak memory {used.get('peak_memory_bytes')} bytes is at least the {block} filled")
            expect(used.get("unmeasured_s") == 0, f"{n}: nothing unmeasured ({used.get('unmeasured_s')} s)")
        records = episodes.run(rt, image, _short_crafter(1), binding.manifest(),
                               command=candidates.command("busy_crash"))
        say(f"  {rt.name} busy_crash: {json.dumps(records)}")
        used = records[0].get("compute", {}) if records else {}
        expect([r["termination"] for r in records] == ["crash"], f"{rt.name} busy_crash: recorded crash")
        expect(used.get("cpu_s", -1) + lim.cpus * used.get("unmeasured_s", -1) >= candidates.BUSY_S,
               f"{rt.name} busy_crash: measured {used.get('cpu_s')} s plus {lim.cpus} CPUs times unmeasured "
               f"{used.get('unmeasured_s')} s covers the known {candidates.BUSY_S} s")
        strays = _removing_strays(rt, before)
        expect(not strays, f"{rt.name}: no candidate container listed after the cases ({strays})")

    _each_runtime(usable, case, expect)
    return ok()


def p10_container_teardown() -> bool:
    """Under every usable runtime, a candidate container whose processes ignore SIGTERM, a child in its own session
    among them, is killed and removed: the runtime lists nothing of it afterwards, both when torn down directly and
    when its stalled step times out, which is then recorded step_timeout, not leaked (brief 1 A4 item 5)."""
    import dataclasses
    import time

    from harness.fixtures import candidates
    from judge import episodes, runtime
    from worlds.crafter import binding

    expect, ok = _expecter()
    # The pin's own bound on how long teardown may take, so that a mutant that never removes fails in seconds.
    t = dataclasses.replace(episodes.timeouts(), step_s=2.0, teardown_s=5.0)
    usable, image = _usable_runtimes(expect)
    def case(rt, expect, say):
        before = _candidates(rt)
        c = episodes.Container(rt, image, runtime.limits(), candidates.command("stubborn"))
        try:
            c.call("begin_episode", {"schema_version": episodes.SCHEMA_VERSION, "manifest": binding.manifest()}, t,
                   time.monotonic() + t.episode_s)
            c._send("step", {"t": 0, "observation": {}, "legal_actions": [0]})
            time.sleep(1.0)
            term = subprocess.run([rt.binary, "kill", "--signal=TERM", c.name], capture_output=True, text=True)
            time.sleep(2.0)
            running = episodes.listed(rt, c.name, running=True)
            expect(term.returncode == 0 and running == [c.name],
                   f"{rt.name}: control: the stubborn container survives SIGTERM (kill exit {term.returncode}; "
                   f"running {running})")
        finally:
            gone = c.teardown(t)
        expect(gone and not episodes.listed(rt, c.name), f"{rt.name}: torn down directly, {c.name} is not listed")
        records = episodes.run(rt, image, _short_crafter(1), binding.manifest(), command=candidates.command("stubborn"),
                               t=t)
        say(f"  {rt.name} stubborn: {json.dumps(records)}")
        expect([r["termination"] for r in records] == ["step_timeout"],
               f"{rt.name}: the stalled episode is recorded step_timeout ({[r['termination'] for r in records]})")
        strays = _removing_strays(rt, before)
        expect(not strays, f"{rt.name}: the runtime lists no candidate container afterwards ({strays})")

    _each_runtime(usable, case, expect)
    return ok()


# P7's malformed predictors (brief 1 section 2): each must end its episode invalid_reply at its first step, unscored.
MALFORMED = ("undeclared", "short", "zeros", "nan")


def _forecaster_observations() -> list[dict]:
    """The observations of the `forecaster` fixture's one short episode, replayed with the same seed and actions."""
    ep = next(_short_crafter(1))
    obs = [ep.observation]
    while not ep.done:
        obs.append(ep.step(ep.legal_actions[0]))
    return obs


def _forecaster_predicted(i: int, s: list, v) -> list[float]:
    """What the `forecaster` fixture predicts for target `i` of support `s` when its field's current value is `v`."""
    return [[float(x == v) for x in s], [0.0 if x == v else 1 / (len(s) - 1) for x in s], [1 / len(s)] * len(s)][i % 3]


def _forecaster_summary(targets) -> dict:
    """What the judge must record for the `forecaster` fixture over one short episode, derived here by replaying the
    same seed and actions in the binding and scoring each step by definition, independently of `judge/scoring.py`."""
    obs = _forecaster_observations()
    predicted = _forecaster_predicted

    def one(i: int, tg: dict) -> dict:
        steps = len(obs) - 1
        if i == len(targets) - 1:
            return {"scored": 0, "missing": steps, "infinite": 0, "finite_sum": 0.0, "log_loss": 0.0}
        s, f = tg["support"], tg["field"]
        qs = [predicted(i, s, a[f])[s.index(b[f])] for a, b in zip(obs, obs[1:])]
        finite = math.fsum(-math.log(q) for q in qs if q > 0)
        inf = sum(q == 0 for q in qs)
        return {"scored": steps, "missing": 0, "infinite": inf, "finite_sum": finite,
                "log_loss": "+inf" if inf else finite}

    return {tg["name"]: one(i, tg) for i, tg in enumerate(targets)}


def _forecaster_calibration(targets, bins: int) -> dict:
    """The calibration the judge must record for the `forecaster` fixture over one short episode, derived here by
    definition, independently of `judge/scoring.py`: per target, every scored step adds, for every support value, one
    count to the bin whose edges enclose the probability it put on that value (the last bin closed at 1), a hit if that
    value was realised, and that probability; and the entropy in nats of its distribution. The last target is missing."""
    obs = _forecaster_observations()
    edges = [b / bins for b in range(1, bins)]

    def one(i: int, tg: dict) -> dict:
        s, f = tg["support"], tg["field"]
        steps = [] if i == len(targets) - 1 else [(_forecaster_predicted(i, s, a[f]), b[f]) for a, b in zip(obs, obs[1:])]
        cells = {(v, b): [] for v in range(len(s)) for b in range(bins)}
        for p, realised in steps:
            for v, x in enumerate(s):
                cells[(v, sum(e <= p[v] for e in edges))].append((p[v], x == realised))
        h = [-math.fsum(q * math.log(q) for q in p if q > 0) for p, _ in steps]
        table = {k: [[g(cells[(v, b)]) for b in range(bins)] for v in range(len(s))]
                 for k, g in (("n", len), ("hits", lambda c: sum(1 for _, r in c if r)),
                              ("p_sum", lambda c: math.fsum(q for q, _ in c)))}
        return {"entropy_sum": math.fsum(h), "mean_entropy": math.fsum(h) / len(h) if h else None,
                "reliability": {"bins": bins} | table}

    return {tg["name"]: one(i, tg) for i, tg in enumerate(targets)}


def p13_calibration() -> bool:
    """Each declared target's calibration (brief 1 A4 item 3; review c2a87f6 F5): the judge's scoring of the
    `forecaster` fixture's episode, replayed here step by step, equals the calibration derived by definition: the
    entropies' sum and mean, none where the target is missing, and a reliability table over the declared support in
    the committed bins, in which every scored step, an infinite-loss step included, enters every support value's row
    once, so each row's counts sum to `scored`. P7 checks the record of the same episode, played through the judge's
    loop under every usable runtime, against the same derivation."""
    from judge import episodes, scoring
    from worlds.crafter import binding

    expect, ok = _expecter()
    m = binding.manifest()
    targets, bins = m["targets"], episodes.calibration_bins()
    obs = _forecaster_observations()
    steps = [scoring.step_predictions({tg["name"]: _forecaster_predicted(i, tg["support"], a[tg["field"]])
                                       for i, tg in enumerate(targets[:-1])}, targets, b)
             for a, b in zip(obs, obs[1:])]
    summary = scoring.summary([scoring.step_losses({n: v[0] for n, v in s.items() if v is not None}, targets, b)
                               for s, b in zip(steps, obs[1:])], targets)
    got, want = scoring.calibration(steps, targets, bins), _forecaster_calibration(targets, bins)
    print(f"  bins {bins}; summary {json.dumps(summary)}")
    expect(any(w["infinite"] == w["scored"] > 0 for w in summary.values()),
           "non-vacuous: some target puts zero mass on the realised value at every scored step")
    expect(any(w["missing"] == w["scored"] + w["missing"] > 0 for w in summary.values()),
           "non-vacuous: some target is missing at every step")
    for tg in targets:
        name, g, w = tg["name"], got.get(tg["name"], {}), want[tg["name"]]
        print(f"  {name}: recorded {json.dumps(g)}")
        expect(g == w, f"{name}: calibration equals its derivation" + ("" if g == w else f" {json.dumps(w)}"))
        rows = g.get("reliability", {}).get("n", [])
        expect(len(rows) == len(tg["support"]) and all(sum(r) == summary[name]["scored"] for r in rows),
               f"{name}: each of the {len(tg['support'])} support values' bin counts sums to scored "
               f"({summary[name]['scored']}): {[sum(r) for r in rows]}")
        hits = g.get("reliability", {}).get("hits", [])
        expect(sum(map(sum, hits)) == summary[name]["scored"],
               f"{name}: each scored step realises one value: {sum(map(sum, hits))} hits")
    return ok()


def p7_infinite_loss() -> bool:
    """Under every usable runtime, a candidate's predictions are scored per declared target per step against the
    World's next observation: zero mass on the realised value is recorded +inf and counted, never clipped; an omitted
    target is recorded missing, never imputed; every record equals the one derived independently by replaying the
    episode. A prediction naming an undeclared target, of the wrong length, not summing to one, or carrying NaN ends
    its episode invalid_reply before the World advances (brief 1 section 2)."""
    from harness.fixtures import candidates
    from judge import episodes
    from worlds.crafter import binding

    expect, ok = _expecter()
    m = binding.manifest()
    want = _forecaster_summary(m["targets"])
    calibration = _forecaster_calibration(m["targets"], episodes.calibration_bins())
    print(f"  derived: {json.dumps(want)}")
    expect(any(w["infinite"] == w["scored"] > 0 for w in want.values()),
           "non-vacuous: some target puts zero mass on the realised value at every scored step")
    expect(any(w["infinite"] == 0 and w["finite_sum"] > 0 for w in want.values()),
           "non-vacuous: some target has a positive finite log-loss")
    expect(any(w["missing"] == LOOP_STEPS for w in want.values()), "non-vacuous: some target is missing at every step")
    usable, image = _usable_runtimes(expect)
    def case(rt, expect, say):
        before = _candidates(rt)
        records = episodes.run(rt, image, _short_crafter(1), m, command=candidates.command("forecaster"))
        say(f"  {rt.name} forecaster: {json.dumps(records)}")
        expect([(r["termination"], r["steps"]) for r in records] == [("truncated", LOOP_STEPS)],
               f"{rt.name} forecaster: one episode of {LOOP_STEPS} steps, ended by the World")
        got = records[0].get("prediction", {}) if records else {}
        for name, w in want.items():
            expect(got.get(name) == w, f"{rt.name} forecaster {name}: recorded {got.get(name)}, derived {w}")
        cal = records[0].get("calibration") if records else None
        expect(cal == calibration, f"{rt.name} forecaster: the recorded calibration equals P13's derivation")
        for behaviour in MALFORMED:
            records = episodes.run(rt, image, _short_crafter(1), m, command=candidates.command(behaviour))
            say(f"  {rt.name} {behaviour}: {json.dumps(records)}")
            expect([(r["termination"], r["steps"]) for r in records] == [("invalid_reply", 0)],
                   f"{rt.name} {behaviour}: invalid_reply at the first step, before the World advances")
            expect(all(v["scored"] == 0 for r in records for v in r["prediction"].values()),
                   f"{rt.name} {behaviour}: nothing scored")
        strays = _removing_strays(rt, before)
        expect(not strays, f"{rt.name}: no candidate container listed after the cases ({strays})")

    _each_runtime(usable, case, expect)
    return ok()



# P12's derivation of the committed price (brief 1 A4 item 4): an episode exhausting every allowance is charged the
# smallest effect brief 1's FIT criterion requires the court to detect, half for CPU and half for memory.
FIT_DELTA = 0.5


def _priced(used: dict, cfg: dict) -> dict:
    """What the judge must charge for `used`, derived here from `judge/config.toml` and the rule `judge/price.py`
    states, independently of that module: the unmeasured stretch at the configured CPUs and memory, the peak memory
    over the rest, in gigabytes of 1e9 bytes."""
    rate, lim = cfg["price"]["crafter"], cfg["candidate"]
    unmeasured = used["unmeasured_s"]
    cpu = rate["cpu_s"] * (used["cpu_s"] + lim["cpus"] * unmeasured)
    memory = rate["memory_gb_s"] * (used["peak_memory_bytes"] * max(used["wall_s"] - unmeasured, 0.0)
                                    + lim["memory_mib"] * 2 ** 20 * unmeasured) / 1e9
    return {"cpu": cpu, "memory": memory, "total": cpu + memory}


def _same(a: dict | None, b: dict) -> bool:
    """`a` equals `b` term by term up to the rounding of a few double-precision operations (a derived bound)."""
    return isinstance(a, dict) and a.keys() == b.keys() and all(
        math.isclose(a[k], b[k], rel_tol=8 * sys.float_info.epsilon, abs_tol=0.0) for k in b)


def p12_compute_price() -> bool:
    """Under every usable runtime, every episode record carries its compute priced in Crafter achievements at the
    rates `judge/config.toml` commits, which equal their stated derivation. The peak memory's scope is stated in the
    record as the container's since its start, and the price follows that scope: a fixture filling a block in its first
    episode only is charged that block's high-water mark in its second episode too. What the judge could not measure,
    the stretch after a crashed container's last read, is charged at the configured CPUs and memory (brief 1 A4 item 4;
    review 42d7331 F4)."""
    import tomllib

    from harness.fixtures import candidates
    from judge import episodes
    from worlds.crafter import binding

    expect, ok = _expecter()
    cfg = tomllib.loads((ROOT / "judge" / "config.toml").read_text())
    rate, lim, t = cfg["price"]["crafter"], cfg["candidate"], cfg["timeouts"]
    derived = {"cpu_s": FIT_DELTA / 2 / (lim["cpus"] * t["episode_s"]),
               "memory_gb_s": FIT_DELTA / 2 / (lim["memory_mib"] * 2 ** 20 / 1e9 * t["episode_s"])}
    print(f"  committed price {rate}; derived {derived}")
    expect(_same(rate, derived), "the committed price equals its derivation from FIT's delta and the allowances")
    block = candidates.BUSY_MIB << 20
    usable, image = _usable_runtimes(expect)
    def case(rt, expect, say):
        before = _candidates(rt)
        records = episodes.run(rt, image, _short_crafter(2), binding.manifest(), command=candidates.command("hog_once"))
        say(f"  {rt.name} hog_once: {json.dumps(records)}")
        expect([(r["termination"], r["steps"]) for r in records] == [("truncated", LOOP_STEPS)] * 2,
               f"{rt.name} hog_once: two episodes of {LOOP_STEPS} steps in one container, ended by the World")
        crashed = episodes.run(rt, image, _short_crafter(1), binding.manifest(),
                               command=candidates.command("busy_crash"))
        say(f"  {rt.name} busy_crash: {json.dumps(crashed)}")
        expect([r["termination"] for r in crashed] == ["crash"], f"{rt.name} busy_crash: recorded crash")
        for r in records:
            used, n = r.get("compute", {}), f"{rt.name} hog_once episode {r['episode']}"
            expect(used.get("peak_memory_scope") == "container_since_start",
                   f"{n}: peak memory's scope stated as container_since_start ({used.get('peak_memory_scope')})")
            expect(used.get("peak_memory_bytes", -1) >= block,
                   f"{n}: peak memory {used.get('peak_memory_bytes')} bytes is at least the {block} filled in episode 0")
            expect(used.get("wall_s", -1) > used.get("unmeasured_s", 0) == 0,
                   f"{n}: measured throughout ({used.get('wall_s')} s wall, {used.get('unmeasured_s')} s unmeasured)")
        for r in records + crashed:
            want = _priced(r["compute"], cfg) if "peak_memory_bytes" in r.get("compute", {}) else {}
            expect(_same(r.get("price"), want),
                   f"{rt.name} {r['termination']} episode {r['episode']}: price {r.get('price')}, derived {want}")
        used = crashed[0].get("compute", {}) if crashed else {}
        expect(used.get("unmeasured_s", 0) > 0,
               f"{rt.name} busy_crash: non-vacuous: {used.get('unmeasured_s')} s unmeasured after the container's last read")
        strays = _removing_strays(rt, before)
        expect(not strays, f"{rt.name}: no candidate container listed after the cases ({strays})")

    _each_runtime(usable, case, expect)
    return ok()

# P9's records (brief 1 A4 item 1): two requests of judge-shaped episode records, an infinite log-loss included, so
# the canonical serialisation is exercised on the strings and floats a real record carries.
P9_REQUESTS = (
    ("p9-request-a", [{"episode": i, "termination": c, "detail": "", "steps": s, "utility": u,
                       "prediction": {"inventory_wood": {"scored": s, "missing": 0, "infinite": f, "finite_sum": 1.5,
                                                         "log_loss": "+inf" if f else 1.5}}}
                      for i, (c, s, u, f) in enumerate((("terminal", 120, 3, 0), ("crash", 7, 0, 1),
                                                         ("truncated", 10000, 5, 0)))]),
    ("p9-request-b", [{"episode": 0, "termination": "step_timeout", "detail": "no reply", "steps": 2, "utility": 1,
                       "prediction": {}}]),
)
CHAIN_FIELDS = ("request_id", "prev_sha256", "sha256")


def _verify_cli(led: Path, private: Path) -> tuple[int, str]:
    """The judge's verification subcommand, run as the judge runs it, in a child interpreter."""
    r = subprocess.run(proc.python("-m", "judge", "verify", str(led), str(private)), cwd=ROOT, env=proc.child_env(),
                       capture_output=True, text=True, timeout=120)
    return r.returncode, (r.stdout + r.stderr).strip()


def _resigned(private: Path, rows: list[dict], led: Path) -> None:
    """Rewrite `led` as `rows` and re-sign heads matching them with the judge's own key: a forger who holds the key,
    so that only the chain itself can expose the tamper."""
    import hashlib
    import hmac

    key = (private / "key").read_bytes()
    data = b"".join(json.dumps(r, sort_keys=True, separators=(",", ":")).encode() + b"\n" for r in rows)
    led.write_bytes(data)
    heads, size = [], 0
    for rid in dict.fromkeys(r["request_id"] for r in rows):
        mine = [r for r in rows if r["request_id"] == rid]
        size += sum(len(json.dumps(r, sort_keys=True, separators=(",", ":")).encode()) + 1 for r in mine)
        h = {"ledger": led.name, "request_id": rid, "records": len(mine), "head": mine[-1]["sha256"], "bytes": size}
        mac = hmac.new(key, json.dumps(h, sort_keys=True, separators=(",", ":")).encode(), hashlib.sha256).hexdigest()
        heads.append(json.dumps(h | {"mac": mac}, sort_keys=True, separators=(",", ":")) + "\n")
    (private / "heads.jsonl").write_text("".join(heads))


def _rechained(rows: list[dict], first_prev) -> list[dict]:
    """`rows` re-chained by definition, each request's first record linking to `first_prev(request_id)`."""
    import hashlib

    out, prev, rid = [], None, None
    for r in rows:
        if r["request_id"] != rid:
            rid, prev = r["request_id"], first_prev(r["request_id"])
        rec = {k: v for k, v in r.items() if k != "sha256"} | {"prev_sha256": prev}
        prev = hashlib.sha256(json.dumps(rec, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        out.append(rec | {"sha256": prev})
    return out


def p9_ledger_tamper() -> bool:
    """The judge's ledger is tamper-evident (brief 1 A4 item 1; A5 F4). Two requests appended by `judge.ledger` hold
    exactly the records given, in order; each record links by `prev_sha256` to the previous record's `sha256`, the
    first to the SHA-256 of its request_id, each `sha256` the digest of its canonical serialisation, all derived here
    by definition; the first request's bytes are untouched by the second (O_APPEND, never rewritten); and `python -m
    judge verify` passes it. Every tamper fails verification: a record dropped, a utility altered, extra records, a
    request removed, a forged head without the key, and, with the key in a forger's hands, a chain rebuilt from the
    empty string or with a record left out. A request_id is written once."""
    import hashlib

    from judge import ledger

    expect, ok = _expecter()
    work = Path(tempfile.mkdtemp(prefix="assize-p9-", dir=context.scratch))
    try:
        led, private = work / "ledger.jsonl", work / "private"
        (a_id, a), (b_id, b) = P9_REQUESTS
        try:
            ledger.append(led, private, a_id, a)
            first = led.read_bytes()
            ledger.append(led, private, b_id, b)
            written = led.read_bytes()
            rows = [json.loads(line) for line in written.splitlines()]
        except (ValueError, OSError) as e:
            expect(False, f"the judge writes two requests to a ledger that parses as JSONL ({type(e).__name__}: {e})")
            return ok()
        expect(written.startswith(first), f"request a's {len(first)} bytes unchanged by request b (never rewritten)")
        expect([{k: v for k, v in r.items() if k not in CHAIN_FIELDS} for r in rows] == a + b,
               f"the ledger holds exactly the {len(a) + len(b)} records given, in order, utilities included: "
               f"{[r.get('utility') for r in rows]}")
        expect([r.get("request_id") for r in rows] == [a_id] * len(a) + [b_id] * len(b), "each record names its request")
        derived = _rechained(rows, lambda rid: hashlib.sha256(rid.encode()).hexdigest())
        expect(rows == derived, "every prev_sha256 and sha256 equals its derivation: first records from the SHA-256 "
                                "of the request_id, each next from the previous sha256")
        code, out = _verify_cli(led, private)
        print("  " + out.replace("\n", "\n  "))
        expect(code == 0, f"verify passes the ledger as written (exit {code})")
        try:
            ledger.append(led, private, a_id, a)
            expect(False, "a request_id already written is refused")
        except ValueError as e:
            expect(led.read_bytes() == written, f"a request_id already written is refused, ledger unchanged ({e})")

        snapshot = {p.name: p.read_bytes() for p in (led, private / "heads.jsonl")}

        def tampered(name: str, act) -> None:
            act()
            code, out = _verify_cli(led, private)
            print(f"  {name}: " + out.replace("\n", "\n    "))
            expect(code == 1, f"{name}: verification fails (exit {code})")
            led.write_bytes(snapshot[led.name])
            (private / "heads.jsonl").write_bytes(snapshot["heads.jsonl"])

        def lines(keep) -> bytes:
            return b"".join(line + b"\n" for i, line in enumerate(written.splitlines()) if keep(i))

        def utility_altered() -> None:
            out = list(rows)
            out[1] = out[1] | {"utility": out[1]["utility"] + 1}
            led.write_bytes(b"".join(ledger.canonical(r) + b"\n" for r in out))

        def forged_head() -> None:
            import hmac
            out = _rechained([r | {"utility": 99} if i == 0 else r for i, r in enumerate(rows)],
                             lambda rid: hashlib.sha256(rid.encode()).hexdigest())
            _resigned(private, out, led)
            heads = [json.loads(h) for h in (private / "heads.jsonl").read_text().splitlines()]
            (private / "heads.jsonl").write_text("".join(
                json.dumps(h | {"mac": hmac.new(b"not the judge's key", ledger.canonical(
                    {k: v for k, v in h.items() if k != "mac"}), hashlib.sha256).hexdigest()}) + "\n" for h in heads))

        tampered("record_dropped", lambda: led.write_bytes(lines(lambda i: i != 1)))
        tampered("last_record_dropped", lambda: led.write_bytes(lines(lambda i: i != len(rows) - 1)))
        tampered("utility_altered", utility_altered)
        tampered("record_appended", lambda: led.write_bytes(written + ledger.canonical(
            _rechained(rows + [rows[-1] | {"episode": 1}], lambda rid: hashlib.sha256(rid.encode()).hexdigest())[-1])
            + b"\n"))
        tampered("request_removed", lambda: led.write_bytes(lines(lambda i: i < len(a))))
        tampered("forged_head", forged_head)
        tampered("rechained_from_empty_with_key", lambda: _resigned(private, _rechained(rows, lambda rid: ""), led))
        tampered("dropped_and_resigned_with_key", lambda: _resigned(private, [r for i, r in enumerate(rows) if i != 1],
                                                                    led))
        code, _ = _verify_cli(led, private)
        expect(code == 0, f"the restored ledger verifies again (exit {code}), so each failure above was the tamper's")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return ok()


PINS = [
    Pin("P0", "surviving mutants are reported and fail the suite",
        p0_survivors_reported, (Mutant("survivors_ignored", _edits("P0_survivors_ignored")),)),
    Pin("P0b", "no code reads a mutant or test variable from the environment",
        p0b_no_switches, (Mutant("env_switch", _edits("P0b_env_switch")),)),
    Pin("P0c", "a failing clean check is recorded and fails the suite",
        p0c_clean_failure, (Mutant("clean_failures_ignored", _edits("P0c_clean_failures_ignored")),)),
    Pin("P0d", "errors and timeouts are INCONCLUSIVE, counted in the denominator, and fail the suite",
        p0d_inconclusive, (Mutant("inconclusive_dropped", _edits("P0d_inconclusive_dropped")),)),
    Pin("P0e", "a registry with a mutant-less pin, a duplicated name or a malformed edit is refused",
        p0e_registry_validation, (Mutant("validation_off", _edits("P0e_validation_off")),)),
    Pin("P0f", "a mutant whose twin fails is NON-CAUSAL and fails the suite",
        p0f_non_causal, (Mutant("twin_ignored", _edits("P0f_twin_ignored")),)),
    Pin("P0g", "an anchor that does not occur exactly once is STALE and fails the suite",
        p0g_stale, (Mutant("stale_ignored", _edits("P0g_stale_ignored")),)),
    Pin("P0h", P0H_SCOPE,
        p0h_timeouts_leave_nothing, (Mutant("death_signal_reverted", _edits("P0h_death_signal_reverted")),
                                     Mutant("scratch_kept", _edits("P0h_scratch_kept")),
                                     Mutant("leaked_not_counted", _edits("P0h_leaked_not_counted")),
                                     Mutant("subreaper_not_set", _edits("P0h_subreaper_not_set")),
                                     Mutant("sweep_skipped", _edits("P0h_sweep_skipped")))),
    Pin("P0i", "a same-length edit landing in the second a bytecode cache recorded takes effect in a copy",
        p0i_no_stale_bytecode, (Mutant("pycache_top_level_only", _edits("P0i_pycache_top_level_only")),
                                 Mutant("pycache_prefix_unset", _edits("P0i_pycache_prefix_unset")))),
    Pin("P0j", "host facts lacking load averages, cpuset, runner version or podman runtime are not a measurement",
        p0j_host_facts_complete, (Mutant("incomplete_facts_accepted", _edits("P0j_incomplete_facts_accepted")),)),
    Pin("P0k", "a forecasts.jsonl resolution lacking id, ts, proposer or outcome, or matching no forecast, is rejected",
        p0k_forecast_ledger, (Mutant("proposer_check_dropped", _edits("P0k_proposer_check_dropped")),)),
    Pin("P0l", "a verdict citing a pins run on another sha, or one not concluded success, is rejected",
        p0l_ci_claims, (Mutant("sha_comparison_skipped", _edits("P0l_sha_comparison_skipped")),)),
    Pin("P0m", "a commit touching an entrenched path without a guy Proposer is rejected; every party is read",
        p0m_commit_proposers, (Mutant("trailer_check_disabled", _edits("P0m_trailer_check_disabled")),
                                Mutant("first_proposer_only", _edits("P0m_first_proposer_only")),
                                Mutant("exemption_unkeyed", _edits("P0m_exemption_unkeyed")),
                                Mutant("exemption_party_unchecked", _edits("P0m_exemption_party_unchecked")))),
    Pin("P2", "a candidate container cannot read judge paths or reach the network; root read-only; config limits",
        p2_peek, (Mutant("network_enabled", _edits("P2_network_enabled")),
                  Mutant("judge_mounted", _edits("P2_judge_mounted")),
                  Mutant("rootfs_writable", _edits("P2_rootfs_writable")),
                  Mutant("memory_limit_dropped", _edits("P2_memory_limit_dropped")))),
    Pin("P3", "every requested episode is recorded with its termination code, failures included",
        p3_survivorship, (Mutant("failures_dropped", _edits("P3_failures_dropped")),)),
    Pin("P4", "an episode's CPU and peak memory are measured from its container's cgroup, never self-reported",
        p4_measured_compute, (Mutant("self_reported", _edits("P4_self_reported")),
                              Mutant("client_rusage", _edits("P4_client_rusage")),
                              Mutant("not_differenced", _edits("P4_not_differenced")),
                              Mutant("peak_from_current", _edits("P4_peak_from_current")))),
    Pin("P7", "zero mass on a realised outcome is recorded +inf, never clipped; missing is never imputed",
        p7_infinite_loss, (Mutant("clipped", _edits("P7_clipped")),
                           Mutant("missing_imputed", _edits("P7_missing_imputed")),
                           Mutant("sum_unchecked", _edits("P7_sum_unchecked")))),
    Pin("P13", "every scored step, +inf included, enters each support value's reliability row; entropy is never imputed",
        p13_calibration, (Mutant("infinite_dropped", _edits("P13_infinite_dropped")),
                          Mutant("realised_row_only", _edits("P13_realised_row_only")),
                          Mutant("entropy_missing_imputed", _edits("P13_entropy_missing_imputed")))),
    Pin("P9", "a ledger record dropped, altered or rechained, or a head forged, fails the judge's verification",
        p9_ledger_tamper, (Mutant("record_dropped", _edits("P9_record_dropped")),
                           Mutant("utility_altered", _edits("P9_utility_altered")),
                           Mutant("chain_update_skipped", _edits("P9_chain_update_skipped")),
                           Mutant("opened_for_rewrite", _edits("P9_opened_for_rewrite")),
                           Mutant("genesis_empty", _edits("P9_genesis_empty")),
                           Mutant("signature_unchecked", _edits("P9_signature_unchecked")))),
    Pin("P12", "every episode's compute is priced by the committed rule; peak memory's scope is stated and followed",
        p12_compute_price, (Mutant("peak_differenced", _edits("P12_peak_differenced")),
                            Mutant("unmeasured_free", _edits("P12_unmeasured_free")))),
    Pin("P10", "a candidate container ignoring SIGTERM is killed and removed on timeout; the runtime lists nothing",
        p10_container_teardown, (Mutant("removal_skipped", _edits("P10_removal_skipped")),)),
    Pin("P6", "no manifest vocabulary token appears in an interface schema file",
        p6_schema_purity, (Mutant("crafter_field_in_schema", _edits("P6_crafter_field_in_schema")),)),
    Pin("P11", "the same seed and actions give an identical Crafter trajectory hash; emitted observations conform",
        p11_crafter_determinism, (Mutant("set_order_restored", _edits("P11_set_order_restored")),
                                  Mutant("seed_ignored", _edits("P11_seed_ignored")),
                                  Mutant("hash_constant", _edits("P11_hash_constant")),
                                  Mutant("field_dropped", _edits("P11_field_dropped")),
                                  Mutant("chunks_replaced_after_worldgen", _edits("P11_chunks_replaced_after_worldgen")),
                                  Mutant("golden_hash_altered", _edits("P11_golden_hash_altered")))),
]
