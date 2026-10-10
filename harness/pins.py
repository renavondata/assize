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
    resolution = {"id": forecast["id"], "ts": "2026-01-02T00:00:00Z", "proposer": LEDGER_PROPOSER | {"session": "t"},
                  "outcome": True}
    return forecast, resolution


def _ledger(*rows: dict) -> list[str]:
    return [json.dumps(r) for r in rows]


def p0k_forecast_ledger() -> bool:
    """A forecasts.jsonl resolution row lacking id, ts, proposer or outcome, matching no earlier forecast, or not
    proposed by the Reviewer or the resolver is rejected (brief 1 A4 item 7a, CLAUDE.md A1.6), and so is one proposed
    by its forecast's own session (rule 4 of the ground, instruction #54 item 4); every real ledger is validated."""
    expect, ok = _expecter()
    forecast, resolution = _ledger_fixture()
    got = claims.ledger_findings(_ledger(forecast, resolution))
    expect(not got, f"well-formed forecast and Reviewer resolution accepted ({[str(f) for f in got]})")
    auditor = _ledger_fixture()[0] | {"proposer": LEDGER_PROPOSER | {"kind": "auditor"}}
    got = claims.ledger_findings(_ledger(auditor))
    expect(not got, f"a forecast proposed by the Auditor accepted (CLAUDE.md Amendment 2) ({[str(f) for f in got]})")
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
    own = resolution | {"proposer": LEDGER_PROPOSER | {"session": forecast["proposer"]["session"]}}
    got = claims.ledger_findings(_ledger(forecast, own))
    expect(_codes(got) == {("row 2", "self_resolution")},
           f"a resolution by its forecast's own session rejected with self_resolution only ({[str(f) for f in got]})")
    mechanism = resolution | {"proposer": {"kind": "mechanism", "model": "harness.ledger",
                                           "session": forecast["proposer"]["session"]}}
    got = claims.ledger_findings(_ledger(forecast, mechanism))
    expect(not got, f"a mechanism's resolution accepted, whatever its session ({[str(f) for f in got]})")
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
    ("auditor, ordinary path", "docs/a.md", ("auditor m s",), set()),
)
EXEMPTION_FIXTURE = (  # (label, path, party stated only in the body, party exempted or None, parties, findings wanted)
    ("body-only Proposer, not exempted", "docs/z.md", "reviewer m s", None, (), {"no_proposer"}),
    ("body-only Proposer, exempted", "docs/z.md", "reviewer m s", "reviewer m s", ("reviewer m s",), set()),
    ("body-only Proposer, another party exempted", "docs/z.md", "reviewer m s", "reviewer m t", (), {"no_proposer"}),
)
SIGNED_AT, BEFORE, AFTER = "2026-01-01T12:00:00Z", "2026-01-01T11:00:00Z", "2026-01-01T13:00:00Z"
INSTRUCTION_ISSUES = {  # the issues INSTRUCTION_FIXTURE cites, as claims.load_issues would read them
    1: claims.Issue("gfrmin", ("instruction",), "open", "gfrmin", SIGNED_AT, ()),
    2: claims.Issue("gfrmin", ("instruction", "constitution"), "closed", "gfrmin", SIGNED_AT, ()),
    3: claims.Issue("assize-builder", ("instruction",), "open", "gfrmin", SIGNED_AT, ()),
    4: claims.Issue("gfrmin", ("constitution",), "open", "gfrmin", SIGNED_AT, ()),  # a timeline read at odds with labels
    5: claims.Issue("assize-vizier", ("draft", "instruction"), "open", "gfrmin", SIGNED_AT, ()),
    6: claims.Issue("assize-vizier", ("draft", "instruction"), "open", "assize-vizier", SIGNED_AT, ()),
    7: claims.Issue("gfrmin", ("instruction",), "open", "assize-builder", SIGNED_AT, ()),
    # instruction #54 item 5: the signature binds its text
    12: claims.Issue("gfrmin", ("instruction",), "open", "gfrmin", SIGNED_AT, (claims.Edit("gfrmin", AFTER),)),
    13: claims.Issue("gfrmin", ("instruction",), "open", "gfrmin", SIGNED_AT, (claims.Edit("gfrmin", BEFORE),
                                                                                claims.Edit("assize-builder", AFTER))),
    14: claims.Issue("assize-vizier", ("draft", "instruction"), "open", "gfrmin", SIGNED_AT,
                     (claims.Edit("assize-vizier", BEFORE),)),
    15: claims.Issue("gfrmin", ("instruction",), "open", "gfrmin", SIGNED_AT, None),
}
INSTRUCTION_FIXTURE = (  # (label, path, Proposer trailer lines, Instruction trailer lines, issues cited, findings wanted)
    ("builder, Instruction of gfrmin's open instruction issue, CLAUDE.md", "CLAUDE.md", ("builder m s",), ("#1",),
     (1,), set()),
    ("builder, Instruction of gfrmin's closed instruction issue, .github/", ".github/i.yml", ("builder m s",),
     ("#2",), (2,), set()),
    ("builder, Instruction of an issue another account authored, CLAUDE.md", "CLAUDE.md", ("builder m s",), ("#3",),
     (3,), {"entrenched_without_guy"}),
    ("builder, Instruction of gfrmin's issue not labelled instruction, CLAUDE.md", "CLAUDE.md", ("builder m s",),
     ("#4",), (4,), {"entrenched_without_guy"}),
    ("builder, Instruction of an issue not read, CLAUDE.md", "CLAUDE.md", ("builder m s",), ("#9",), (9,),
     {"entrenched_without_guy"}),
    ("builder, malformed Instruction, CLAUDE.md", "CLAUDE.md", ("builder m s",), ("1",), (), {"entrenched_without_guy"}),
    ("builder, Instruction of a draft gfrmin signed, .claude/", ".claude/d.md", ("builder m s",), ("#5",), (5,), set()),
    ("builder, Instruction of a draft the Vizier labelled itself, .claude/", ".claude/d.md", ("builder m s",), ("#6",),
     (6,), {"entrenched_without_guy"}),
    ("builder, Instruction of gfrmin's issue another account labelled, CLAUDE.md", "CLAUDE.md", ("builder m s",),
     ("#7",), (7,), {"entrenched_without_guy"}),
    ("builder, Instruction of an issue gfrmin edited after signing, CLAUDE.md", "CLAUDE.md", ("builder m s",),
     ("#12",), (12,), set()),
    ("builder, Instruction of an issue another account edited after signing, CLAUDE.md", "CLAUDE.md",
     ("builder m s",), ("#13",), (13,), {"entrenched_without_guy"}),
    ("builder, Instruction of a draft its poster edited before signing, .claude/", ".claude/d.md", ("builder m s",),
     ("#14",), (14,), set()),
    ("builder, Instruction of an issue whose edits were not read, CLAUDE.md", "CLAUDE.md", ("builder m s",),
     ("#15",), (15,), {"entrenched_without_guy"}),
)
TIMELINE_FIXTURE = (  # (label, timeline events, who the standing `instruction` label was applied by)
    ("gfrmin labels", (("labeled", "instruction", "gfrmin"),), "gfrmin"),
    ("the Vizier labels", (("labeled", "draft", "assize-vizier"), ("labeled", "instruction", "assize-vizier")),
     "assize-vizier"),
    ("the Vizier labels, gfrmin relabels", (("labeled", "instruction", "assize-vizier"),
                                             ("unlabeled", "instruction", "gfrmin"),
                                             ("labeled", "instruction", "gfrmin")), "gfrmin"),
    ("gfrmin labels, another account relabels", (("labeled", "instruction", "gfrmin"),
                                                  ("unlabeled", "instruction", "assize-builder"),
                                                  ("labeled", "instruction", "assize-builder")), "assize-builder"),
    ("gfrmin labels, then unlabels", (("labeled", "instruction", "gfrmin"), ("unlabeled", "instruction", "gfrmin")),
     None),
    ("only other labels and events", (("labeled", "draft", "gfrmin"), ("commented", None, "gfrmin")), None),
)


def _timeline(events: tuple) -> list[dict]:
    """Timeline events in the shape the GitHub API returns them, the i-th made at hour i."""
    return [{"event": e, "actor": {"login": a}, "created_at": f"2026-01-01T{i:02d}:00:00Z"}
            | ({"label": {"name": n}} if n else {}) for i, (e, n, a) in enumerate(events)]

MERGE_FIXTURE = (  # (label, path the merge writes, author address, Proposer trailer lines, parties, findings wanted)
    ("merge by gfrmin's noreply", "docs/m.md", "416374+gfrmin@users.noreply.github.com", (), ("guy",), set()),
    ("merge by gfrmin's own address, CLAUDE.md", "CLAUDE.md", "git@gfrm.in", (), ("guy",), set()),
    ("merge by assize-builder", "docs/m.md", "339109611+assize-builder@users.noreply.github.com", (), ("builder",),
     set()),
    ("merge by assize-reviewer, .github/", ".github/m.yml", "assize-reviewer@gfrm.in", (), ("reviewer",),
     {"entrenched_without_guy"}),
    ("merge by an unknown author", "docs/m.md", "f@f", (), (), {"unknown_merge_author"}),
    ("merge by an unknown author, Proposer: guy trailer", "docs/m.md", "f@f", ("guy",), (), {"unknown_merge_author"}),
)
FIXTURE_GIT = {"GIT_AUTHOR_NAME": "f", "GIT_AUTHOR_EMAIL": "f@f", "GIT_COMMITTER_NAME": "f",
               "GIT_COMMITTER_EMAIL": "f@f"}


