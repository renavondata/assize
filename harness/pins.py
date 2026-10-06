"""The harness's own pins (L0, brief 0 A2). Each kills its named mutant, an anchored edit to the harness,
and each kill is causal: the mutant run fails and its unedited twin passes."""

from __future__ import annotations

import json
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
FIXTURE_GIT = {"GIT_AUTHOR_NAME": "f", "GIT_AUTHOR_EMAIL": "f@f", "GIT_COMMITTER_NAME": "f",
               "GIT_COMMITTER_EMAIL": "f@f"}


def _trailer_repo(repo: Path) -> list[str]:
    """A fixture repository: a base commit, then one commit per TRAILER_FIXTURE case. Returns their shas."""
    env = os.environ | claims.GIT_ENV | FIXTURE_GIT

    def git(*args: str) -> str:
        return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True,
                              env=env).stdout.strip()

    def commit(path: str, trailers: tuple[str, ...], n: int) -> str:
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"{n}\n")
        git("add", "-A")
        git("commit", "-q", "-m", f"case {n}\n\nbody\n\n" + "".join(f"Proposer: {t}\n" for t in trailers))
        return git("rev-parse", "HEAD")

    repo.mkdir(parents=True)
    git("init", "-q", "-b", "master")
    commit("CODEOWNERS", ("guy",), 0)
    return [commit(path, trailers, n) for n, (_, path, trailers, _) in enumerate(TRAILER_FIXTURE, 1)]


def _branch_base(root: Path) -> str | None:
    for ref in ("origin/master", "master"):
        try:
            return claims._git(root, "merge-base", "HEAD", ref).strip()
        except subprocess.CalledProcessError:
            continue
    return None


def p0m_commit_proposers() -> bool:
    """Every commit on the branch carries well-formed `Proposer:` trailers; one touching an entrenched path
    (CODEOWNERS) without a `guy` party is rejected; every party line is read (brief 1 A4 item 7c, A5 F2)."""
    expect, ok = _expecter()
    patterns = claims.codeowners_patterns((ROOT / "CODEOWNERS").read_text())
    expect("CLAUDE.md" in patterns and ".github/" in patterns, f"entrenched paths from CODEOWNERS: {patterns}")
    work = Path(tempfile.mkdtemp(prefix="assize-p0m-", dir=context.scratch))
    shas = _trailer_repo(work / "repo")
    commits = claims.branch_commits(work / "repo", "master~" + str(len(TRAILER_FIXTURE)))
    expect([c.sha for c in commits] == shas, f"fixture: {len(commits)} branch commits read, want {len(shas)}")
    for (label, _, trailers, want), c in zip(TRAILER_FIXTURE, commits):
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
                                Mutant("first_proposer_only", _edits("P0m_first_proposer_only")))),
    Pin("P6", "no manifest vocabulary token appears in an interface schema file",
        p6_schema_purity, (Mutant("crafter_field_in_schema", _edits("P6_crafter_field_in_schema")),)),
]