def _trailer_repo(repo: Path) -> tuple[list[str], dict[str, str]]:
    """A fixture repository: a base commit, one commit per TRAILER_FIXTURE case, then one per EXEMPTION_FIXTURE case,
    whose `Proposer:` line a blank line separates from a following `Co-Authored-By:`, so git parses no trailer, then one
    per INSTRUCTION_FIXTURE case, carrying its `Instruction:` and `Proposer:` trailers, then one
    merge per MERGE_FIXTURE case, on the branch and the base commit, by its author (brief 1 A9). Returns their shas and
    the exemptions the EXEMPTION_FIXTURE cases name."""
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

    def merge(path: str, author: str, message: str, n: int, base: str) -> str:
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"{n}\n")
        git("add", "-A")
        sha = subprocess.run(["git", "-C", str(repo), "commit-tree", git("write-tree"), "-p", "HEAD", "-p", base,
                              "-m", f"case {n}\n\nbody\n\n{message}"], check=True, capture_output=True, text=True,
                             env=env | {"GIT_AUTHOR_EMAIL": author}).stdout.strip()
        git("update-ref", "HEAD", sha)
        return sha

    repo.mkdir(parents=True)
    git("init", "-q", "-b", "master")
    commit("CODEOWNERS", trailered(("guy",)), 0)
    shas = [commit(path, trailered(trailers), n) for n, (_, path, trailers, _) in enumerate(TRAILER_FIXTURE, 1)]
    unparsed = [commit(path, f"Proposer: {party}\n\nCo-Authored-By: f <f@f>\n", n)
                for n, (_, path, party, *_) in enumerate(EXEMPTION_FIXTURE, len(shas) + 1)]
    exemptions = {sha: exempt for sha, (_, _, _, exempt, *_) in zip(unparsed, EXEMPTION_FIXTURE) if exempt}
    instructed = [commit(path, "".join(f"Instruction: {i}\n" for i in cited) + trailered(trailers), n)
                  for n, (_, path, trailers, cited, *_) in enumerate(INSTRUCTION_FIXTURE,
                                                                      len(shas) + len(unparsed) + 1)]
    base = git("rev-list", "--max-parents=0", "HEAD")
    merges = [merge(path, author, trailered(trailers), n, base)
              for n, (_, path, author, trailers, *_) in enumerate(MERGE_FIXTURE,
                                                                  len(shas) + len(unparsed) + len(instructed) + 1)]
    return shas + unparsed + instructed + merges, exemptions


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
    (review aa993f4 F1). A merge needs no trailer: its one party is its author account's, and a merge by any other
    author is rejected, whatever trailer it carries (brief 1 A9). `Instruction: #<n>` carries Guy's authority on an
    entrenched path when issue <n>, read through the GitHub API, is authored by gfrmin and labelled `instruction`, open
    or closed (CLAUDE.md A1.5, instruction #38), and only if its timeline shows gfrmin applied the label; a `draft` the
    Vizier posted counts once gfrmin applies it (CLAUDE.md Amendment 3, instruction #49); and only if no account but
    gfrmin edited its body after his signature, its edits read (instruction #54 item 5). An exemption reachable from
    master is inert and a finding; the real branch is checked in CI too, never skipped."""
    expect, ok = _expecter()
    patterns = claims.codeowners_patterns((ROOT / "CODEOWNERS").read_text())
    expect("CLAUDE.md" in patterns and ".github/" in patterns, f"entrenched paths from CODEOWNERS: {patterns}")
    work = Path(tempfile.mkdtemp(prefix="assize-p0m-", dir=context.scratch))
    shas, exemptions = _trailer_repo(work / "repo")
    commits = claims.branch_commits(work / "repo", "master~" + str(len(shas)), exemptions=exemptions)
    expect([c.merge for c in commits] == [False] * (len(shas) - len(MERGE_FIXTURE)) + [True] * len(MERGE_FIXTURE),
           f"fixture: the last {len(MERGE_FIXTURE)} commits read as merges and no other")
    expect([c.sha for c in commits] == shas, f"fixture: {len(commits)} branch commits read, want {len(shas)}")
    cases = [(label, trailers, (), want) for label, _, trailers, want in TRAILER_FIXTURE] + \
            [(label, trailers, (), want) for label, _, _, _, trailers, want in EXEMPTION_FIXTURE] + \
            [(label, trailers, cited, want) for label, _, trailers, _, cited, want in INSTRUCTION_FIXTURE] + \
            [(label, parties, (), want) for label, _, _, _, parties, want in MERGE_FIXTURE]
    for (label, trailers, cited, want), c in zip(cases, commits):
        got = {f.code for f in claims.commit_findings(c, patterns, INSTRUCTION_ISSUES)}
        expect(got == want and c.parties == trailers and c.instructions == cited,
               f"{label}: parties reported {list(c.parties)}, instructions {list(c.instructions)}, findings "
               f"{sorted(got)}; want {list(trailers)}, {list(cited)}, {sorted(want)}")
    inert = claims.inert_exemptions(work / "repo", "master", exemptions)
    expect(bool(exemptions) and {f.where for f in inert} == {f"exemption {s[:12]}" for s in exemptions}
           and all(f.code == "inert_exemption" for f in inert),
           f"fixture: every exemption reachable from master is inert ({[str(f) for f in inert]})")
    expect(not claims.inert_exemptions(work / "repo", shas[0], exemptions),
           "fixture: an exemption not reachable from the base is not inert")
    shutil.rmtree(work, ignore_errors=True)
    for label, events, want in TIMELINE_FIXTURE:
        got = claims.instruction_labeler(_timeline(events))
        at = claims.instruction_labeled_at(_timeline(events))
        want_at = next((f"2026-01-01T{i:02d}:00:00Z" for i, (e, n, _) in reversed(list(enumerate(events)))
                        if n == "instruction"), None) if want else None
        expect(got == want and at == want_at, f"timeline, {label}: `instruction` label applied by {got!r} at {at}, "
                                               f"want {want!r} at {want_at}")

    root = _real_root()
    base = _branch_base(root)
    expect(base is not None, f"real branch: base resolved ({base})")
    inert = claims.inert_exemptions(root, base) if base else []
    expect(not inert, f"real: no exemption in claims.PROPOSER_EXEMPTIONS reachable from {base and base[:12]} "
                      f"({[str(f) for f in inert]})")
    real = claims.branch_commits(root, base) if base else []
    # Only an entrenched commit without a guy party needs its instructions read, so a branch whose commits carry
    # `Proposer: guy` makes no API call (pins CI holds no token that can read issues).
    issues = claims.load_issues(root, [n for c in real if claims.needs_guy(c, patterns) for n in c.instructions])
    found = [f for c in real for f in claims.commit_findings(c, patterns, issues)]
    for c in real:
        print(f"    {c.sha[:12]} parties {list(c.parties)} instructions {list(c.instructions)}")
    expect(not found, f"real branch {base and base[:12]}..HEAD: {len(real)} commits; findings "
                      f"{[str(f) for f in found]}")
    return ok()


def _forecast(claim: str, p: float, kind: str = "builder") -> dict:
    ts = "2026-01-01T00:00:00Z"
    return {"id": claims.forecast_id(claim, ts), "ts": ts, "proposer": LEDGER_PROPOSER | {"kind": kind},
            "sha_before": "0" * 40, "claim": claim, "p": p, "resolves_by": "r"}


def _resolved(f: dict, outcome: bool) -> dict:
    return {"id": f["id"], "ts": "2026-01-02T00:00:00Z", "proposer": LEDGER_PROPOSER, "outcome": outcome}


F_OLD, F_A, F_R, F_B, F_C = (_forecast("old", 0.99), _forecast("a", 0.9), _forecast("r", 0.99, "reviewer"),
                             _forecast("b", 0.6), _forecast("c", 0.99))
SURPRISE_FIXTURE = (  # (PR number, ledger, rows its branch appends); PR 1 merges before `since`
    (1, "reports/L1/forecasts.jsonl", (F_OLD,)),
    (2, "reports/L2/forecasts.jsonl", (F_A, F_R)),
    (3, "reports/L2/forecasts.jsonl", (F_B, _resolved(F_A, False), _resolved(F_R, False), _resolved(F_OLD, False),
                                       _resolved(F_B, False), _resolved(F_B, True))),
    (4, "reports/L1/forecasts.jsonl", (F_C,)),
)
# (PR number, Builder's cumulative log-loss, resolved, made), by the definition: A's 0.9 resolved false, B's 0.6
# resolved true by its last resolution, C unresolved; R is the Reviewer's and PR 1 merged before `since`.
SURPRISE_WANT = ((2, -math.log(1 - 0.9), 1, 1), (3, -math.log(0.6), 1, 1), (4, 0.0, 0, 1))


def _surprise_repo(repo: Path) -> str:
    """A fixture repository whose master merges one `Merge pull request #<n>` branch per SURPRISE_FIXTURE case, each
    appending its rows to its ledger. Returns the sha of PR 1's merge."""
    env = os.environ | claims.GIT_ENV | FIXTURE_GIT

    def git(*args: str) -> str:
        return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True,
                              env=env).stdout.strip()

    repo.mkdir(parents=True)
    git("init", "-q", "-b", "master")
    git("commit", "-q", "--allow-empty", "-m", "base")
    merges = []
    for n, ledger, rows in SURPRISE_FIXTURE:
        git("checkout", "-q", "-b", f"pr{n}")
        target = repo / ledger
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a") as f:
            f.writelines(json.dumps(r) + "\n" for r in rows)
        git("add", "-A")
        git("commit", "-q", "-m", f"pr {n}")
        git("checkout", "-q", "master")
        git("merge", "-q", "--no-ff", "-m", f"Merge pull request #{n} from f/pr{n}", f"pr{n}")
        merges.append(git("rev-parse", "HEAD"))
    return merges[0]


def p0n_surprise_ranking() -> bool:
    """`python -m harness.ledger surprise --since <sha>` lists the pull requests merged since <sha>, ranked by the
    Builder's cumulative log-loss on the forecasts each added, largest first, with its resolved and made counts
    (instruction #46 item 5)."""
    from harness import ledger

    expect, ok = _expecter()
    work = Path(tempfile.mkdtemp(prefix="assize-p0n-", dir=context.scratch))
    since = _surprise_repo(work / "repo")
    ranked = ledger.surprise(ledger.merged_since(work / "repo", since), ledger.outcomes(ledger.ledger_rows(work / "repo")))
    for r in ranked:
        print(f"    {r}")
    got = [(r.number, r.resolved, r.made) for r in ranked]
    expect(got == [(n, res, made) for n, _, res, made in SURPRISE_WANT],
           f"ranked (PR, resolved, made) {got}, want {[(n, res, made) for n, _, res, made in SURPRISE_WANT]}")
    expect(all(math.isclose(r.loss, loss) for r, (_, loss, _, _) in zip(ranked, SURPRISE_WANT)),
           f"losses {[r.loss for r in ranked]}, want {[w[1] for w in SURPRISE_WANT]}")
    expect(all(r.sessions == ("s",) for r in ranked), f"builder sessions {[r.sessions for r in ranked]}, want ('s',)")
    out = subprocess.run([sys.executable, "-B", "-m", "harness.ledger", "surprise", "--since", since,
                          "--repo", str(work / "repo")], cwd=ROOT, capture_output=True, text=True)
    listed = [line.split()[0] for line in out.stdout.splitlines() if line.startswith("#") and not line.startswith("# ")]
    expect(out.returncode == 0 and listed == [f"#{n}" for n, *_ in SURPRISE_WANT],
           f"the command lists {listed} (exit {out.returncode}; {out.stderr.strip()[-200:]!r})")
    shutil.rmtree(work, ignore_errors=True)
    return ok()


def _vizier(claim: str, p: float, cls: str, mode: str) -> dict:
    return _forecast(claim, p, "vizier") | {"class": cls, "mode": mode}


V_REC1, V_REC2, V_ACT1, V_ACT2, V_OPEN = (_vizier("r1", 0.8, "relabel", "recommend"),
                                          _vizier("r2", 0.7, "relabel", "recommend"),
                                          _vizier("a1", 0.9, "close-failed", "act"),
                                          _vizier("a2", 0.6, "close-failed", "act"),
                                          _vizier("o", 0.5, "relabel", "recommend"))
PROPOSER_FIXTURE = (V_REC1, V_REC2, V_ACT1, V_ACT2, V_OPEN, F_A, _resolved(V_REC1, True), _resolved(V_REC2, True),
                    _resolved(V_ACT1, True), _resolved(V_ACT2, False), _resolved(F_A, False))
# (class, made, resolved, correct, overturned, log-loss, unbroken), by the definition: both relabel recommendations
# resolved true, the third open; one close-failed act stood (0.9, true) and one was overturned (0.6, false); F_A is the
# Builder's and is not the Vizier's record.
PROPOSER_WANT = (("close-failed", 2, 2, 1, 1, -math.log(0.9) - math.log(1 - 0.6), False),
                 ("relabel", 3, 2, 2, 0, -math.log(0.8) - math.log(0.7), True))


def p0o_proposer_record() -> bool:
    """`python -m harness.ledger proposer vizier` reports the Vizier's record per class: made, resolved, correct,
    overturned acts, cumulative log-loss, and whether the class is correct on every resolved case; an overturned act
    is never a success (instruction #49 §4)."""
    from harness import ledger

    expect, ok = _expecter()
    got = ledger.record(list(PROPOSER_FIXTURE), "vizier")
    for r in got:
        print(f"    {r}")
    expect([(r.cls, r.made, r.resolved, r.correct, r.overturned, r.unbroken) for r in got]
           == [(c, m, res, cor, ov, u) for c, m, res, cor, ov, _, u in PROPOSER_WANT],
           f"records {[(r.cls, r.made, r.resolved, r.correct, r.overturned, r.unbroken) for r in got]}, want "
           f"{[(c, m, res, cor, ov, u) for c, m, res, cor, ov, _, u in PROPOSER_WANT]}")
    expect(all(math.isclose(r.loss, w[5]) for r, w in zip(got, PROPOSER_WANT)),
           f"losses {[r.loss for r in got]}, want {[w[5] for w in PROPOSER_WANT]}")
    later = ledger.record(list(PROPOSER_FIXTURE), "vizier", since="2026-01-01T00:00:01Z")
    expect(later == [], f"no Vizier forecast at or after a later --since: {later}")
    work = Path(tempfile.mkdtemp(prefix="assize-p0o-", dir=context.scratch))
    repo = work / "repo"
    env = os.environ | claims.GIT_ENV | FIXTURE_GIT
    (repo / "reports/L2").mkdir(parents=True)
    (repo / "reports/L2/forecasts.jsonl").write_text("".join(json.dumps(r) + "\n" for r in PROPOSER_FIXTURE))
    for args in (("init", "-q", "-b", "master"), ("add", "-A"), ("commit", "-q", "-m", "ledger")):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env)
    out = subprocess.run([sys.executable, "-B", "-m", "harness.ledger", "proposer", "vizier", "--repo", str(repo)],
                         cwd=ROOT, capture_output=True, text=True)
    listed = [line.split()[:5] for line in out.stdout.splitlines() if not line.startswith("#")]
    want = [[c, f"made={m}", f"resolved={res}", f"correct={cor}/{res}", f"overturned={ov}"]
            for c, m, res, cor, ov, _, _ in PROPOSER_WANT]
    expect(out.returncode == 0 and listed == want,
           f"the command lists {listed} (exit {out.returncode}; {out.stderr.strip()[-200:]!r})")
    shutil.rmtree(work, ignore_errors=True)
    return ok()


def _git_fixture(repo: Path):
    """A `git` for a fixture repository, reading no user or system configuration."""
    env = os.environ | claims.GIT_ENV | FIXTURE_GIT

    def git(*args: str) -> str:
        return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True,
                              env=env).stdout.strip()

    return git


def _append(repo: Path, path: str, text: str) -> None:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a") as f:
        f.write(text)


def _append_only_repo(repo: Path) -> tuple[str, dict[str, str]]:
    """A fixture repository: a base commit holding a ledger, a review file and REPORT.md; then on master an appending
    commit, a rewriting commit, and a merge of two branches each appending to another append-only path. Returns the
    base and the shas by role."""
    git = _git_fixture(repo)
    repo.mkdir(parents=True)
    git("init", "-q", "-b", "master")
    _append(repo, "reports/L1/forecasts.jsonl", '{"id": "a"}\n')
    _append(repo, "reports/L1/review-abc.md", "VERDICT: ACCEPT\n")
    _append(repo, "REPORT.md", "# report\n- L0 — PASSED\n")
    git("add", "-A")
    git("commit", "-q", "-m", "base")
    base = git("rev-parse", "HEAD")
    _append(repo, "reports/L1/forecasts.jsonl", '{"id": "b"}\n')
    git("commit", "-qam", "appends")
    shas = {"appending": git("rev-parse", "HEAD")}
    (repo / "REPORT.md").write_text("# report\n- L0 — FAILED\n")
    git("commit", "-qam", "rewrites")
    shas["rewriting"] = git("rev-parse", "HEAD")
    git("checkout", "-q", "-b", "x")
    _append(repo, "reports/L1/forecasts.jsonl", '{"id": "c"}\n')
    git("commit", "-qam", "x appends")
    git("checkout", "-q", "-b", "y", shas["rewriting"])
    _append(repo, "reports/L1/review-abc.md", "F1: appended\n")
    git("commit", "-qam", "y appends")
    git("checkout", "-q", "x")
    git("merge", "-q", "--no-ff", "-m", "merge y", "y")
    shas["merge"] = git("rev-parse", "HEAD")
    return base, shas


def p0q_append_only() -> bool:
    """Every commit on the branch only adds lines to the ledgers, review and audit files and the root REPORT.md, and
    a merge only adds lines relative to each of its parents (rule 1 of the ground, instruction #54 item 1)."""
    expect, ok = _expecter()
    work = Path(tempfile.mkdtemp(prefix="assize-p0q-", dir=context.scratch))
    base, shas = _append_only_repo(work / "repo")
    got = claims.append_only(work / "repo", base)
    for f in got:
        print(f"    fixture: {f}")
    expect({(f.where, f.code) for f in got} == {(f"commit {shas['rewriting'][:12]}", "ledger_rewrite")}
           and any("REPORT.md" in f.detail for f in got),
           "fixture: the rewriting commit, and only it, is found; the appending commit and the merge of two appending "
           "branches pass")
    shutil.rmtree(work, ignore_errors=True)

    root = _real_root()
    base = _branch_base(root)
    expect(base is not None, f"real branch: base resolved ({base})")
    real = claims.append_only(root, base) if base else []
    n = len(claims._git(root, "rev-list", f"{base}..HEAD").split()) if base else 0
    expect(not real, f"real branch {base and base[:12]}..HEAD: {n} commits; findings {[str(f) for f in real]}")
    return ok()


def _late_repo(repo: Path) -> tuple[str, str, str]:
    """A fixture repository: master with an empty ledger, then a branch of two commits whose forecast appears only in
    the second. Returns the base and the two commits."""
    git = _git_fixture(repo)
    repo.mkdir(parents=True)
    git("init", "-q", "-b", "master")
    _append(repo, "reports/L2/forecasts.jsonl", "")
    git("add", "-A")
    git("commit", "-q", "-m", "base")
    base = git("rev-parse", "HEAD")
    git("checkout", "-q", "-b", "pr")
    _append(repo, "harness/x.py", "x = 1\n")
    git("add", "-A")
    git("commit", "-q", "-m", "code")
    first = git("rev-parse", "HEAD")
    _append(repo, "reports/L2/forecasts.jsonl", json.dumps(_forecast("late", 0.5)) + "\n")
    git("commit", "-qam", "forecast")
    return base, first, git("rev-parse", "HEAD")


def _pins_run(run_id: int, sha: str, created: str, event: str = "pull_request") -> dict:
    return {"id": run_id, "head_sha": sha, "created_at": created, "event": event, "path": claims.PINS_WORKFLOW}


def _ledgers_at(repo: Path, sha: str, paths) -> dict[str, str | None]:
    def text(path: str) -> str | None:
        try:
            return claims._git(repo, "show", f"{sha}:{path}")
        except subprocess.CalledProcessError:
            return None
    return {p: text(p) for p in paths}


def p0r_claims_precede_scoring() -> bool:
    """The forecast rows a pull request adds are present in the tree at the head of the first `pins` run on its
    branch; a row first present in a later head is `late_forecast` (rule 2 of the ground, instruction #54 item 2). The
    real branch's runs are read through `gh api`; an unreadable record is a failure, not a skip."""
    expect, ok = _expecter()
    work = Path(tempfile.mkdtemp(prefix="assize-p0r-", dir=context.scratch))
    base, first, second = _late_repo(work / "repo")
    added = claims.forecast_rows_added(work / "repo", base, second)
    expect(list(added) == ["reports/L2/forecasts.jsonl"] and len(added["reports/L2/forecasts.jsonl"]) == 1,
           f"fixture: the branch adds one forecast row ({added})")
    runs = [_pins_run(2, second, "2026-01-02T00:00:00Z"), _pins_run(1, first, "2026-01-01T00:00:00Z"),
            _pins_run(0, base, "2025-12-31T00:00:00Z", "push")]
    run = claims.first_pins_run(runs)
    expect(run is not None and run["id"] == 1, f"fixture: the first pull_request pins run is run 1 ({run})")
    got = claims.late_forecasts(added, _ledgers_at(work / "repo", run["head_sha"], added), run["head_sha"]) \
        if run else []
    expect([f.code for f in got] == ["late_forecast"], f"fixture: a forecast first present in the second commit, "
                                                        f"after the first run's head, is late ({[str(f) for f in got]})")
    got = claims.late_forecasts(added, _ledgers_at(work / "repo", second, added), second)
    expect(not got, f"fixture: the same forecast present at the first run's head is not late ({[str(f) for f in got]})")
    shutil.rmtree(work, ignore_errors=True)

    root = _real_root()
    base = _branch_base(root)
    expect(base is not None, f"real branch: base resolved ({base})")
    added = claims.forecast_rows_added(root, base) if base else {}
    print(f"    real branch adds {sum(map(len, added.values()))} forecast rows in {sorted(added)}")
    if not added:
        return ok()
    branch = os.environ.get("GITHUB_HEAD_REF") or claims._git(root, "branch", "--show-current").strip()
    expect(bool(branch), f"real branch: name resolved ({branch!r}; GITHUB_HEAD_REF in CI, else the checked-out branch)")
    try:
        out = subprocess.run(["gh", "api", "--paginate", f"repos/{{owner}}/{{repo}}/actions/workflows/pins.yml/runs?"
                              f"event=pull_request&branch={branch}&per_page=100", "--jq",
                              ".workflow_runs[] | {id, head_sha, created_at, event, path}"], cwd=root, check=True,
                             capture_output=True, text=True, timeout=120).stdout
        runs = [json.loads(line) for line in out.splitlines() if line.strip()]
    except (OSError, subprocess.SubprocessError) as e:
        expect(False, f"real branch: pins runs on {branch!r} read through gh api ({getattr(e, 'stderr', '') or e})")
        return ok()
    run = claims.first_pins_run(runs)
    if run is None:
        print(f"    real branch {branch}: {len(runs)} pins runs; none yet, so the first will run on a head that holds "
              f"these rows")
        return ok()
    sha = str(run["head_sha"])
    try:
        texts = {p: _ledger_text(root, sha, p) for p in added}
    except (OSError, subprocess.SubprocessError) as e:
        expect(False, f"real branch: ledgers at {sha[:12]}, the first pins run's head, read ({e})")
        return ok()
    got = claims.late_forecasts(added, texts, sha)
    expect(not got, f"real branch {branch}: first pins run {run['id']} on {sha[:12]} of {len(runs)}; findings "
                    f"{[str(f) for f in got]}")
    return ok()


def _ledger_text(root: Path, sha: str, path: str) -> str | None:
    """A ledger's text at `sha`: from git if this clone holds the commit, else through the contents API; None if the
    file is absent there."""
    if subprocess.run(["git", "-C", str(root), "cat-file", "-e", f"{sha}^{{commit}}"], capture_output=True,
                      env=os.environ | claims.GIT_ENV).returncode == 0:
        return _ledgers_at(root, sha, [path])[path]
    got = subprocess.run(["gh", "api", f"repos/{{owner}}/{{repo}}/contents/{path}?ref={sha}", "-H",
                          "Accept: application/vnd.github.raw"], cwd=root, capture_output=True, text=True, timeout=60)
    if got.returncode != 0 and "404" in got.stderr:
        return None
    if got.returncode != 0:
        raise subprocess.CalledProcessError(got.returncode, "gh api contents", got.stdout, got.stderr)
    return got.stdout


def _typed(claim: str, p: float, ftype: str | None, args: dict, ts: str = "2026-01-10T00:00:00Z") -> dict:
    f = {"id": claims.forecast_id(claim, ts), "ts": ts, "proposer": LEDGER_PROPOSER | {"kind": "builder"},
         "sha_before": "0" * 40, "claim": claim, "p": p, "resolves_by": "the resolver"}
    return f | ({"type": ftype, "args": args} if ftype else {})


BEFORE_TS, AFTER_TS, LATER_TS = "2026-01-09T00:00:00Z", "2026-01-11T00:00:00Z", "2026-01-12T00:00:00Z"
REVIEW_BLOCKED = "VERDICT: ACCEPT WITH OBLIGATIONS\nF1: x — severity: BLOCK (rule) — witness: w\n"
# (forecast, outcome wanted: True, False, or None for not observable / never resolved by the mechanism)
OUTCOME_FIXTURE = (
    (_typed("pins: first run after the forecast failed", 0.8, "pins_green", {"pr": 1}), False),
    (_typed("review: first file after the forecast carries a BLOCK", 0.7, "review_accept", {"pr": 2}), False),
    (_typed("review: accepted", 0.7, "review_accept", {"pr": 3}), True),
    (_typed("merged", 0.9, "merged", {"pr": 4}), True),
    (_typed("still open", 0.9, "merged", {"pr": 5}), None),
    (_typed("host FIT, the line says UNFIT", 0.4, "host_verdict", {"layer": 2, "verdict": "FIT"}), False),
    (_typed("host UNFIT", 0.4, "host_verdict", {"layer": 2, "verdict": "UNFIT"}), True),
    (_typed("no L3 line yet", 0.4, "host_verdict", {"layer": 3, "verdict": "FIT"}), None),
    (_typed("Guy approves", 0.6, "guy_answers", {"item": 6, "answer": "approved"}), True),
    (_typed("Guy signs; closed unsigned", 0.6, "guy_answers", {"item": 7, "answer": "labeled:instruction"}), False),
    (_typed("act stands", 0.9, "not_overturned", {"item": 8, "until": LATER_TS}), True),
    (_typed("act reversed", 0.9, "not_overturned", {"item": 9, "until": LATER_TS}), False),
    (_typed("act, until not reached", 0.9, "not_overturned", {"item": 8, "until": "2027-01-01T00:00:00Z"}), None),
    (_typed("two findings in 1-3", 0.5, "finding_count", {"sha": "abc123", "bin": "1–3"}), True),
    (_typed("two findings in 0", 0.2, "finding_count", {"sha": "abc123", "bin": "0"}), False),
    (_typed("guy-items at most 3", 0.5, "price", {"quantity": "guy-items", "layer": 2, "bound": 3}), False),
    (_typed("free text, untyped", 0.5, None, {}), None),
    (_typed("free text, typed free", 0.5, "free", {}), None),
)
OUTCOME_UNREAD = (_typed("no such type", 0.5, "nonsense", {}),)
OUTCOME_ANSWERS = {  # what the GitHub API and the tree answer, in the shapes the real observer returns
    ("pins_runs", 1): [_pins_run(10, "a" * 40, BEFORE_TS), _pins_run(12, "c" * 40, LATER_TS),
                       _pins_run(11, "b" * 40, AFTER_TS)],
    ("run_attempt", 10): {"status": "completed", "conclusion": "success"},
    ("run_attempt", 11): {"status": "completed", "conclusion": "failure"},
    ("run_attempt", 12): {"status": "completed", "conclusion": "success"},
    ("review_files", 2): [{"sha": "d" * 40, "date": BEFORE_TS, "path": "reports/L2/review-d.md",
                           "text": "VERDICT: ACCEPT\n"},
                          {"sha": "e" * 40, "date": AFTER_TS, "path": "reports/L2/review-e.md", "text": REVIEW_BLOCKED}],
    ("review_files", 3): [{"sha": "f" * 40, "date": AFTER_TS, "path": "reports/L2/review-f.md",
                           "text": "VERDICT: ACCEPT\nF1: fine — severity: OBLIGATION on L3 — witness: w\n"}],
    ("pr", 4): {"state": "closed", "merged": True, "merged_at": AFTER_TS},
    ("pr", 5): {"state": "open", "merged": False},
    ("report",): "# REPORT\n- L1 — **SEALED; Crafter FIT**\n- L2 — **NetHack MARGINAL**\n- L2 — **NetHack UNFIT**\n",
    ("timeline", 6): [{"event": "reviewed", "user": {"login": "gfrmin"}, "state": "commented", "submitted_at": AFTER_TS},
                      {"event": "reviewed", "user": {"login": "gfrmin"}, "state": "approved", "submitted_at": LATER_TS}],
    ("timeline", 7): [{"event": "labeled", "actor": {"login": "gfrmin"}, "label": {"name": "instruction"},
                       "created_at": BEFORE_TS},
                      {"event": "closed", "actor": {"login": "assize-reviewer"}, "created_at": AFTER_TS}],
    ("timeline", 8): [{"event": "merged", "actor": {"login": "gfrmin"}, "created_at": AFTER_TS},
                      {"event": "closed", "actor": {"login": "gfrmin"}, "created_at": AFTER_TS},
                      {"event": "unlabeled", "actor": {"login": "assize-reviewer"}, "created_at": AFTER_TS}],
    ("timeline", 9): [{"event": "reopened", "actor": {"login": "gfrmin"}, "created_at": AFTER_TS}],
    ("audit", "abc123"): ("reports/L2/audit-abc123.md", "AUDIT: abc123\nFINDINGS: 2\nF1: a\nF2: b\nre-reviewed: none\n"),
    ("price", 2): {"guy-items": 5.0},
}
OUTCOME_NOW = "2026-06-01T00:00:00Z"


def _observe(kind: str, *key: object) -> object:
    from harness import ledger

    if (kind, *key) not in OUTCOME_ANSWERS:
        raise ledger.Unreadable(f"fixture has no answer to {(kind, *key)}")
    return OUTCOME_ANSWERS[(kind, *key)]


def p0s_outcomes_by_code() -> bool:
    """`python -m harness.ledger resolve` resolves every open typed forecast whose outcome is observable, by its
    type's definition, from fixture API answers for every type, with a resolution proposed by the mechanism; leaves
    the unobservable open; never resolves a `free` one; and names, never drops, one it cannot read (rule 3 of the
    ground, instruction #54 item 3)."""
    from harness import ledger

    expect, ok = _expecter()
    rows = [f for f, _ in OUTCOME_FIXTURE] + list(OUTCOME_UNREAD)
    got, unread = ledger.resolve(rows, _observe, OUTCOME_NOW, "p0s")
    by_id = {r["id"]: r["outcome"] for r in got}
    for (f, want) in OUTCOME_FIXTURE:
        expect(by_id.get(f["id"]) == want, f"{f.get('type', 'untyped')} {f['claim']!r}: resolved "
                                           f"{by_id.get(f['id'], 'open')}, want {'open' if want is None else want}")
    expect(len(got) == sum(1 for _, w in OUTCOME_FIXTURE if w is not None), f"{len(got)} resolutions, one per "
                                                                           f"observable typed forecast")
    expect(all(r["proposer"] == {"kind": "mechanism", "model": "harness.ledger", "session": "p0s"} and r["ts"] ==
               OUTCOME_NOW and r.get("witness") for r in got), "every resolution is the mechanism's, now, witnessed")
    expect(len(unread) == 1 and OUTCOME_UNREAD[0]["id"] in unread[0], f"the unknown type is named, not dropped "
                                                                      f"({unread})")
    findings = claims.ledger_findings(_ledger(*rows, *got))
    expect(not findings, f"forecasts and resolutions pass the ledger check ({[str(f) for f in findings]})")
    again, _ = ledger.resolve(rows + got, _observe, OUTCOME_NOW, "p0s")
    expect(not again, f"a resolved forecast is not resolved again ({again})")
    return ok()


T0 = "2026-02-01T00:00:00Z"


def _h(hours: float) -> str:
    import datetime
    return (datetime.datetime.fromisoformat(T0.replace("Z", "+00:00")) + datetime.timedelta(hours=hours)) \
        .strftime("%Y-%m-%dT%H:%M:%SZ")


PRICE_REACHED = (  # (item, route, hour it reached Guy)
    (1, "awaits-guy", 1), (2, "assigned", 2), (3, "needs-you", 3), (3, "awaits-guy", 4), (4, "awaits-guy", -5))
PRICE_ACTIONS = {1: (0.5, 3), 3: (5,), 4: (-4,)}  # hours of gfrmin's actions per item
PRICE_RUNS = (  # (workflow, conclusion, start hour, minutes)
    (".github/workflows/build.yml", "success", 1, 30), (".github/workflows/review.yml", "failure", 2, 60),
    (".github/workflows/review.yml", "skipped", 2, 1), (claims.PINS_WORKFLOW, "success", 3, 10),
    (".github/workflows/build.yml", "success", -10, 99))
PRICE_UNTIL = 10
# by the definition, over [T0, T0 + 10h): items 1, 2, 3 (4 reached before the window; 3 once, at its first arrival);
# latencies 1 -> 3 is 2h, 2 unanswered is 10 - 2 = 8h (open, never dropped), 3 -> 5 is 2h; sessions: the build and
# the failed review (the skipped one never ran); runner-minutes 30 + 60 + 10, pins 10.
PRICE_WANT = {"items": (1, 2, 3), "latencies": (2.0, 8.0, 2.0), "open": (2,), "sessions": 2, "runner": 100.0,
              "pins": 10.0}


def p0t_price() -> bool:
    """`python -m harness.ledger price` counts every item that reached Guy by an `awaits-guy` label, an assignment or
    a NEEDS YOU line, once, with its latency to his first action after it, or to the window's end if none yet; and
    sessions and runner-minutes per workflow (rule 6 of the ground, instruction #54 item 6)."""
    from harness import ledger

    expect, ok = _expecter()
    reached = [{"item": n, "route": r, "at": _h(h)} for n, r, h in PRICE_REACHED]
    actions = {n: [_h(h) for h in hs] for n, hs in PRICE_ACTIONS.items()}
    runs = [{"path": w, "conclusion": c, "created_at": _h(h), "run_started_at": _h(h), "updated_at": _h(h + m / 60)}
            for w, c, h, m in PRICE_RUNS]
    got = ledger.price(reached, actions, runs, T0, _h(PRICE_UNTIL))
    print(f"    {got}")
    print(f"    {got.status_line()}")
    expect(got.items == PRICE_WANT["items"], f"items {got.items}, want {PRICE_WANT['items']}")
    expect(len(got.latencies_h) == len(got.items) and all(
        math.isclose(a, b) for a, b in zip(got.latencies_h, PRICE_WANT["latencies"])),
        f"latencies {got.latencies_h}, want {PRICE_WANT['latencies']}")
    expect(got.open_items == PRICE_WANT["open"], f"open items {got.open_items}, want {PRICE_WANT['open']}")
    expect(got.sessions == PRICE_WANT["sessions"], f"sessions {got.sessions}, want {PRICE_WANT['sessions']}")
    expect(math.isclose(sum(got.runner_min.values()), PRICE_WANT["runner"]) and math.isclose(got.pins_min,
                                                                                            PRICE_WANT["pins"]),
           f"runner-minutes {dict(got.runner_min)}, pins {got.pins_min}; want {PRICE_WANT['runner']}, "
           f"{PRICE_WANT['pins']}")
    expect(got.status_line() == "price: guy-items 3; guy-latency median 2.0h max 8.0h; sessions 2; runner-min 100",
           f"STATUS line {got.status_line()!r}")
    return ok()


def _elector(model: str, p: float, outcome: bool | None, kind: str = "reviewer") -> list[dict]:
    f = _forecast(f"{kind} {model} {p} {outcome}", p, kind)
    f["proposer"] = f["proposer"] | {"model": model}
    return [f] + ([_resolved(f, outcome)] if outcome is not None else [])


ELECTION_ENTRANTS = ("m-a", "m-b", "m-c")
ELECTION_FIXTURE = (_elector("m-a", 0.9, True) + _elector("m-a", 0.2, True) + _elector("m-b", 0.5, False)
                    + _elector("m-a", 0.01, False, "builder") + _elector("m-b", 0.3, None))


def p0u_election() -> bool:
    """`python -m harness.ledger elect <procedure> --seed <run id>` draws an entrant by Hedge over the entrants'
    cumulative log-loss on that procedure's resolved forecasts: weights exp(-eta L_m), eta = sqrt(8 ln K / t), no
    record meaning L = 0; over a sweep of every seed residue the draw's frequencies equal the weights (rule 7 of the
    ground, instruction #54 item 7)."""
    from harness import ledger

    expect, ok = _expecter()
    rows = list(ELECTION_FIXTURE)
    loss = {"m-a": -math.log(0.9) - math.log(0.2), "m-b": -math.log(1 - 0.5), "m-c": 0.0}  # by the definition
    t, k = 3, len(ELECTION_ENTRANTS)
    eta = math.sqrt(8 * math.log(k) / t)
    raw = {m: math.exp(-eta * v) for m, v in loss.items()}
    want = {m: w / sum(raw.values()) for m, w in raw.items()}
    counts = {m: 0 for m in ELECTION_ENTRANTS}
    for seed in range(ledger.DRAWS):
        m = ledger.elect(rows, "review", ELECTION_ENTRANTS, seed + 123456789)
        counts[m] = counts.get(m, 0) + 1
    print(f"    weights {want}; draws over {ledger.DRAWS} seeds {counts}")
    expect(all(abs(counts[m] - want[m] * ledger.DRAWS) <= 1 for m in ELECTION_ENTRANTS) and sum(counts.values())
           == ledger.DRAWS, f"every entrant drawn its weight's share of the sweep, to one draw ({counts})")
    expect(ledger.elect(rows, "audit", ELECTION_ENTRANTS, 0) in ELECTION_ENTRANTS,
           "a procedure with no record draws among its entrants")
    work = Path(tempfile.mkdtemp(prefix="assize-p0u-", dir=context.scratch))
    repo = work / "repo"
    git = _git_fixture(repo)
    repo.mkdir(parents=True)
    git("init", "-q", "-b", "master")
    _append(repo, "reports/L2/forecasts.jsonl", "".join(json.dumps(r) + "\n" for r in rows))
    _append(repo, ledger.ENTRANTS, f"review = {json.dumps(list(ELECTION_ENTRANTS))}\n")
    git("add", "-A")
    git("commit", "-q", "-m", "ledger")
    seeds = (7, 40000, 65535)
    out = [subprocess.run([sys.executable, "-B", "-m", "harness.ledger", "elect", "review", "--seed", str(s), "--repo",
                           str(repo)], cwd=ROOT, capture_output=True, text=True) for s in seeds]
    printed = [o.stdout.strip() for o in out]
    expect(all(o.returncode == 0 for o in out) and printed == [ledger.elect(rows, "review", ELECTION_ENTRANTS, s)
                                                               for s in seeds],
           f"the command prints the draw for its seed: {printed} ({[o.stderr.strip()[-200:] for o in out]})")
    shutil.rmtree(work, ignore_errors=True)
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


def p1_seed_issuance() -> bool:
    """Evaluation seeds are issued from a CSPRNG into judge-private storage, keyed by the seed the World actually
    generates from, and never reissued: two requests from two store openings get disjoint evaluation-domain seeds, all
    recorded; the issuance check refuses a used seed, a training-domain seed, a reused request id and a non-private
    store, recording nothing; the public training stream is deterministic and entirely training-domain, hence
    disjoint from every issued seed (brief 1 section 2)."""
    from judge import seeds
    from worlds.crafter import binding

    expect, ok = _expecter()
    key, world, n = binding.world_seed, "crafter", 5
    work = Path(tempfile.mkdtemp(prefix="assize-p1-", dir=context.scratch))
    root = work / "judge-private"

    def refused(code: str, ss, rid: str) -> None:
        before = (root / f"{world}.seeds.jsonl").read_bytes()
        try:
            seeds.admit(root, world, key, ss, rid)
            got = "admitted"
        except seeds.SeedError as e:
            got = e.code
        expect(got == code and (root / f"{world}.seeds.jsonl").read_bytes() == before,
               f"admit({ss}, {rid!r}) refused {code}, store unchanged (got {got})")

    issued: list[int] = []
    for rid in ("request-a", "request-b"):  # each from the store as the files left it, no state carried over
        try:
            got = seeds.issue(root, world, key, n, rid)
        except seeds.SeedError as e:
            got = []
            print(f"    issue({rid!r}) raised {e}")
        print(f"    {rid}: {got}")
        expect(len(got) == n, f"{rid}: {n} seeds issued")
        issued += got
    keys = [key(s) for s in issued]
    expect(len(set(keys)) == len(keys) == 2 * n, f"{len(keys)} issued seeds have {len(set(keys))} distinct World keys")
    expect(all(k % 2 == seeds.EVAL for k in keys), "every issued seed is keyed in the evaluation domain (odd)")
    recs = seeds.records(root, world)
    expect([(r["request_id"], r["seed"], r["key"]) for r in recs]
           == [(rid, s, key(s)) for rid, ss in (("request-a", issued[:n]), ("request-b", issued[n:])) for s in ss],
           f"the store records exactly the issued seeds, in order ({len(recs)} records)")
    mode = (root.stat().st_mode & 0o777, (root / f"{world}.seeds.jsonl").stat().st_mode & 0o777)
    expect(mode == (0o700, 0o600), f"store directory and file modes {oct(mode[0])}, {oct(mode[1])}")

    refused("reused", [issued[0]], "request-c")
    refused("reused", [issued[-1]], "request-d")
    twin = next(s for s in range(SEED_SCAN) if key(s) % 2 == seeds.EVAL and key(s) not in keys)
    refused("reused", [twin, twin], "request-e")
    refused("request_reused", [twin], "request-a")
    train = seeds.training_seeds(world, key, n)
    refused("training_domain", [train[0]], "request-f")
    refused("out_of_space", [seeds.SEED_SPACE], "request-g")

    again = seeds.training_seeds(world, key, n)
    tkeys = [key(s) for s in train]
    print(f"    training stream: {train}")
    expect(train == again and len(set(tkeys)) == n, "the training stream is deterministic and its keys distinct")
    expect(all(k % 2 == seeds.TRAIN for k in tkeys), "every training seed is keyed in the training domain (even)")
    expect(not set(tkeys) & set(keys), "no training seed's key is an issued seed's key")

    loose = work / "loose"
    loose.mkdir(mode=0o755)
    loose.chmod(0o755)
    try:
        seeds.issue(loose, world, key, 1, "request-h")
        got = "issued"
    except seeds.SeedError as e:
        got = e.code
    expect(got == "not_private", f"a store directory of mode 755 refused not_private (got {got})")
    shutil.rmtree(work, ignore_errors=True)
    return ok()


SEED_SCAN = 64  # small seeds searched for an unissued evaluation-domain one; each is odd-keyed with probability 1/2


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


def _priced(used: dict, cfg: dict, rate: dict) -> dict:
    """What the judge must charge for `used` at the manifest's `rate`, derived here from `judge/config.toml` and the
    rule `judge/price.py` states, independently of that module: the unmeasured stretch at the configured CPUs and
    memory, the peak memory over the rest, in gigabytes of 1e9 bytes."""
    lim = cfg["candidate"]
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
    rates Crafter's manifest commits, which equal their stated derivation. The peak memory's scope is stated in the
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
    rate = {k: binding.manifest()["price"][k] for k in ("cpu_s", "memory_gb_s")}
    lim, t = cfg["candidate"], cfg["timeouts"]
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
            want = _priced(r["compute"], cfg, rate) if "peak_memory_bytes" in r.get("compute", {}) else {}
            expect(_same(r.get("price"), want),
                   f"{rt.name} {r['termination']} episode {r['episode']}: price {r.get('price')}, derived {want}")
        used = crashed[0].get("compute", {}) if crashed else {}
        expect(used.get("unmeasured_s", 0) > 0,
               f"{rt.name} busy_crash: non-vacuous: {used.get('unmeasured_s')} s unmeasured after the container's last read")
        strays = _removing_strays(rt, before)
        expect(not strays, f"{rt.name}: no candidate container listed after the cases ({strays})")

    _each_runtime(usable, case, expect)
    return ok()

# P19 and P20 (brief 2 A2): fixture Worlds added to a copy of the tree by their directories alone, no judge edit. `fx`
# has a manifest, a price and a binding; `unpriced` has a manifest without a price; `bare` has a binding and no
# manifest. Each is asked of `evaluate()` under a runtime that does not exist, so a World the judge binds and prices is
# refused only `unknown_runtime`, after its binding and price are settled and before any seed is issued.
FIXTURE_WORLD_BINDING = '''import json
from pathlib import Path

MARK = Path(__file__).parent.name


def manifest():
    return json.loads(Path(__file__).with_name("manifest.json").read_text())


def world_seed(seed):
    return seed


class Episode:
    def __init__(self, seed, m=None):
        raise AssertionError("a fixture World is never played")
'''
FIXTURE_WORLDS_RUN = """
import json, sys
from pathlib import Path
from judge import evaluate, registry
private, ledgers = Path(sys.argv[1]), Path(sys.argv[2])
image = "sha256:" + "d" * 64
registry.register(private, image, registry.credential(private, json.loads(sys.argv[3])))
out = {"bound": evaluate.bound(), "refused": {}}
for w in json.loads(sys.argv[4]):
    try:
        evaluate.evaluate(image, w, 1, "fixture-" + w, private=private, ledgers=ledgers, runtime_name="no-such-runtime")
        out["refused"][w] = None
    except registry.Refused as e:
        out["refused"][w] = e.code
try:
    out["fx_binding"] = getattr(evaluate._binding("fx"), "MARK", None)
except registry.Refused as e:
    out["fx_binding"] = e.code
out["seed_stores"] = sorted(p.name for p in private.glob("*.seeds.jsonl"))
print(json.dumps(out))
"""
FIXTURE_PARTY = {"kind": "builder", "model": "claude-opus-5-5", "session": "p19-fixture-party"}
FIXTURE_ASKED = ("crafter", "fx", "unpriced", "bare")


def _fixture_worlds() -> dict:
    """FIXTURE_WORLDS_RUN in a copy of the running tree with the fixture Worlds' directories added; its findings."""
    with tree.disposable_copy() as copy:
        m = json.loads((copy / "worlds" / "crafter" / "manifest.json").read_text())
        for name, manifest in (("fx", m | {"world": "fx"}),
                               ("unpriced", {k: v for k, v in m.items() if k != "price"} | {"world": "unpriced"}),
                               ("bare", None)):
            d = copy / "worlds" / name
            d.mkdir()
            (d / "binding.py").write_text(FIXTURE_WORLD_BINDING)
            if manifest is not None:
                (d / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        state = Path(tempfile.mkdtemp(prefix="fixture-worlds-", dir=context.scratch))
        r = subprocess.run(proc.python("-c", FIXTURE_WORLDS_RUN, str(state / "private"), str(state / "ledgers"),
                                       json.dumps(FIXTURE_PARTY), json.dumps(FIXTURE_ASKED)),
                           cwd=copy, env=proc.child_env(), capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError(f"fixture-worlds child exited {r.returncode}: {r.stderr.strip()[-500:]}")
        got = json.loads(r.stdout)
        print(f"  fixture Worlds in a copy of the tree: {json.dumps(got)}")
        return got


def p19_world_discovery() -> bool:
    """The judge binds a World by its directory alone: a fixture directory with a manifest and a binding, added to a copy
    of the tree with no edit to `judge/`, is bound under its name, its own binding is the one imported, and `evaluate()`
    takes it past the World check to the runtime check; a directory with a binding but no manifest is not bound, and is
    refused `unknown_world`. Crafter stays bound. No seed is issued to any fixture request (brief 2 A2)."""
    expect, ok = _expecter()
    got = _fixture_worlds()
    expect(got["bound"] == ["crafter", "fx", "unpriced"],
           f"bound: every directory with a manifest and a binding, and only those ({got['bound']})")
    expect(got["fx_binding"] == "fx", f"fx's own binding is imported ({got['fx_binding']})")
    for w, want in (("fx", "unknown_runtime"), ("crafter", "unknown_runtime"), ("bare", "unknown_world")):
        expect(got["refused"][w] == want, f"evaluate({w!r}) refused {want} ({got['refused'][w]})")
    expect(not got["seed_stores"], f"no seed issued to a refused request ({got['seed_stores']})")
    return ok()


def p20_world_price() -> bool:
    """A World is priced from its own manifest: `evaluate()` refuses `unpriced`, before any seed is issued, a World whose
    manifest commits no price, and takes a World whose manifest commits one past the price check; every manifest in
    the tree commits one, and the manifest schema requires it (brief 2 A2)."""
    import jsonschema
    import referencing
    from worlds.spec import purity

    expect, ok = _expecter()
    got = _fixture_worlds()
    for w, want in (("unpriced", "unpriced"), ("fx", "unknown_runtime")):
        expect(got["refused"][w] == want, f"evaluate({w!r}) refused {want} ({got['refused'][w]})")
    expect(not got["seed_stores"], f"no seed issued to a refused request ({got['seed_stores']})")
    schemas, manifests = purity.load(purity.schema_files()), purity.load(purity.manifest_files())
    registry = referencing.Registry().with_resources(
        (s["$id"], referencing.Resource.from_contents(s)) for s in schemas.values())
    v = jsonschema.Draft202012Validator(schemas["manifest.schema.json"], registry=registry)
    for name, m in manifests.items():
        expect("price" in m and v.is_valid(m), f"{name} commits a price and conforms to manifest.schema.json")
        unpriced = {k: x for k, x in m.items() if k != "price"}
        expect(not v.is_valid(unpriced), f"manifest.schema.json rejects {name} without its price")
    return ok()

def p21_replay_verified() -> bool:
    """Replay checks a request's records against its signed head (brief 2 A2, L2a obligation 3; review 6debf231b630 F2).
    Of two signed requests, `evaluate._recorded` returns the first's records exactly as written and an unknown request
    as None; and refuses `ledger_unverified` when a utility is altered, a record is dropped, a record is added, or
    the head's signature is forged."""
    from judge import evaluate, ledger, registry

    expect, ok = _expecter()
    work = Path(tempfile.mkdtemp(prefix="assize-p21-", dir=context.scratch))
    try:
        led, private = work / "ledger.jsonl", work / "private"
        (a_id, a), (b_id, b) = P9_REQUESTS
        held_a = ledger.append(led, private, a_id, a)
        ledger.append(led, private, b_id, b)
        written, heads = led.read_bytes(), (private / "heads.jsonl").read_bytes()
        rows = [json.loads(line) for line in written.splitlines()]

        def replay(name: str, want) -> None:
            try:
                got = evaluate._recorded(led, private, a_id)
            except registry.Refused as e:
                got = e.code
            expect(got == want, f"{name}: replay gives {want if isinstance(want, str) else 'the records as written'} "
                                f"(got {got if isinstance(got, str) else 'records'})")

        def tampered(name: str, act) -> None:
            act()
            replay(name, "ledger_unverified")
            led.write_bytes(written)
            (private / "heads.jsonl").write_bytes(heads)

        def put(out: list[dict]) -> None:
            led.write_bytes(b"".join(ledger.canonical(r) + b"\n" for r in out))

        def utility_altered() -> None:
            put([r | {"utility": r["utility"] + 99} if i == 0 else r for i, r in enumerate(rows)])

        def record_dropped() -> None:
            put([r for i, r in enumerate(rows) if i != 1])

        def record_added() -> None:
            put(rows[:3] + [rows[0]] + rows[3:])

        def head_forged() -> None:
            forged = [json.loads(h) | {"mac": "0" * 64} for h in heads.splitlines()]
            (private / "heads.jsonl").write_bytes(b"".join(ledger.canonical(h) + b"\n" for h in forged))

        replay("untouched", held_a)
        expect(evaluate._recorded(led, private, "p21-unknown") is None, "a request never signed replays as None")
        for name, act in (("a utility altered", utility_altered), ("a record dropped", record_dropped),
                          ("a record added", record_added),
                          ("the head's signature forged", head_forged)):
            tampered(name, act)
    finally:
        shutil.rmtree(work, ignore_errors=True)
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


def _verify_cli(led: Path, private: Path, anchor: str) -> tuple[int, str]:
    """The judge's verification subcommand, run as the judge runs it, in a child interpreter."""
    r = subprocess.run(proc.python("-m", "judge", "verify", str(led), str(private), anchor), cwd=ROOT,
                       env=proc.child_env(), capture_output=True, text=True, timeout=120)
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
    request removed, a forged head without the key, the last request truncated with its head, the ledger and its heads
    both deleted (review 2817eb7 F2: verified against the head the caller holds, the last record's `sha256`), and,
    with the key in a forger's hands, a chain rebuilt from the empty string or with a record left out. An earlier
    request's head still anchors the ledger after later requests. A request_id is written once."""
    import hashlib

    from judge import ledger

    expect, ok = _expecter()
    work = Path(tempfile.mkdtemp(prefix="assize-p9-", dir=context.scratch))
    try:
        led, private = work / "ledger.jsonl", work / "private"
        (a_id, a), (b_id, b) = P9_REQUESTS
        try:
            held_a = ledger.append(led, private, a_id, a)
            first = led.read_bytes()
            held_b = ledger.append(led, private, b_id, b)
            written = led.read_bytes()
        except (ValueError, OSError) as e:
            expect(False, f"the judge writes two requests to a ledger ({type(e).__name__}: {e})")
            return ok()
        # Compared as bytes before anything parses them (review 2817eb7 F3): a rewrite is caught by its bytes, not by
        # the parse error its garbage later causes.
        expect(written.startswith(first), f"request a's {len(first)} bytes unchanged by request b (never rewritten)")
        try:
            rows = [json.loads(line) for line in written.splitlines()]
        except ValueError as e:
            expect(False, f"the ledger parses as JSONL ({type(e).__name__}: {e})")
            return ok()
        expect([{k: v for k, v in r.items() if k not in CHAIN_FIELDS} for r in rows] == a + b,
               f"the ledger holds exactly the {len(a) + len(b)} records given, in order, utilities included: "
               f"{[r.get('utility') for r in rows]}")
        expect([r.get("request_id") for r in rows] == [a_id] * len(a) + [b_id] * len(b), "each record names its request")
        derived = _rechained(rows, lambda rid: hashlib.sha256(rid.encode()).hexdigest())
        expect(rows == derived, "every prev_sha256 and sha256 equals its derivation: first records from the SHA-256 "
                                "of the request_id, each next from the previous sha256")
        anchor = held_b[-1]["sha256"]  # the head the caller holds: the last record `append` returned to it
        code, out = _verify_cli(led, private, anchor)
        print("  " + out.replace("\n", "\n  "))
        expect(code == 0, f"verify passes the ledger as written, anchored at request b's head (exit {code})")
        code, out = _verify_cli(led, private, held_a[-1]["sha256"])
        expect(code == 0, f"verify passes it anchored at request a's head, a later request admitted (exit {code})")
        try:
            ledger.append(led, private, a_id, a)
            expect(False, "a request_id already written is refused")
        except ValueError as e:
            expect(led.read_bytes() == written, f"a request_id already written is refused, ledger unchanged ({e})")

        snapshot = {p.name: p.read_bytes() for p in (led, private / "heads.jsonl")}

        def tampered(name: str, act) -> None:
            act()
            code, out = _verify_cli(led, private, anchor)
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
        tampered("last_request_truncated", lambda: (led.write_bytes(first), (private / "heads.jsonl").write_bytes(
            snapshot["heads.jsonl"].splitlines(keepends=True)[0])))
        tampered("ledger_and_heads_deleted", lambda: (led.unlink(), (private / "heads.jsonl").unlink()))
        tampered("rechained_from_empty_with_key", lambda: _resigned(private, _rechained(rows, lambda rid: ""), led))
        tampered("dropped_and_resigned_with_key", lambda: _resigned(private, [r for i, r in enumerate(rows) if i != 1],
                                                                    led))
        code, _ = _verify_cli(led, private, anchor)
        expect(code == 0, f"the restored ledger verifies again (exit {code}), so each failure above was the tamper's")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return ok()


# P16's parties (brief 1 A4 item 2; CLAUDE.md A1.7) and images: digests the judge never pulls, since registration reads
# nothing of an image but its digest.
P16_BUILDER = {"kind": "builder", "model": "claude-opus-5-5", "session": "p16-builder-session"}
P16_REVIEWER = {"kind": "reviewer", "model": "claude-opus-5-5", "session": "p16-reviewer-session"}
P16_IMAGES = tuple(f"sha256:{c * 64}" for c in "abc")


def _judge_cli(private: Path, *args: str, stdin: str = "") -> tuple[int, str, str]:
    """A judge subcommand, run as the judge runs it, in a child interpreter."""
    r = subprocess.run(proc.python("-m", "judge", args[0], str(private), *args[1:]), cwd=ROOT, env=proc.child_env(),
                       input=stdin, capture_output=True, text=True, timeout=120)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def p16_proposer_from_credential() -> bool:
    """A candidate's proposer is the party whose judge-issued credential registered its image (brief 1 A4 item 2).
    Two credentials register two images, each attributed exactly to its holder, and the judge keeps no token; the same
    party registering again changes nothing; a candidate with no attributable proposer is refused, recording nothing:
    no token, a forged token, a proposer the candidate names itself, or the stored hash of a real token; another
    party's credential cannot take over a registered image; and an unregistered image has no proposer."""
    import hashlib

    from judge import registry

    expect, ok = _expecter()
    work = Path(tempfile.mkdtemp(prefix="assize-p16-", dir=context.scratch))
    try:
        private = work / "private"
        regs = private / registry.REGISTRATIONS
        tokens = {}
        for party in (P16_BUILDER, P16_REVIEWER):
            code, out, err = _judge_cli(private, "credential", party["kind"], party["model"], party["session"])
            expect(code == 0 and len(out) == 64, f"{party['kind']}: credential issued (exit {code}) {err}")
            tokens[party["kind"]] = out
        stored = (private / registry.CREDENTIALS).read_text() if (private / registry.CREDENTIALS).exists() else ""
        expect(bool(stored) and not any(t in stored for t in tokens.values()), "the judge keeps no token, only hashes")
        mode = (private.stat().st_mode & 0o777, (private / registry.CREDENTIALS).stat().st_mode & 0o777
                if stored else None)
        expect(mode == (0o700, 0o600), f"private storage and credentials modes {[m and oct(m) for m in mode]}")

        def registered(image: str, token: str, party: dict) -> None:
            code, out, err = _judge_cli(private, "register", image, stdin=token)
            got = json.loads(out) if code == 0 else err
            print(f"    register {image[:15]}: exit {code}: {got}")
            expect(code == 0 and got.get("proposer") == party and got.get("image") == image,
                   f"{image[:15]} registered to the credential's holder {party['kind']}")
            expect(registry.proposer_of(private, image) == party, f"{image[:15]}: proposer_of is {party['kind']}")

        def refused(label: str, image: str, token: str, want: str) -> None:
            before = regs.read_bytes() if regs.exists() else b""
            code, out, err = _judge_cli(private, "register", image, stdin=token)
            print(f"    {label}: exit {code}: {out or err}")
            expect(code == 1 and f"refused: {want}:" in err and (regs.read_bytes() if regs.exists() else b"") == before,
                   f"{label}: refused {want}, registrations unchanged")

        a, b, c = P16_IMAGES
        registered(a, tokens["builder"], P16_BUILDER)
        registered(b, tokens["reviewer"], P16_REVIEWER)
        rows = registry._lines(regs)
        expect([(r["image"], r["proposer"]) for r in rows] == [(a, P16_BUILDER), (b, P16_REVIEWER)],
               f"the registrations are exactly the two, in order ({len(rows)} rows)")
        before = regs.read_bytes()
        registered(a, tokens["builder"], P16_BUILDER)
        expect(regs.read_bytes() == before, "the same party registering again records nothing new")

        refused("no token", c, "", "unattributed")
        refused("forged token", c, "0" * 64, "unattributed")
        refused("self-named proposer", c, json.dumps(P16_BUILDER | {"kind": "guy"}), "unattributed")
        refused("stored hash of a real token", c, hashlib.sha256(tokens["builder"].encode()).hexdigest(),
                "unattributed")
        refused("another party's credential on a registered image", a, tokens["reviewer"], "registered")
        refused("not a digest", "candidate:latest", tokens["builder"], "bad_image")
        expect(registry.proposer_of(private, a) == P16_BUILDER, "image a's proposer is still the builder")
        try:
            got = registry.proposer_of(private, c)
        except registry.Refused as e:
            got = e.code
        expect(got == "unregistered", f"an image never registered has no proposer ({got})")
        code, _, err = _judge_cli(private, "credential", "candidate", "m", "s")
        expect(code == 1 and "bad_proposer" in err, f"a credential for a kind outside A1.7 is refused (exit {code})")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return ok()


def p5_commitment_order() -> bool:
    """Under every usable runtime, a candidate commits its prediction before the observation it predicts exists for
    it: a clairvoyant fixture, which puts all mass on any observation the step request carries beyond the current
    one and otherwise predicts the floor, records exactly the floor's log-loss over one episode with the same actions,
    so it gains nothing; the floor's log-loss is finite and positive at every target. A judge that sent the next
    observation early would let it score zero (brief 1 section 2, P5)."""
    from harness.fixtures import candidates
    from judge import episodes
    from worlds.crafter import binding

    expect, ok = _expecter()
    m = binding.manifest()
    usable, image = _usable_runtimes(expect)
    def case(rt, expect, say):
        before = _candidates(rt)
        got = {}
        for behaviour in ("floor", "clairvoyant"):
            records = episodes.run(rt, image, _short_crafter(1), m, command=candidates.command(behaviour))
            say(f"  {rt.name} {behaviour}: {json.dumps(records)}")
            expect([(r["termination"], r["steps"]) for r in records] == [("truncated", LOOP_STEPS)],
                   f"{rt.name} {behaviour}: one episode of {LOOP_STEPS} steps, ended by the World")
            got[behaviour] = records[0]["prediction"] if records else {}
        floor, seer = got["floor"], got["clairvoyant"]
        expect(len(floor) == len(m["targets"]) and all(
            v["scored"] == LOOP_STEPS and v["infinite"] == 0 and v["finite_sum"] > 0 for v in floor.values()),
               f"{rt.name}: non-vacuous: the floor scores every declared target finite and positive at every step")
        for name, v in floor.items():
            expect(seer.get(name) == v, f"{rt.name} clairvoyant {name}: log-loss {seer.get(name, {}).get('log_loss')}, "
                                        f"floor {v['log_loss']}: equal, so nothing gained")
        strays = _removing_strays(rt, before)
        expect(not strays, f"{rt.name}: no candidate container listed after the cases ({strays})")

    _each_runtime(usable, case, expect)
    return ok()


# P14 plays the random incumbent (brief 1 section 4) for two episodes in one container, each cut to INCUMBENT_STEPS
# steps: 2 x 100 draws over Crafter's 17 actions expect about 11.8 per action, enough for Pearson's chi-square. Its
# uniformity is refused only below UNIFORM_ALPHA, the false-failure rate the pin accepts per runtime per run, stated
# before any run; a candidate's score never passes through it.
INCUMBENT = ROOT / "incumbents" / "random"
INCUMBENT_EPISODES = 2
INCUMBENT_STEPS = 100
UNIFORM_ALPHA = 1e-6


class _Recording:
    """A World that records each action it is stepped with and each observation it emits, the first included."""

    def __init__(self, world):
        self.world, self.actions, self.observations = world, [], [world.observation]

    def __getattr__(self, name):
        return getattr(self.world, name)

    def step(self, action: int) -> dict:
        self.actions.append(action)
        self.observations.append(self.world.step(action))
        return self.observations[-1]


def _recorded_crafter(n: int, steps: int) -> list[_Recording]:
    from worlds.crafter import binding

    def cut(seed: int):
        ep = binding.Episode(seed)
        ep._env._length = steps
        return _Recording(ep)

    return [cut(seed) for seed in range(1, n + 1)]


def _floor_summary(observations: list[dict], targets) -> dict:
    """What the judge must record for the predictive floor over one episode's observations, derived by definition:
    at step i the floor has seen observations 0..i and puts (1 + count) / (|support| + i + 1) on the value realised at
    i + 1; scored as -ln of it, summed exactly. Independent of `judge/scoring.py` and of the incumbent's code."""

    def one(tg: dict) -> dict:
        f, n = tg["field"], len(tg["support"])
        qs = [(1 + sum(o[f] == nxt[f] for o in observations[:i + 1])) / (n + i + 1)
              for i, nxt in enumerate(observations[1:])]
        return {"scored": len(qs), "missing": 0, "infinite": 0, "finite_sum": math.fsum(-math.log(q) for q in qs),
                "log_loss": math.fsum(-math.log(q) for q in qs)}

    return {tg["name"]: one(tg) for tg in targets}


def _chi2_sf(x: float, df: int) -> float:
    """P(X >= x) for X chi-square with `df` degrees of freedom: the regularised upper gamma Q(df/2, x/2) in its closed
    forms, a finite sum for integer shape and erfc plus a finite sum for half-integer shape."""
    h = x / 2
    if df % 2 == 0:
        return math.exp(-h) * math.fsum(h ** i / math.factorial(i) for i in range(df // 2))
    return math.erfc(math.sqrt(h)) + math.exp(-h) * math.fsum(h ** (i + 0.5) / math.gamma(i + 1.5)
                                                               for i in range((df - 1) // 2))


def _build(rt, context_dir: Path) -> str:
    """Build the image of `context_dir` under `rt` with no network and no pull; return its image id."""
    with tempfile.TemporaryDirectory() as d:
        iid = Path(d) / "iid"
        subprocess.run([rt.binary, "build", "--network=none", "--pull=false", "-q", f"--iidfile={iid}",
                        "-f", str(context_dir / "Containerfile"), str(context_dir)], check=True, capture_output=True)
        return iid.read_text().strip()


def p14_random_incumbent() -> bool:
    """The random incumbent of brief 1 section 4 is a candidate image that exercises the whole path: under every usable
    runtime its image builds offline from the judge's pinned base image and, run by the judge with no command of the
    pin's, plays two episodes in one container, each ended by the World; every action it plays is uniform over the
    legal actions (Pearson's chi-square not refused at UNIFORM_ALPHA); and its recorded log-loss at every declared
    target equals the predictive floor derived by definition from the episode's own observations, per episode, so the
    floor starts afresh in each, finite and positive."""
    from judge import episodes, runtime
    from worlds.crafter import binding

    expect, ok = _expecter()
    m = binding.manifest()
    base = runtime.candidate_config()["base_image"]
    froms = [ln.split()[1] for ln in (INCUMBENT / "Containerfile").read_text().splitlines() if ln.startswith("FROM ")]
    expect(froms == [base], f"the incumbent's one FROM is the judge's pinned base image ({froms}, {base})")
    usable, _ = _usable_runtimes(expect)

    def case(rt, expect, say):
        before = _candidates(rt)
        image = _build(rt, INCUMBENT)
        say(f"  {rt.name} incumbent image: {image}")
        try:
            worlds = _recorded_crafter(INCUMBENT_EPISODES, INCUMBENT_STEPS)
            records = episodes.run(rt, image, worlds, m)
        finally:
            subprocess.run([rt.binary, "rmi", "-f", image], capture_output=True)
        say(f"  {rt.name} incumbent: {json.dumps(records)}")
        expect([r["termination"] in episodes.WORLD_ENDINGS for r in records] == [True] * INCUMBENT_EPISODES,
               f"{rt.name}: {INCUMBENT_EPISODES} episodes, each ended by the World "
               f"({[(r['termination'], r['steps']) for r in records]})")
        for r, w in zip(records, worlds):
            want = _floor_summary(w.observations, m["targets"])
            expect(len(w.actions) == r["steps"] > 0 and all(v["finite_sum"] > 0 for v in want.values()),
                   f"{rt.name} episode {r['episode']}: non-vacuous: {r['steps']} steps, the floor positive everywhere")
            for name, v in want.items():
                got = r["prediction"].get(name)
                expect(got == v, f"{rt.name} episode {r['episode']} {name}: recorded {got}, floor derived {v}")
        k = len(m["actions"])
        played = [a for w in worlds for a in w.actions]
        counts = [played.count(a) for a in range(k)]
        e = len(played) / k
        chi2 = math.fsum((c - e) ** 2 / e for c in counts)
        p = _chi2_sf(chi2, k - 1)
        say(f"  {rt.name} actions: {len(played)} played, counts {counts}; chi-square {chi2:.3f}, df {k - 1}, p {p:.3g}")
        expect(all(w.legal_actions == list(range(k)) for w in worlds),
               f"{rt.name}: the legal set is all {k} actions, so uniform means {e:.2f} each")
        expect(p >= UNIFORM_ALPHA, f"{rt.name}: actions uniform over the legal ones: p {p:.3g} >= {UNIFORM_ALPHA}")
        strays = _removing_strays(rt, before)
        expect(not strays, f"{rt.name}: no candidate container listed after the cases ({strays})")

    _each_runtime(usable, case, expect)
    return ok()


# P15's fixture: per-episode utilities 0 and 2, half each, so variance 1 (population) and an independent oracle in
# closed form: with each arm's posterior mean normal, the expected posterior mass on the correct sign at m episodes
# per arm is Phi(delta / (2 sigma / sqrt(m))), which reaches q at m = 4 sigma^2 Phi^-1(q)^2 / delta^2.
TTL_UTILITIES = (0,) * 100 + (2,) * 100
# The pin's criterion: the Bayesian bootstrap's m* within this factor of the normal oracle's. A pin constant, stated
# before any run; no candidate's score passes through it.
TTL_FACTOR = 1.5
BRIEF_PILOT = {"world": "crafter", "episodes": 200, "cap_s": 7200}
BRIEF_TTL = {"deltas": [0.25, 0.5, 1.0], "mass": 0.9, "fit_delta": 0.5, "marginal_delta": 1.0, "budget_s": 86400}


def p15_time_to_learn() -> bool:
    """Brief 1 section 5's committed pilot size, cap, shifts, mass and FIT/MARGINAL criteria are the brief's; on a
    fixture whose answer is known in closed form, the Bayesian-bootstrap time-to-learn finds, for every shift, the
    smallest episodes per arm whose expected posterior mass on the correct sign reaches the mass, within TTL_FACTOR of
    the normal oracle; the wall-clock counts both arms; and the verdict is FIT, MARGINAL or UNFIT as the budget affords
    the oracle's episodes for 0.5, only for 1, or for neither."""
    import statistics

    from pilot import timetolearn as ttl

    expect, ok = _expecter()
    whole = ttl.config()
    cfg = whole["time_to_learn"]
    expect(whole["pilot"] == BRIEF_PILOT, f"pilot config is the brief's default ({whole['pilot']})")
    expect({k: cfg[k] for k in BRIEF_TTL} == BRIEF_TTL, f"time-to-learn config is the brief's ({cfg})")

    mean = statistics.fmean(TTL_UTILITIES)
    var = statistics.fmean((u - mean) ** 2 for u in TTL_UTILITIES)
    z = statistics.NormalDist().inv_cdf(cfg["mass"])
    oracle = {d: 4 * var * z * z / (d * d) for d in cfg["deltas"]}
    cap = math.ceil(TTL_FACTOR * 2 * max(oracle.values()))
    found = {}
    for d in cfg["deltas"]:
        got = ttl.episodes_per_arm(TTL_UTILITIES, d, cap, cfg)
        found[d] = got
        print(f"  delta {d}: episodes per arm {got}, normal oracle {oracle[d]:.2f}")
        expect(got is not None and oracle[d] / TTL_FACTOR <= got[0] <= oracle[d] * TTL_FACTOR,
               f"delta {d}: m* {got and got[0]} within x{TTL_FACTOR} of the oracle {oracle[d]:.2f}")
        if got is not None:
            expect(got[1] >= cfg["mass"], f"delta {d}: measure at m* {got[1]:.4f} >= {cfg['mass']}")
            below = ttl.measure(TTL_UTILITIES, d, got[0] - 1, cfg) if got[0] > 1 else None
            expect(below is None or below < cfg["mass"], f"delta {d}: m* is the smallest: measure at m*-1 {below}")

    flat = ttl.episodes_per_arm((3,) * 50, cfg["fit_delta"], cap, cfg)
    expect(flat == (1, 1.0), f"no incumbent variance: one episode per arm, all mass on the correct sign ({flat})")

    # Budgets at the boundaries the search found: exactly m* for 0.5, one short of it, and one short of m* for 1.
    # Counting one arm would double each and move the last two verdicts up.
    m_fit, m_marg = (found[cfg[k]] and found[cfg[k]][0] for k in ("fit_delta", "marginal_delta"))
    expect(m_fit is not None and m_marg is not None and 1 < m_marg < m_fit,
           f"fixture separates the verdicts: m* {m_marg} for {cfg['marginal_delta']} < m* {m_fit} for {cfg['fit_delta']}")
    if m_fit is None or m_marg is None:
        return ok()
    budget = cfg["budget_s"]
    affords = {"FIT": m_fit, "MARGINAL": m_fit - 1, "UNFIT": m_marg - 1}
    for want, k in affords.items():
        throughput = (2 * k + 0.5) / budget  # a quarter-episode spare per arm, so rounding never costs one
        rows = ttl.table(TTL_UTILITIES, throughput, cfg)
        got = ttl.verdict(rows, cfg)
        print(f"  {k} episodes per arm affordable: {[(r.delta, r.episodes_per_arm, r.wall_s) for r in rows]}")
        expect(ttl.affordable(throughput, cfg) == k, f"{want}: the budget affords {k} episodes per arm, both arms run")
        expect(all(r.wall_s == 2 * r.episodes_per_arm / throughput for r in rows if r.episodes_per_arm is not None),
               f"{want}: wall-clock counts both arms")
        expect(got == want, f"{k} episodes per arm affordable: verdict {got}, want {want}")
    return ok()

# P17 registers the random incumbent's image under one credential and asks `evaluate` for EVALUATE_EPISODES full
# Crafter episodes of it; a random player dies within a few hundred steps, so each costs about a second.
P17_PARTY = {"kind": "builder", "model": "claude-opus-5-5", "session": "p17-builder-session"}
EVALUATE_EPISODES = 2
# What `judge_sha256` must cover, from the root: P17 changes one byte of each in a copy and requires a new hash.
JUDGE_HASHED = ("judge/config.toml", "judge/episodes.py", "worlds/spec/rpc.schema.json",
                "worlds/crafter/manifest.json", "worlds/crafter/binding.py", "uv.lock")


def _digest(iid: str) -> str:
    return iid if iid.startswith("sha256:") else f"sha256:{iid}"


def _judge_hash_by_definition(root: Path) -> str:
    """SHA-256 over every file of judge/, worlds/ and uv.lock under `root` but bytecode caches, in path order: path,
    NUL, the SHA-256 of its bytes, newline. Derived here from the definition, independently of `judge/evaluate.py`."""
    import hashlib

    files = sorted(f.relative_to(root).as_posix() for top in ("judge", "worlds") for f in (root / top).rglob("*")
                   if f.is_file() and "__pycache__" not in f.relative_to(root).parts) + ["uv.lock"]
    h = hashlib.sha256()
    for rel in sorted(files):
        h.update(rel.encode() + b"\0" + hashlib.sha256((root / rel).read_bytes()).hexdigest().encode() + b"\n")
    return h.hexdigest()


def _keys(x) -> set[str]:
    if isinstance(x, dict):
        return set(x) | {k for v in x.values() for k in _keys(v)}
    return {k for v in x for k in _keys(v)} if isinstance(x, list) else set()


def p17_evaluate() -> bool:
    """`evaluate(image, world, n_episodes, request_id)` (brief 1 section 2; A4 items 1 and 2). Under every usable
    runtime, the random incumbent's image, registered under one judge-issued credential, is evaluated on two fresh
    Crafter seeds: two records, each ended by the World and carrying `schema_version`, the image digest, the
    registering party as `proposer`, the judge hash derived by definition, the World, its achievement set (utility its
    size) and no seed; the ledger verifies and holds exactly them, and the seed store exactly the request's two seeds.
    The same request asked again, from a child interpreter, prints the same records and changes nothing; asked of
    another episode count it is refused `request_conflict`. A present but unregistered image is refused `unregistered`
    with the seed store and ledger unchanged, so no seed is issued to it; a request whose seeds were issued but never
    signed is refused `interrupted`. The judge hash changes when any of judge config and code, the interface, the
    Crafter binding and manifest, or the lock file changes."""
    from judge import episodes, evaluate, ledger, registry, runtime, seeds
    from worlds.crafter import binding

    expect, ok = _expecter()
    want_hash = _judge_hash_by_definition(ROOT)
    work = Path(tempfile.mkdtemp(prefix="assize-p17-", dir=context.scratch))
    try:
        copy = work / "copy"
        for top in ("judge", "worlds"):
            shutil.copytree(ROOT / top, copy / top, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy2(ROOT / "uv.lock", copy / "uv.lock")
        base = evaluate.judge_hash(copy)
        expect(base == want_hash == evaluate.judge_hash(), f"judge_hash is the definition's ({base[:12]})")
        for rel in JUDGE_HASHED:
            original = (copy / rel).read_bytes()
            (copy / rel).write_bytes(original + b" ")
            changed = evaluate.judge_hash(copy)
            (copy / rel).write_bytes(original)
            expect(changed != base, f"judge_hash changes when {rel} changes ({changed[:12]})")
        components = binding.crafter.constants.achievements
        usable, base_image = _usable_runtimes(expect)

        def case(rt, expect, say):
            before = _candidates(rt)
            private, ledgers = work / rt.name / "private", work / rt.name / "ledgers"
            led = evaluate.ledger_path(ledgers, "crafter")
            store = private / "crafter.seeds.jsonl"
            image = _digest(_build(rt, INCUMBENT))
            other = _digest(subprocess.run([rt.binary, "image", "inspect", "--format", "{{.Id}}", base_image],
                                           capture_output=True, text=True, check=True).stdout.strip())
            say(f"  {rt.name} incumbent image {image}; unregistered present image {other}")

            def snapshot() -> tuple[bytes, bytes]:
                return tuple(p.read_bytes() if p.exists() else b"" for p in (store, led))

            def refused(label: str, want: str, *args, **kw) -> None:
                was = snapshot()
                try:
                    evaluate.evaluate(*args, private=private, ledgers=ledgers, runtime_name=rt.name, **kw)
                    got = "evaluated"
                except (registry.Refused, seeds.SeedError) as e:
                    got = e.code
                expect(got == want and snapshot() == was,
                       f"{rt.name} {label}: refused {want} (got {got}), seed store and ledger unchanged")

            try:
                registry.register(private, image, registry.credential(private, P17_PARTY))
                refused("unregistered image", "unregistered", other, "crafter", EVALUATE_EPISODES, "p17-other")
                got = evaluate.evaluate(image, "crafter", EVALUATE_EPISODES, "p17-a", private=private,
                                        ledgers=ledgers, runtime_name=rt.name)
                say(f"  {rt.name} evaluate p17-a: {json.dumps(got)}")
                expect([(r["episode"], r["termination"] in episodes.WORLD_ENDINGS) for r in got]
                       == [(i, True) for i in range(EVALUATE_EPISODES)],
                       f"{rt.name}: {EVALUATE_EPISODES} records, in order, each ended by the World "
                       f"({[(r['termination'], r['steps']) for r in got]})")
                stamped = {"schema_version": episodes.SCHEMA_VERSION, "image": image, "proposer": P17_PARTY,
                           "judge_sha256": want_hash, "world": "crafter", "n_episodes": EVALUATE_EPISODES}
                for r in got:
                    for k, v in stamped.items():
                        expect(r.get(k) == v, f"{rt.name} episode {r['episode']}: {k} is {r.get(k)!r}, want {v!r}")
                    expect(set(r["achievements"]) <= set(components) and r["utility"] == len(r["achievements"]),
                           f"{rt.name} episode {r['episode']}: utility {r['utility']} is the size of its achievement "
                           f"set {r['achievements']}")
                    expect(not _keys(r) & {"seed", "seeds", "key"}, f"{rt.name} episode {r['episode']}: no seed")
                expect(ledger.verify(led, private, got[-1]["sha256"]) == [] and ledger._lines(led) == got,
                       f"{rt.name}: the ledger verifies and holds exactly the request's records")
                issued = seeds.records(private, "crafter")
                expect([r["request_id"] for r in issued] == ["p17-a"] * EVALUATE_EPISODES,
                       f"{rt.name}: the seed store holds exactly the request's {EVALUATE_EPISODES} seeds")

                was = snapshot()
                code, out, err = _judge_cli(private, "evaluate", str(ledgers), rt.name, image, "crafter",
                                            str(EVALUATE_EPISODES), "p17-a")
                again = [json.loads(line) for line in out.splitlines()] if code == 0 else err
                expect(again == got and snapshot() == was,
                       f"{rt.name}: p17-a asked again from a child interpreter prints the same records, changing "
                       f"nothing (exit {code}{'' if code == 0 else ': ' + err})")
                refused("p17-a of another episode count", "request_conflict", image, "crafter",
                        EVALUATE_EPISODES + 1, "p17-a")
                seeds.issue(private, "crafter", binding.world_seed, 1, "p17-b")
                refused("seeds issued, records never signed", "interrupted", image, "crafter", 1, "p17-b")
            finally:
                subprocess.run([rt.binary, "rmi", "-f", image], capture_output=True)
            strays = _removing_strays(rt, before)
            expect(not strays, f"{rt.name}: no candidate container listed after the cases ({strays})")

        _each_runtime(usable, case, expect)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return ok()


# P18's fixture pilot (brief 1 section 5; A4 items 2 and 3): 25 episodes asked in requests of 10, two of them crashes
# with utility 0, one with an infinite loss on target `a`. The judge's records are faked, so the pin starts no container;
# what it pins is how the pilot asks, stops and reports, which reads nothing but records. Every number below is the
# fixture's, stated before any run; no candidate's score passes through it.
P18_CFG = {"pilot": {"world": "crafter", "episodes": 25, "cap_s": 1000.0}, "requests": {"episodes": 10},
           "time_to_learn": {"deltas": [0.25, 0.5, 1.0], "mass": 0.9, "fit_delta": 0.5, "marginal_delta": 1.0,
                             "budget_s": 86400, "experiments": 200, "posterior_draws": 200, "seed": 0},
           "incumbent": {"context": "incumbents/random",
                         "proposer": {"kind": "guy", "model": "", "session": "not-the-registering-party"}}}
P18_PARTY = {"kind": "builder", "model": "claude-opus-5-5", "session": "p18-registering-party"}
P18_TARGETS = ("a", "b")
P18_COMPONENTS = ("x", "y", "z")
P18_CRASHES = (3, 17)
P18_INFINITE = 5
P18_STEP_S = 1.0  # the fake clock's advance per reading: the pilot's wall-clock far exceeds its episodes' compute wall


def _p18_record(i: int, proposer: dict = P18_PARTY) -> dict:
    crash = i in P18_CRASHES
    achieved = [] if crash else list(P18_COMPONENTS[: 1 + i % 3])

    def pred(name: str) -> dict:
        inf = int(name == "a" and i == P18_INFINITE)
        return {"scored": 10, "missing": i % 2, "infinite": inf, "finite_sum": 1.0 + i, "log_loss": "+inf" if inf
                else 1.0 + i}

    def cal(name: str) -> dict:
        return {"entropy_sum": 0.5 * (i + 1), "mean_entropy": 0.05 * (i + 1),
                "reliability": {"bins": 2, "n": [[i % 10, 10 - i % 10], [10 - i % 10, i % 10]], "hits": [[0, 1], [1, 0]],
                                "p_sum": [[0.25, 0.5], [0.5, 0.25]]}}

    return {"episode": i, "termination": "crash" if crash else "terminal", "utility": len(achieved),
            "achievements": achieved, "proposer": proposer, "judge_sha256": "f" * 64, "image": "sha256:" + "e" * 64,
            "world": "crafter", "runtime": "fake", "prediction": {t: pred(t) for t in P18_TARGETS},
            "calibration": {t: cal(t) for t in P18_TARGETS},
            "compute": {"cpu_s": 0.01, "wall_s": 0.02, "unmeasured_s": 0.0, "peak_memory_bytes": 1000 + i,
                        "peak_memory_scope": "container_since_start"},
            "price": {"cpu": 0.0, "memory": 0.0, "total": 1e-6 * i}}


def _p18_clock(step: float = P18_STEP_S):
    t = [0.0]

    def clock() -> float:
        t[0] += step
        return t[0]

    return clock


def p18_pilot() -> bool:
    """Brief 1 section 5's pilot runner (`pilot/run.py`) over a faked `evaluate()`. The 25 episodes are asked in
    requests of 10, 10 and 5 under distinct request ids, and every record enters the report: the crashes' utilities
    among the per-episode utilities and terminations (none dropped); the throughput is recorded episodes over the
    pilot's wall-clock, not over its episodes' compute; the proposer is the one the records carry, not the config's,
    and records of two proposers are no pilot; a target with an infinite step has log-loss +inf; reliability tables add.
    The cap passing before the episodes complete, a refused request, or a request returning fewer records than asked,
    each stops the pilot with the records it has and no verdict."""
    from judge import registry
    from pilot import run
    from worlds.crafter import binding

    expect, ok = _expecter()
    asked: list[tuple[str, int]] = []

    def ask(rid: str, n: int, short: bool = False, refuse_at: int | None = None, mixed: bool = False) -> list[dict]:
        if refuse_at is not None and len(asked) == refuse_at:
            raise registry.Refused("interrupted", f"{rid}: fixture refusal")
        start = sum(k for _, k in asked)
        asked.append((rid, n))
        return [_p18_record(i, P18_CFG["incumbent"]["proposer"] if mixed and i == start else P18_PARTY)
                for i in range(start, start + n - short)]

    def pilot(**kw):
        asked.clear()
        clock = kw.pop("clock", _p18_clock())
        played = run.play(lambda rid, n: ask(rid, n, **kw), "p18", P18_CFG, refusals=(registry.Refused,),
                          clock=clock)
        return played, run.report(played, P18_CFG, P18_TARGETS, P18_COMPONENTS, binding.hafner_score,
                                  evidence=False)

    played, rep = pilot()
    print(f"  full pilot: requests {asked}; verdict {rep['verdict']}; terminations {rep['episodes']['terminations']}")
    every = [_p18_record(i) for i in range(25)]
    expect([n for _, n in asked] == [10, 10, 5] and len({r for r, _ in asked}) == 3,
           f"25 episodes asked in requests of 10, 10, 5 under distinct ids ({asked})")
    expect(rep["episodes"]["recorded"] == 25 and rep["episodes"]["terminations"] == {"crash": 2, "terminal": 23},
           f"every record counted, crashes included ({rep['episodes']})")
    expect(rep["utility"]["per_episode"] == [r["utility"] for r in every] and rep["utility"]["n"] == 25,
           f"per-episode utilities are every episode's, crashes' zeros included ({rep['utility']['counts']})")
    expect(rep["verdict"] in {"FIT", "MARGINAL", "UNFIT"} and len(rep["time_to_learn"]["rows"]) == 3,
           f"a completed pilot states a verdict and a time-to-learn row per shift ({rep['verdict']})")
    expect(rep["throughput_episodes_per_s"] == 25 / played.wall_s and played.wall_s > 25 * 0.02,
           f"throughput is recorded episodes over the pilot's wall-clock {played.wall_s} s "
           f"({rep['throughput_episodes_per_s']})")
    expect(rep["proposer"] == P18_PARTY, f"the report's proposer is the records' ({rep['proposer']})")
    rates = [100 * sum(c in r["achievements"] for r in every) / 25 for c in P18_COMPONENTS]
    hafner = math.exp(math.fsum(math.log(1 + s) for s in rates) / len(rates)) - 1
    expect(math.isclose(rep["hafner_score"], hafner), f"Hafner score {rep['hafner_score']} is {hafner}")
    a, b = rep["prediction"]["a"], rep["prediction"]["b"]
    finite = math.fsum(1.0 + i for i in range(25))
    expect(a["log_loss_per_step"] == "+inf" and a["infinite"] == 1,
           f"a target with an infinite step has log-loss +inf, counted ({a})")
    expect(b["log_loss_per_step"] == finite / 250 and b["missing"] == 12 and b["scored"] == 250,
           f"a finite target's log-loss per scored step is its finite sum over 250 scored, 12 missing ({b})")
    rel = rep["calibration"]["a"]["reliability"]
    expect(rel["n"] == [[100, 150], [150, 100]] and rel["hits"] == [[0, 25], [25, 0]]
           and rep["calibration"]["a"]["mean_entropy"] == 0.5 * 325 / 250,
           f"reliability tables and entropies add over episodes ({rel['n']}, {rep['calibration']['a']['mean_entropy']})")

    played, rep = pilot(clock=_p18_clock(P18_CFG["pilot"]["cap_s"] / 3))
    print(f"  cap pilot: requests {asked}; verdict {rep['verdict']}")
    expect(rep["verdict"].startswith("STOPPED: cap") and rep["episodes"]["recorded"] == 10
           and rep["time_to_learn"]["rows"] == [],
           f"the cap passing after one request stops the pilot with its 10 records and no verdict "
           f"({rep['verdict']}, {rep['episodes']['recorded']})")
    played, rep = pilot(refuse_at=1)
    expect(rep["verdict"].startswith("STOPPED: refused") and rep["episodes"]["recorded"] == 10,
           f"a refused request stops the pilot with the records it has ({rep['verdict']})")
    played, rep = pilot(short=True)
    expect(rep["verdict"].startswith("STOPPED: request") and rep["episodes"]["recorded"] == 9,
           f"a request returning 9 of 10 records stops the pilot ({rep['verdict']})")
    played, rep = pilot(mixed=True)
    expect(rep["verdict"].startswith("STOPPED: records carry 2 proposer") and rep["time_to_learn"]["rows"] == [],
           f"records of two proposers are no pilot ({rep['verdict']})")
    return ok()


PINS = [
    Pin("P0", "surviving mutants are reported and fail the suite",
        p0_survivors_reported, (Mutant("survivors_ignored", _edits("P0_survivors_ignored")),)),
    Pin("P0b", "no code reads a mutant or test variable from the environment",
        p0b_no_switches, (Mutant("env_switch", _edits("P0b_env_switch")),
                         Mutant("judge_imports_mutants", _edits("P0b_judge_imports_mutants")))),
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
    Pin("P0k", "a forecasts.jsonl resolution lacking id, ts, proposer or outcome, matching no forecast, or by its "
        "forecast's session, is rejected",
        p0k_forecast_ledger, (Mutant("proposer_check_dropped", _edits("P0k_proposer_check_dropped")),
                              Mutant("self_resolution_admitted", _edits("P0k_self_resolution_admitted")))),
    Pin("P0l", "a verdict citing a pins run on another sha, or one not concluded success, is rejected",
        p0l_ci_claims, (Mutant("sha_comparison_skipped", _edits("P0l_sha_comparison_skipped")),)),
    Pin("P0m", "a commit touching an entrenched path without a guy Proposer or a gfrmin instruction is rejected; "
        "every party is read",
        p0m_commit_proposers, (Mutant("trailer_check_disabled", _edits("P0m_trailer_check_disabled")),
                                Mutant("first_proposer_only", _edits("P0m_first_proposer_only")),
                                Mutant("exemption_unkeyed", _edits("P0m_exemption_unkeyed")),
                                Mutant("exemption_party_unchecked", _edits("P0m_exemption_party_unchecked")),
                                Mutant("unknown_merge_author", _edits("P0m_unknown_merge_author")),
                                Mutant("instruction_author_unchecked", _edits("P0m_instruction_author_unchecked")),
                                Mutant("instruction_label_unchecked", _edits("P0m_instruction_label_unchecked")),
                                Mutant("instruction_labeler_unchecked", _edits("P0m_instruction_labeler_unchecked")),
                                Mutant("body_edit_unchecked", _edits("P0m_body_edit_unchecked")),
                                Mutant("inert_exemption_admitted", _edits("P0m_inert_exemption_admitted")))),
    Pin("P0n", "merged pull requests are ranked by the Builder's cumulative log-loss on their forecasts, largest first",
        p0n_surprise_ranking, (Mutant("ranking_reversed", _edits("P0n_ranking_reversed")),)),
    Pin("P0o", "a proposer's record per class counts an overturned act as a failure, never a success",
        p0o_proposer_record, (Mutant("overturned_scored_success", _edits("P0o_overturned_scored_success")),)),
    Pin("P0q", "a commit removing a line of a ledger, review, audit or REPORT.md is rejected; a merge of appends is not",
        p0q_append_only, (Mutant("ledger_rewrite_admitted", _edits("P0q_ledger_rewrite_admitted")),)),
    Pin("P0r", "a forecast row a pull request adds after the head of its first pins run is late",
        p0r_claims_precede_scoring, (Mutant("late_forecast_admitted", _edits("P0r_late_forecast_admitted")),)),
    Pin("P0s", "typed forecasts are resolved by code from what the API shows; free ones never by the mechanism",
        p0s_outcomes_by_code, (Mutant("outcome_inverted", _edits("P0s_outcome_inverted")),
                               Mutant("free_resolved_by_mechanism", _edits("P0s_free_resolved_by_mechanism")))),
    Pin("P0t", "every item that reached Guy is counted once, with its latency, answered or not",
        p0t_price, (Mutant("latency_dropped", _edits("P0t_latency_dropped")),
                    Mutant("guy_items_undercounted", _edits("P0t_guy_items_undercounted")))),
    Pin("P0u", "a procedure's model is drawn by Hedge over its entrants' log-loss, never by argmin",
        p0u_election, (Mutant("argmin_election", _edits("P0u_argmin_election")),)),
    Pin("P1", "evaluation seeds come from a CSPRNG, are recorded privately, and are never reissued or training seeds",
        p1_seed_issuance, (Mutant("seed_reissued", _edits("P1_seed_reissued")),
                           Mutant("reuse_check_skipped", _edits("P1_reuse_check_skipped")),
                           Mutant("domain_check_skipped", _edits("P1_domain_check_skipped")),
                           Mutant("training_undomained", _edits("P1_training_undomained")))),
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
    Pin("P5", "a clairvoyant candidate gains nothing over the predictive floor: no observation is sent early",
        p5_commitment_order, (Mutant("next_sent_early", _edits("P5_next_sent_early")),)),
    Pin("P14", "the random incumbent's image plays uniformly over legal actions and records exactly the predictive floor",
        p14_random_incumbent, (Mutant("first_legal_action", _edits("P14_first_legal_action")),
                               Mutant("floor_unsmoothed", _edits("P14_floor_unsmoothed")),
                               Mutant("seen_not_reset", _edits("P14_seen_not_reset")))),
    Pin("P15", "time-to-learn finds the episodes per arm a known shift needs, counts both arms, and states the verdict",
        p15_time_to_learn, (Mutant("abs_difference", _edits("P15_abs_difference")),
                            Mutant("shift_dropped", _edits("P15_shift_dropped")),
                            Mutant("one_arm", _edits("P15_one_arm")),
                            Mutant("budget_one_arm", _edits("P15_budget_one_arm")))),
    Pin("P7", "zero mass on a realised outcome is recorded +inf, never clipped; missing is never imputed",
        p7_infinite_loss, (Mutant("clipped", _edits("P7_clipped")),
                           Mutant("missing_imputed", _edits("P7_missing_imputed")),
                           Mutant("sum_unchecked", _edits("P7_sum_unchecked")))),
    Pin("P13", "every scored step, +inf included, enters each support value's reliability row; entropy is never imputed",
        p13_calibration, (Mutant("infinite_dropped", _edits("P13_infinite_dropped")),
                          Mutant("realised_row_only", _edits("P13_realised_row_only")),
                          Mutant("entropy_missing_imputed", _edits("P13_entropy_missing_imputed")))),
    Pin("P9", "a ledger record dropped, altered or rechained, a head forged, or the tail truncated, fails the judge's "
              "verification",
        p9_ledger_tamper, (Mutant("record_dropped", _edits("P9_record_dropped")),
                           Mutant("utility_altered", _edits("P9_utility_altered")),
                           Mutant("chain_update_skipped", _edits("P9_chain_update_skipped")),
                           Mutant("opened_for_rewrite", _edits("P9_opened_for_rewrite")),
                           Mutant("genesis_empty", _edits("P9_genesis_empty")),
                           Mutant("signature_unchecked", _edits("P9_signature_unchecked")),
                           Mutant("independent_heads", _edits("P9_independent_heads")))),
    Pin("P16", "a candidate's proposer comes from the judge-issued credential that registered it, or it is refused",
        p16_proposer_from_credential, (Mutant("unattributed_admitted", _edits("P16_unattributed_admitted")),
                                       Mutant("any_credential", _edits("P16_any_credential")),
                                       Mutant("registration_taken_over", _edits("P16_registration_taken_over")))),
    Pin("P17", "evaluate() stamps every record with its registered proposer, issues no seed unregistered, is idempotent",
        p17_evaluate, (Mutant("fixed_proposer", _edits("P17_fixed_proposer")),
                       Mutant("seeds_before_proposer", _edits("P17_seeds_before_proposer")),
                       Mutant("idempotency_dropped", _edits("P17_idempotency_dropped")),
                       Mutant("conflict_unchecked", _edits("P17_conflict_unchecked")),
                       Mutant("hash_partial", _edits("P17_hash_partial")))),
    Pin("P18", "the pilot records every episode, stops at the cap, and reports the records' proposer and throughput",
        p18_pilot, (Mutant("cap_ignored", _edits("P18_cap_ignored")),
                    Mutant("failures_dropped", _edits("P18_failures_dropped")),
                    Mutant("throughput_from_episodes", _edits("P18_throughput_from_episodes")),
                    Mutant("proposer_from_config", _edits("P18_proposer_from_config")),
                    Mutant("mixed_proposers_admitted", _edits("P18_mixed_proposers_admitted")),
                    Mutant("infinite_pooled_finite", _edits("P18_infinite_pooled_finite")),
                    Mutant("short_request_admitted", _edits("P18_short_request_admitted")))),
    Pin("P12", "every episode's compute is priced by the committed rule; peak memory's scope is stated and followed",
        p12_compute_price, (Mutant("peak_differenced", _edits("P12_peak_differenced")),
                            Mutant("unmeasured_free", _edits("P12_unmeasured_free")))),
    Pin("P19", "a World is bound by its directory alone, a manifest beside a binding; no manifest, no binding",
        p19_world_discovery, (Mutant("world_table_hardcoded", _edits("P19_world_table_hardcoded")),)),
    Pin("P20", "a World is priced from its own manifest; evaluate() refuses one that commits no price",
        p20_world_price, (Mutant("crafter_price_fallback", _edits("P20_crafter_price_fallback")),)),
    Pin("P21", "replay returns a request's records only if they match its signed head, else refuses ledger_unverified",
        p21_replay_verified, (Mutant("replay_unchecked", _edits("P21_replay_unchecked")),)),
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
