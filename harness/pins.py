"""The harness's own pins (L0, brief 0 A2). Each kills its named mutant, an anchored edit to the harness,
and each kill is causal: the mutant run fails and its unedited twin passes."""

from __future__ import annotations

import dataclasses
import json
import math
import os
import py_compile
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

from harness import claims, config, context, edits, proc, runner, scan, tree
from harness.fixtures import daemon, escapee, leaky, witness
from harness.nested import run_nested
from harness.pin import ALWAYS, ROOT, Mutant, Pin, RegistryError, validate


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
    from harness import ledger
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

    root = _real_root()
    layers = sorted(root.glob("reports/L*"))
    expect(bool(layers), f"real layers found: {[str(p.relative_to(root)) for p in layers]}")
    for layer in layers:
        frozen = layer / "forecasts.jsonl"
        own = sorted((layer / "forecasts").glob("*.jsonl"))
        if not frozen.exists() and not own:
            continue
        # A resolution may sit in another session's file than its forecast: a layer's ledger is the frozen file's rows,
        # then every file under forecasts/ ordered by ts then id (instruction #135).
        later = ledger.ordered([r for p in own for r in map(json.loads, filter(str.strip, p.read_text().splitlines()))])
        lines = (frozen.read_text().splitlines() if frozen.exists() else []) + [json.dumps(r) for r in later]
        got = claims.ledger_findings(lines)
        allowed = L0_PRE_RULE if layer.name == "L0" else set()
        for f in got:
            print(f"    {layer.name}: {f}")
        expect(_codes(got) == allowed if allowed else not got,
               f"{layer.relative_to(root)}: {len(lines)} rows in {1 + len(own) if frozen.exists() else len(own)} files, "
               f"{len(got)} findings; expected exactly {sorted(allowed) or 'none'}")
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
    statuses = sorted(p for g in claims.STATUS_GLOBS for p in root.glob(g)
                      if int(re.search(r"/L(\d+)/", f"/{p.relative_to(root)}").group(1)) >= 1)
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

    # Wish #179 (instruction #181): the disposition of L1 obligations 44-55.
    registry = {p.name: frozenset(p.label(m) for m in p.mutants) for p in PINS}
    carried = "carried to the agent repository as a design input: x"
    good = f"discharged by P0l (instruction #1); mutant P0l/sha_comparison_skipped; pins CI run 1 on {a}: x"
    table = lambda **over: "\n".join(f"{i}. {over.get(f'n{i}', carried)}" for i in range(44, 56) if f"n{i}" not in over
                                      or over[f"n{i}"] is not None)
    for label, text, want in (
            ("every row carried", table(), set()),
            ("one row discharged by a registry pin and mutant", table(n45=good), set()),
            ("a number missing", table(n50=None), {"missing"}),
            ("a number twice", table() + f"\n47. {carried}", {"duplicate"}),
            ("both dispositions", table(n46=f"{good} and {carried}"), {"disposition"}),
            ("neither disposition", table(n47="x"), {"disposition"}),
            ("a nonexistent pin", table(n48=good.replace("P0l (", "P0zz (").replace("P0l/", "P0zz/")), {"not_in_registry"}),
            ("a nonexistent mutant", table(n49=good.replace("sha_comparison_skipped", "nope")), {"not_in_registry"}),
            ("no CI run cited", table(n51=good.split("; pins CI")[0]), {"discharge_uncited"})):
        got = {f.code for f in claims.obligation_findings("fixture", text, registry, 44, 55)}
        expect(got == want, f"obligations table {label}: findings {sorted(got)}, want {sorted(want)}")
    path = root / "reports" / "L2" / "obligations-44-55.md"
    expect(path.exists(), "reports/L2/obligations-44-55.md exists")
    got = claims.obligation_findings(str(path.relative_to(root)), path.read_text() if path.exists() else "", registry, 44, 55)
    expect(not got, f"reports/L2/obligations-44-55.md: findings {[str(f) for f in got]}")
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
    _append(repo, "reports/draws.jsonl", '{"drawn": "m-a"}\n')
    git("add", "-A")
    git("commit", "-q", "-m", "base")
    base = git("rev-parse", "HEAD")
    _append(repo, "reports/L1/forecasts.jsonl", '{"id": "b"}\n')
    git("commit", "-qam", "appends")
    shas = {"appending": git("rev-parse", "HEAD")}
    (repo / "REPORT.md").write_text("# report\n- L0 — FAILED\n")
    (repo / "reports/draws.jsonl").write_text('{"drawn": "m-b"}\n')
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
    """Every commit on the branch only adds lines to the ledgers, the draw ledger, review and audit files and the root
    REPORT.md, and
    a merge only adds lines relative to each of its parents (rule 1 of the ground, instruction #54 item 1)."""
    expect, ok = _expecter()
    work = Path(tempfile.mkdtemp(prefix="assize-p0q-", dir=context.scratch))
    base, shas = _append_only_repo(work / "repo")
    got = claims.append_only(work / "repo", base)
    for f in got:
        print(f"    fixture: {f}")
    expect({(f.where, f.code) for f in got} == {(f"commit {shas['rewriting'][:12]}", "ledger_rewrite")}
           and any("REPORT.md" in f.detail for f in got) and any("reports/draws.jsonl" in f.detail for f in got),
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


def _typed(claim: str, p: float, ftype: str | None, args: dict, ts: str = "2026-01-10T00:00:00Z",
           resolves_by: str = "the resolver") -> dict:
    f = {"id": claims.forecast_id(claim, ts), "ts": ts, "proposer": LEDGER_PROPOSER | {"kind": "builder"},
         "sha_before": "0" * 40, "claim": claim, "p": p, "resolves_by": resolves_by}
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
    # instruction #66: bound by branch, the pull request whose head ref it is, not the most recently opened one
    (_typed("pins, by branch", 0.8, "pins_green", {"branch": "b/pins"}), False),
    (_typed("review, by branch", 0.7, "review_accept", {"branch": "b/review"}), True),
    (_typed("still open, by branch", 0.9, "merged", {"branch": "b/open"}), None),
    (_typed("merged, by a reused branch", 0.9, "merged", {"branch": "b/reused"}), True),
    (_typed("no PR by resolves_by", 0.9, "merged", {"branch": "b/never"}, resolves_by=LATER_TS), False),
    (_typed("no PR yet", 0.9, "merged", {"branch": "b/never"}, resolves_by="2027-01-01T00:00:00Z"), None),
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
    ("pr", 13): {"state": "closed", "merged": False, "closed_at": BEFORE_TS},
    ("prs",): [{"number": 1, "head_ref": "b/pins", "created_at": AFTER_TS, "closed_at": None},
               {"number": 3, "head_ref": "b/review", "created_at": AFTER_TS, "closed_at": None},
               {"number": 5, "head_ref": "b/open", "created_at": AFTER_TS, "closed_at": None},
               {"number": 13, "head_ref": "b/reused", "created_at": BEFORE_TS, "closed_at": BEFORE_TS},
               {"number": 4, "head_ref": "b/reused", "created_at": AFTER_TS, "closed_at": AFTER_TS},
               {"number": 14, "head_ref": "b/other", "created_at": LATER_TS, "closed_at": None}],
    ("report",): "# REPORT\n- L1 — **SEALED; Crafter FIT**\n- L2 — **NetHack MARGINAL**\n- L2 — **NetHack UNFIT**\n",
    ("timeline", 6): [{"event": "reviewed", "user": {"login": "gfrmin"}, "state": "commented", "submitted_at": AFTER_TS},
                      {"event": "reviewed", "user": {"login": "gfrmin"}, "state": "approved", "submitted_at": LATER_TS}],
    ("timeline", 7): [{"event": "labeled", "actor": {"login": "gfrmin"}, "label": {"name": "instruction"},
                       "created_at": BEFORE_TS},
                      {"event": "closed", "actor": {"login": "assize-reviewer"}, "created_at": AFTER_TS}],
    ("issue", 7): {"number": 7, "title": "an instruction", "labels": ["instruction"]},  # not a draft (instruction #112)
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
# wishes (number, filed hour) and the instructions citing them (number, wish, hour filed, hour merged or None):
# wish 10 filed at 1h, drafted by 20 (filed at 4h, merged at 6h) and 21 (filed at 5h, merged at 9h): 6 - 1 = 5h, the
# earliest merge, not 6 - 4; wish 11 filed at 2h, instruction 22 merged at 12h, after the window's end: open; wish 12
# filed at 3h with no instruction: open; wish 13 filed before the window: not counted.
PRICE_WISHES = ((10, 1), (11, 2), (12, 3), (13, -2))
PRICE_INSTRUCTIONS = ((20, 10, 4, 6), (21, 10, 5, 9), (22, 11, 3, 12))
# by the definition, over [T0, T0 + 10h): items 1, 2, 3 (4 reached before the window; 3 once, at its first arrival);
# latencies 1 -> 3 is 2h, 2 unanswered is 10 - 2 = 8h (open, never dropped), 3 -> 5 is 2h; sessions: the build and
# the failed review (the skipped one never ran); runner-minutes 30 + 60 + 10, pins 10.
PRICE_WANT = {"items": (1, 2, 3), "latencies": (2.0, 8.0, 2.0), "open": (2,), "sessions": 2, "runner": 100.0,
              "pins": 10.0}
# Instruction #139: run 100 (the build) drew model x and its one session emits cumulative results of $1.00 then $1.50,
# the final one $1.50 (review b2e7f72 F1); run 101 (the review, 60 minutes) drew y for review then x for vizier, and its
# log ends after one result of $2.00, the vizier session never reaching its own. By the definition: x has two sessions
# over 30 + 30 minutes with one cost known ($1.50, one unknown); y has one session over 30 minutes at $2.00. The run
# before the window (104) is in neither.
PRICE_DRAWS = (("build", 100, "claude-x"), ("review", 101, "claude-y"), ("vizier", 101, "claude-x"))
PRICE_LOGS = {100: ((1.0, 1.5),), 101: ((2.0,),)}  # run -> per session, the cost of each of its result events in order
PRICE_MODELS_WANT = (("claude-x", 2, 60.0, 1.5, 1), ("claude-y", 1, 30.0, 2.0, 0))


def _session_log(*sessions_: tuple) -> list[dict]:
    """A stream-json log of sessions: each, under its own `session_id`, is an assistant message and a `result` event
    carrying its cumulative cost, if any, per wake-up."""
    events: list[dict] = []
    for s, costs in enumerate(sessions_):
        for cost in costs:
            events += [{"type": "assistant", "session_id": f"s{s}", "message": {"id": "m", "content": []}},
                       {"type": "result", "subtype": "success", "session_id": f"s{s}"}
                       | ({} if cost is None else {"total_cost_usd": cost})]
    return events


def p0t_price() -> bool:
    """`python -m harness.ledger price` counts every item that reached Guy by an `awaits-guy` label, an assignment or
    a NEEDS YOU line, once, with its latency to his first action after it, or to the window's end if none yet; and
    sessions and runner-minutes per workflow (rule 6 of the ground, instruction #54 item 6)."""
    from harness import ledger

    expect, ok = _expecter()
    reached = [{"item": n, "route": r, "at": _h(h)} for n, r, h in PRICE_REACHED]
    actions = {n: [_h(h) for h in hs] for n, hs in PRICE_ACTIONS.items()}
    runs = [{"id": 100 + i, "path": w, "conclusion": c, "created_at": _h(h), "run_started_at": _h(h),
             "updated_at": _h(h + m / 60)} for i, (w, c, h, m) in enumerate(PRICE_RUNS)]
    draws = [{"procedure": p, "run": r, "drawn": m} for p, r, m in PRICE_DRAWS]
    costs = {r: ledger.result_costs(_session_log(*cs)) for r, cs in PRICE_LOGS.items()}
    got = ledger.price(reached, actions, runs, T0, _h(PRICE_UNTIL), draws, costs)
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
    wishes = {n: _h(h) for n, h in PRICE_WISHES}
    cited = {i: w for i, w, _, _ in PRICE_INSTRUCTIONS}
    merged = {i: _h(m) for i, _, _, m in PRICE_INSTRUCTIONS}
    created = {i: _h(c) for i, _, c, _ in PRICE_INSTRUCTIONS}
    ws, wl, wo = ledger.wish_latency(wishes | created, [n for n, _ in PRICE_WISHES], cited, merged, T0, _h(PRICE_UNTIL))
    print(f"    wishes {ws}, latencies {wl}, open {wo}")
    expect(ws == (10, 11, 12) and wo == (11, 12) and len(wl) == 1 and math.isclose(wl[0], 5.0),
           f"wishes {ws}, latencies {wl}, open {wo}; want (10, 11, 12), (5.0,), (11, 12)")
    line = dataclasses.replace(got, wishes=ws, wish_latencies_h=wl, open_wishes=wo).status_line()
    expect(line == "price: guy-items 3; guy-latency median 2.0h max 8.0h; sessions 2; runner-min 100; "
                   "models claude-x s2/60m/$1.50+?, claude-y s1/30m/$2.00; "
                   "wish-latency median 5.0h max 5.0h open 2; sessions-over-bound 0/0; sessions-lost-to-limit 0",
           f"STATUS line {line!r}")
    # Instruction #139 item 4: each model reported separately, correct sums, a session without a result counted.
    have = tuple((m.model, m.sessions, m.minutes, m.cost_usd, m.cost_unknown) for m in got.models)
    expect(len(have) == len(PRICE_MODELS_WANT) and all(
        a[:2] == b[:2] and a[4] == b[4] and math.isclose(a[2], b[2]) and math.isclose(a[3], b[3])
        for a, b in zip(have, PRICE_MODELS_WANT)), f"per-model price {have}, want {PRICE_MODELS_WANT}")
    expect(sum(m.sessions for m in got.models) == len(PRICE_DRAWS) and got.sessions == 2,
           "every drawn session is under a model (three draws over two runs); the vizier session without a result is "
           "counted, not dropped")
    bare = ledger.model_price({7: 10.0}, [], {})
    expect(bare == (ledger.ModelPrice(ledger.UNKNOWN_MODEL, 1, 10.0, 0.0, 1),),
           f"a session run with no draw and no log is one unknown session with cost unknown: {bare}")
    expect(ledger.result_costs([{"type": "result"}, {"type": "result", "total_cost_usd": 0.25}, {"type": "assistant"}])
           == [None, 0.25], "a result event without a cost reads as unknown, not zero")
    return ok()


ELECTION_ENTRANTS = ("m-a", "m-b", "m-c")
ELECTION_BOUND = 2.0
ELECTION_TS = [f"2026-01-0{i}T00:00:00Z" for i in range(1, 9)]


def _scored(model: str, p: float, outcome: bool, ts: str, kind: str = "reviewer") -> list[dict]:
    f = _forecast(f"{kind} {model} {p} {outcome} {ts}", p, kind)
    f["proposer"] = f["proposer"] | {"model": model}
    f["ts"] = ts
    return [f, _resolved(f, outcome)]


def _drew(model: str, probabilities: dict, ts: str, procedure: str = "review") -> dict:
    return {"procedure": procedure, "ts": ts, "run": 1, "gamma": 0.5, "probabilities": probabilities, "drawn": model}


# The recorded draws and what followed them. Draw 3 re-draws m-a (so m-a's forecasts after it belong to it alone), draw 4
# is of m-c, which made no forecast (observed nothing), draw 5 names a model that is no entrant (unknown). The recorded
# probabilities are not what a replay would compute: the estimate must divide by these. One m-a round is clipped.
ELECTION_DRAWS = [_drew("m-a", {"m-a": .5, "m-b": .25, "m-c": .25}, ELECTION_TS[0]),
                  _drew("m-b", {"m-a": .25, "m-b": .5, "m-c": .25}, ELECTION_TS[2]),
                  _drew("m-a", {"m-a": .4, "m-b": .3, "m-c": .3}, ELECTION_TS[4]),
                  _drew("m-c", {"m-a": .3, "m-b": .3, "m-c": .4}, ELECTION_TS[5]),
                  _drew("m-x", {"m-x": .5, "m-a": .5}, ELECTION_TS[6]),
                  _drew("m-a", {"m-a": 1.0}, ELECTION_TS[0], "build")]
ELECTION_FIXTURE = (_scored("m-a", .9, True, ELECTION_TS[1]) + _scored("m-a", .2, True, ELECTION_TS[1])
                    + _scored("m-b", .5, False, ELECTION_TS[3]) + _scored("m-b", .1, True, ELECTION_TS[1])
                    + _scored("m-a", .01, True, ELECTION_TS[4]) + _scored("m-a", .01, False, ELECTION_TS[1], "builder")
                    + [_forecast("open", .5, "reviewer") | {"ts": ELECTION_TS[1]}
                       | {"proposer": LEDGER_PROPOSER | {"kind": "reviewer", "model": "m-a"}}])


def _exp3_by_definition(rows: list[dict], draws: list[dict], procedure: str, entrants: tuple, bound: float):
    """EXP3 on losses written out from the definition: each round of `procedure` that drew a known model adds, to that
    model alone, min(mean log-loss of its resolved forecasts from the draw to its next draw, B) over the probability
    recorded with the draw; gamma = min(1, sqrt(K ln K / ((e - 1) t))), t = rounds + 1; w proportional to
    exp(-gamma L^ / (K B)); p = (1 - gamma) w + gamma / K. Returns p, then (unknown, unobserved, clipped) round counts."""
    mine = [d for d in draws if d["procedure"] == procedure]
    resolved = {r["id"]: r["outcome"] for r in rows if "outcome" in r}
    loss = {m: 0.0 for m in entrants}
    unknown = unobserved = clipped = 0
    for i, d in enumerate(mine):
        if d["drawn"] not in entrants:
            unknown += 1
            continue
        nxt = min([e["ts"] for e in mine[i + 1:] if e["drawn"] == d["drawn"]], default="9")
        got = [-math.log(f["p"] if resolved[f["id"]] else 1 - f["p"]) for f in rows
               if "claim" in f and f["id"] in resolved and f["proposer"]["kind"] == "reviewer"
               and f["proposer"]["model"] == d["drawn"] and d["ts"] <= f["ts"] < nxt]
        if not got:
            unobserved += 1
            continue
        mean = sum(got) / len(got)
        clipped += mean > bound
        loss[d["drawn"]] += min(mean, bound) / d["probabilities"][d["drawn"]]
    k, t = len(entrants), len(mine) + 1
    g = min(1.0, math.sqrt(k * math.log(k) / ((math.e - 1) * t)))
    raw = {m: math.exp(-g * loss[m] / (k * bound)) for m in entrants}
    return {m: (1 - g) * raw[m] / sum(raw.values()) + g / k for m in entrants}, (unknown, unobserved, clipped)


def p0u_election() -> bool:
    """`python -m harness.ledger elect <procedure> --seed <run id>` draws an entrant by EXP3 over the entrants (bandit
    feedback: only the drawn model of a round is updated, by its clipped loss over the probability recorded with that
    draw, 0 for the rest), over a sweep of every seed residue the frequencies equal the probabilities, rounds that name
    no entrant, observed nothing or were clipped are counted, and the command records the draw it makes and reads
    `harness/entrants.toml` from the checkout (rule 7 of the ground, instruction #54 item 7; instruction #64)."""
    from harness import ledger

    expect, ok = _expecter()
    rows = list(ELECTION_FIXTURE) + ELECTION_DRAWS
    want, (unknown, unobserved, clipped) = _exp3_by_definition(rows, ELECTION_DRAWS, "review", ELECTION_ENTRANTS,
                                                              ELECTION_BOUND)
    counts = {m: 0 for m in ELECTION_ENTRANTS}
    for seed in range(ledger.DRAWS):
        m = ledger.elect(rows, "review", ELECTION_ENTRANTS, ELECTION_BOUND, seed + 123456789).model
        counts[m] = counts.get(m, 0) + 1
    print(f"    probabilities {want}; draws over {ledger.DRAWS} seeds {counts}")
    expect(all(abs(counts[m] - want[m] * ledger.DRAWS) <= 1 for m in ELECTION_ENTRANTS) and sum(counts.values())
           == ledger.DRAWS, f"every entrant drawn its probability's share of the sweep, to one draw ({counts})")
    got = ledger.elect(rows, "review", ELECTION_ENTRANTS, ELECTION_BOUND, 0)
    expect((got.rounds, got.unknown, got.unobserved, got.clipped) == (5, unknown, unobserved, clipped) == (5, 1, 1, 1),
           f"rounds counted, none dropped: {got.report()}")
    expect(all(math.isclose(got.probabilities[m], want[m]) for m in ELECTION_ENTRANTS),
           f"probabilities {dict(got.probabilities)}, by definition {want}")
    expect(ledger.elect(rows, "audit", ELECTION_ENTRANTS, ELECTION_BOUND, 0).model in ELECTION_ENTRANTS,
           "a procedure with no record draws among its entrants")
    # Instruction #139 item 5: with three entrants and no recorded draw, each starts at EXP3's uniform 1/3 and a sweep of
    # every seed draws each a third of the time, and nothing else.
    three = ("m-a", "m-b", "m-c")
    fresh = {m: 0 for m in three}
    for seed in range(ledger.DRAWS):
        fresh[ledger.elect([], "vizier", three, ELECTION_BOUND, seed).model] += 1
    start = ledger.elect([], "vizier", three, ELECTION_BOUND, 0)
    expect(set(start.probabilities) == set(three) and all(math.isclose(p, 1 / 3) for p in start.probabilities.values())
           and all(abs(n - ledger.DRAWS / 3) <= 1 for n in fresh.values()),
           f"three new entrants start uniform: {dict(start.probabilities)}, sweep {fresh}")
    work = Path(tempfile.mkdtemp(prefix="assize-p0u-", dir=context.scratch))
    repo = work / "repo"
    git = _git_fixture(repo)
    repo.mkdir(parents=True)
    git("init", "-q", "-b", "master")
    _append(repo, "reports/L2/forecasts.jsonl", "".join(json.dumps(r) + "\n" for r in ELECTION_FIXTURE))
    _append(repo, ledger.DRAW_LEDGER, "".join(json.dumps(r) + "\n" for r in ELECTION_DRAWS))
    _append(repo, ledger.ENTRANTS, f"review = {json.dumps(list(ELECTION_ENTRANTS))}\n[bound]\nloss = {ELECTION_BOUND}\n")
    git("add", "-A")
    git("commit", "-q", "-m", "ledger")

    def run(seed: int):
        return subprocess.run([sys.executable, "-B", "-m", "harness.ledger", "elect", "review", "--seed", str(seed),
                               "--repo", str(repo)], cwd=ROOT, capture_output=True, text=True)

    seeds = (7, 40000, 65535)
    out = [run(s) for s in seeds]
    printed = [o.stdout.strip() for o in out]
    expect(all(o.returncode == 0 for o in out) and printed == [ledger.elect(rows, "review", ELECTION_ENTRANTS,
                                                                            ELECTION_BOUND, s).model for s in seeds],
           f"the command prints the draw for its seed: {printed} ({[o.stderr.strip()[-200:] for o in out]})")
    recorded = [json.loads(x) for x in (repo / ledger.DRAW_LEDGER).read_text().splitlines()[len(ELECTION_DRAWS):]]
    expect([r["drawn"] for r in recorded] == printed and [r["run"] for r in recorded] == list(seeds)
           and all(r["procedure"] == "review" and math.isclose(r["gamma"], got.gamma)
                   and all(math.isclose(r["probabilities"][m], want[m]) for m in ELECTION_ENTRANTS)
                   for r in recorded), f"each draw is recorded with the distribution it was drawn from: {recorded}")
    (repo / ledger.ENTRANTS).write_text('review = ["m-a", "m-b"]\n[bound]\nloss = 3.0\n')  # the checkout, not head
    out = [run(s) for s in seeds]
    rows2 = [json.loads(x) for x in (repo / ledger.DRAW_LEDGER).read_text().splitlines()[len(ELECTION_DRAWS) + 3:]]
    expect(all(o.returncode == 0 for o in out) and all(set(r["probabilities"]) == {"m-a", "m-b"} for r in rows2)
           and len(rows2) == 3, f"entrants are read from the checkout, not from head: {rows2}")
    # Review of 22d0279 F1: a published draw reaches the next election, run from another checkout of the same remote
    # (a fresh runner workspace), and a push from a stale tip appends to the new one instead of replacing it.
    git("init", "-q", "--bare", str(work / "remote.git"))
    git("remote", "add", "origin", str(work / "remote.git"))
    git("push", "-q", "origin", "master")
    git("clone", "-q", str(work / "remote.git"), str(work / "other"))

    def publish(where: Path, seed: int):
        return subprocess.run([sys.executable, "-B", "-m", "harness.ledger", "elect", "review", "--seed", str(seed),
                               "--repo", str(where), "--publish", "origin"], cwd=ROOT, capture_output=True, text=True)

    def published() -> list[dict]:
        tip = ledger.draw_tip(repo, "origin")
        return ledger.draw_rows(repo, tip) if tip else []

    local = (repo / ledger.DRAW_LEDGER).read_text()
    first, second = publish(repo, 11), publish(work / "other", 12)
    rounds = [re.search(r"^rounds (\d+)", o.stderr, re.M) for o in (first, second)]
    print(f"    published elections: {[o.stderr.strip().splitlines()[-1:] for o in (first, second)]}")
    expect(first.returncode == second.returncode == 0 and [int(r.group(1)) if r else None for r in rounds] == [0, 1]
           and [r["run"] for r in published()] == [11, 12] and (repo / ledger.DRAW_LEDGER).read_text() == local,
           f"a published draw is read by the next election from another checkout: rounds "
           f"{[r and r.group(1) for r in rounds]}, branch {published()}")
    stale = ledger.draw_tip(work / "other", "origin")
    publish(repo, 13)
    ledger.publish_draw(work / "other", "origin", ledger.draw_row(got, "review", 14, "2026-01-01T00:00:00Z"), stale)
    expect([r["run"] for r in published()] == [11, 12, 13, 14],
           f"a draw pushed from a stale tip is appended, none lost: {[r['run'] for r in published()]}")
    shutil.rmtree(work, ignore_errors=True)
    return ok()


REVIEW_EVENTS = (  # (what, sender, event, action, label, must start a review) -- instruction #65
    ("a needs-review label applied by the reviewer account (an audit PR, the Vizier sending a changed head back)",
     "assize-reviewer", "pull_request", "labeled", "needs-review", True),
    ("an awaits-guy label applied by a review session", "assize-reviewer", "pull_request", "labeled", "awaits-guy",
     False),
    ("a needs-review label applied by the builder", "assize-builder", "pull_request", "labeled", "needs-review", True),
)


def _review_condition(text: str) -> str | None:
    """The `if:` of the review job in `.github/workflows/review.yml`, its folded lines joined."""
    m = re.search(r"^  review:\n    if: >-\n((?:      .*\n)+)", text, re.M)
    return " ".join(x.strip() for x in m.group(1).splitlines()) if m else None


def _github_value(expression: str, context_: dict[str, object]) -> object:
    """Evaluates the subset of the Actions expression language the workflow conditions use (`==`, `!=`, `&&`, `||`,
    which yield an operand as Actions' do, `contains(fromJSON('[..]'), x)`, and `github.*` and `inputs.*` names, null
    when the event does not carry one)."""
    py = re.sub(r"contains\(fromJSON\('(\[[^']*\])'\),\s*([^()]*?)\)", r"(\2 in \1)", expression)
    py = re.sub(r"(?:github|inputs)(?:\.\w+)+", lambda m: f"ctx.get({m.group(0)!r})", py)
    return eval(py.replace("&&", " and ").replace("||", " or "), {"__builtins__": {}}, {"ctx": context_})


def _github_condition(condition: str, context_: dict[str, object]) -> bool:
    return bool(_github_value(condition, context_))


BUILD_EVENTS = (  # (what, label, must start, on the PR branch) -- instruction #102
    ("an awaits-guy label on a pull request", "awaits-guy", True, False),
    ("a blocked label on a pull request", "blocked", True, True),
    ("a needs-review label on a pull request", "needs-review", False, None),
)
BUILD_EVENT_PR = 7


def _build_expressions(text: str) -> tuple[str | None, str | None, str | None]:
    """The build job's `if:`, its concurrency group's expression, and the `if:` of the step that checks out a pull
    request, from `.github/workflows/build.yml`."""
    job = re.search(r"^  build:\n    if: (.*)$", text, re.M)
    group = re.search(r"^      group: build-\$\{\{ (.*) \}\}$", text, re.M)
    checkout = re.search(r"^      - if: (.*)\n        run: gh pr checkout ", text, re.M)
    return tuple(m.group(1) if m else None for m in (job, group, checkout))


def p0aj_awaits_guy_builds_master() -> bool:
    """An `awaits-guy` label on a pull request starts a Builder on master, in master's queue, checking out no pull
    request; a `blocked` label builds on the pull request, in its queue, as before; a `needs-review` label starts no
    Builder (instruction #102). The workflow states this, and that the `blocked` path is unchanged."""
    expect, ok = _expecter()
    text = (ROOT / ".github" / "workflows" / "build.yml").read_text()
    job, group, checkout = _build_expressions(text)
    expect(None not in (job, group, checkout), "the build job's `if:`, its concurrency group and the PR checkout step's "
                                              f"`if:` are found ({job is not None}, {group is not None}, "
                                              f"{checkout is not None})")
    if None in (job, group, checkout):
        return ok()
    for what, label, start, on_pr in BUILD_EVENTS:
        # `inputs.pr` is '' outside a dispatch: Actions compares a missing input equal to ''.
        ctx = {"github.event_name": "pull_request", "github.event.action": "labeled", "github.event.label.name": label,
               "github.event.pull_request.number": BUILD_EVENT_PR, "inputs.pr": ""}
        started = _github_condition(job, ctx)
        expect(started is start, f"{what}: {'starts' if started else 'does not start'} a Builder (must "
                                 f"{'start' if start else 'not start'})")
        if not start:
            continue
        pr_branch, queue = _github_condition(checkout, ctx), _github_value(group, ctx)
        want_queue = BUILD_EVENT_PR if on_pr else "master"
        expect(pr_branch is on_pr and queue == want_queue,
               f"{what}: builds on {'the PR branch' if pr_branch else 'master'} in queue build-{queue} (must build on "
               f"{'the PR branch' if on_pr else 'master'} in queue build-{want_queue})")
    head = text.split("concurrency:")[0]
    expect("awaits-guy" in head and "master" in head and "`blocked` path is unchanged" in head,
           "the workflow states that awaits-guy starts a master Builder and that the `blocked` path is unchanged")
    return ok()


PRICE_BEFORE, PRICE_MERGED, PRICE_AFTER = "2000-01-01T00:00:00Z", "2026-10-11T00:00:00Z", "2999-01-01T00:00:00Z"
PRICE_N = 200
PRICE_MERGE_DATE = "2030-01-01T00:00:00+00:00"  # the fixture merge's committer time, later than its branch commit's
PRICE_WORKFLOW_COMMIT = claims.Commit("a" * 40, ("guy",), (".github/workflows/build.yml",),
                                      instructions=(PRICE_N + 5, PRICE_N + 16))
PRICE_DOC_COMMIT = claims.Commit("b" * 40, ("guy",), ("harness/ledger.py",), instructions=(PRICE_N + 6,))
PRICE_ISSUES = (  # (issue, body, signed at, rule merged at, commits, finding codes wanted)
    (PRICE_N + 1, "Do it.\nPrice: guy-latency; down; 2.5\nNothing else.", PRICE_AFTER, PRICE_MERGED, (), set()),
    (PRICE_N + 2, "Do it.\nPrice: none (recording-only)", PRICE_AFTER, PRICE_MERGED, (), set()),
    (PRICE_N + 3, "Do it, no price.", PRICE_AFTER, PRICE_MERGED, (), {"price_line"}),
    (PRICE_N + 4, "Price: sessions; down; 1\nPrice: none (recording-only)", PRICE_AFTER, PRICE_MERGED, (),
     {"price_line"}),
    (PRICE_N + 5, "Price: none (recording-only)", PRICE_AFTER, PRICE_MERGED, (PRICE_WORKFLOW_COMMIT,),
     {"price_none_on_workflow"}),
    (PRICE_N + 6, "Price: none (recording-only)", PRICE_AFTER, PRICE_MERGED, (PRICE_DOC_COMMIT, PRICE_WORKFLOW_COMMIT),
     set()),
    (PRICE_N + 7, "Price: sessions; down; 1", PRICE_AFTER, PRICE_MERGED, (PRICE_WORKFLOW_COMMIT,), set()),
    (PRICE_N + 8, "Price: happiness; up; 3", PRICE_AFTER, PRICE_MERGED, (), {"price_form"}),
    (PRICE_N + 9, "Price: sessions; sideways; 3", PRICE_AFTER, PRICE_MERGED, (), {"price_form"}),
    (PRICE_N + 10, "Price: sessions; down", PRICE_AFTER, PRICE_MERGED, (), {"price_form"}),
    (PRICE_N + 11, "Signed before the rule merged, no price.", PRICE_BEFORE, PRICE_MERGED, (), set()),
    (PRICE_N + 12, "Never signed, no price.", None, PRICE_MERGED, (), set()),
    (PRICE_N + 13, "Signed, but the rule has not merged, no price.", PRICE_AFTER, None, (), set()),
    (67, "An old draft by number, signed after the rule merged, no price.", PRICE_AFTER, PRICE_MERGED, (),
     {"price_line"}),
    (900, "A new draft by number, signed before the rule merged, no price.", PRICE_BEFORE, PRICE_MERGED, (), set()),
    (PRICE_N + 14, "Batch.\n## Part A\nDo a.\nPrice: sessions; down; 1\n## Part B\nDo b.\nPrice: none (recording-only)\n",
     PRICE_AFTER, PRICE_MERGED, (), set()),
    (PRICE_N + 15, "Batch.\n## Part A\nDo a.\n## Part B\nDo b.\nPrice: sessions; down; 1\n", PRICE_AFTER, PRICE_MERGED, (),
     {"price_line"}),
    (PRICE_N + 16, "Batch.\n## Part A\nPrice: none (recording-only)\n## Part B\nPrice: none (recording-only)\n",
     PRICE_AFTER, PRICE_MERGED, (PRICE_WORKFLOW_COMMIT,), {"price_none_on_workflow"}),
    (PRICE_N + 17, "Batch.\nPrice: sessions; down; 1\n## Part A\nPrice: sessions; down; 1\n", PRICE_AFTER, PRICE_MERGED,
     (), {"price_line"}),
)


def _price_repo(repo: Path) -> tuple[str, str, str]:
    """A fixture repository: master without the rule, a branch adding it, and master's merge of that branch.
    Returns master before the merge, the branch head, and the merge."""
    git = _git_fixture(repo)
    repo.mkdir(parents=True)
    git("init", "-q", "-b", "master")
    _append(repo, claims.PRICE_PATH, "# no rule yet\n")
    git("add", "-A")
    git("commit", "-q", "-m", "base")
    before = git("rev-parse", "HEAD")
    git("checkout", "-q", "-b", "rule")
    _append(repo, claims.PRICE_PATH, f"{claims.PRICE_MARK}n, body): ...\n")
    git("commit", "-q", "-am", "rule")
    branch = git("rev-parse", "HEAD")
    git("checkout", "-q", "master")
    _append(repo, "other", "x\n")
    git("add", "-A")
    git("commit", "-q", "-m", "other")
    subprocess.run(["git", "-C", str(repo), "merge", "-q", "--no-ff", "-m", "Merge pull request #1", "rule"], check=True,
                   capture_output=True, env=os.environ | claims.GIT_ENV | FIXTURE_GIT | {"GIT_COMMITTER_DATE": PRICE_MERGE_DATE})
    return before, branch, git("rev-parse", "HEAD")


def p0x_price_declared() -> bool:
    """Every `instruction` issue signed after the rule merged (claims.price_from: the committer time of the merge
    that brought claims.PRICE_MARK onto master's first-parent line, read from git; before it exists, no issue) carries
    exactly one `Price:` line, or one per `## Part` of a batch, `<quantity>; down|up; <bound>` with a quantity of
    `python -m harness.ledger price`, or `none (recording-only)`; and a commit citing an issue whose every line is of
    the second kind touches no workflow (instruction #70). The real issues are read in CI once the rule has merged."""
    expect, ok = _expecter()
    for n, body, at, since, commits, want in PRICE_ISSUES:
        got = {f.code for f in claims.price_findings(n, body, at, since, commits)}
        expect(got == want, f"issue #{n} (signed {at}, rule merged {since}): findings {sorted(got)}, want {sorted(want)}")
    repo = Path(tempfile.mkdtemp(prefix="assize-p0x-", dir=context.scratch)) / "repo"
    before, branch, merge = _price_repo(repo)
    merged_at = _git_fixture(repo)("log", "-1", "--format=%cI", merge)
    branched_at = _git_fixture(repo)("log", "-1", "--format=%cI", branch)
    got = {k: claims.price_from(repo, sha) for k, sha in (("before", before), ("merge", merge))}
    expect(got == {"before": None, "merge": merged_at} and claims._after(merged_at, branched_at),
           f"rule merged at {got}: none before the merge; after it the merge's committer time {merged_at}, not the "
           f"branch commit's {branched_at}")
    root = _real_root()
    base = _branch_base(root)
    since = claims.price_from(root, base) if base else None
    expect(base is not None, f"master's merge base with HEAD read ({base})")
    if since is None:
        print("    real: the rule has not merged on master's first-parent line; the real-tree check covers no issue")
        return ok()
    try:
        real = claims.load_priced(root, since)
    except (OSError, subprocess.SubprocessError) as e:
        real, _ = {}, expect(False, f"real issues not read ({e})")
    commits = claims.branch_commits(root, base)
    found = [f for n, (body, at) in sorted(real.items()) for f in claims.price_findings(n, body, at, since, commits)]
    print(f"    real: rule merged {since}; {len(real)} instruction issues updated since: {sorted(real)}")
    expect(not found, f"real instruction issues: findings {[str(f) for f in found]}")
    return ok()


def p0v_review_trigger() -> bool:
    """The review job starts on a `needs-review` label applied by the reviewer account (an audit-findings pull request,
    the Vizier sending a changed head back), on one applied by the builder, and not on an `awaits-guy` label a review
    session applied (instruction #65)."""
    expect, ok = _expecter()
    text = (ROOT / ".github" / "workflows" / "review.yml").read_text()
    condition = _review_condition(text)
    expect(condition is not None, "the review job's `if:` is found")
    for what, sender, event, action, label, want in REVIEW_EVENTS:
        got = condition is not None and _github_condition(condition, {
            "github.event.sender.login": sender, "github.event_name": event, "github.event.action": action,
            "github.event.label.name": label})
        expect(got is want, f"{what}: {'starts' if got else 'does not start'} a review (must "
                            f"{'start' if want else 'not start'})")
    expect("awaits-guy" in text.split("jobs:")[0] and "recognised" in text.split("jobs:")[0],
           "the workflow states how a review session's own label changes are recognised")
    return ok()


PARSED, SPLIT = "Proposer: guy\nCo-Authored-By: f <f@f>\n", "Proposer: guy\n\nCo-Authored-By: f <f@f>\n"
TRAILERS_FIXTURE = (  # (what, message after the body, findings wanted) -- instruction #110 Part C
    ("Proposer and Co-Authored-By in one trailer block", PARSED, set()),
    ("Instruction and both Proposer lines in one block", "Instruction: #1\nProposer: guy\nProposer: builder m s\n",
     set()),
    ("a blank line between Proposer and Co-Authored-By (the #48/#106 class)", SPLIT,
     {"no_proposer", "outside_trailer_block"}),
    ("an Instruction line in the body, the Proposer trailer parsed", "Instruction: #1\n\nProposer: guy\n",
     {"outside_trailer_block"}),
    ("no Proposer line at all", "Co-Authored-By: f <f@f>\n", {"no_proposer"}),
)


def _commit_as(git, repo: Path, n: int, message: str, amend: bool = False, path: str = "f") -> str:
    (repo / path).write_text(f"{n}\n")
    git("add", "-A")
    git("commit", "-q", *(["--amend"] if amend else []), "-m", f"case {n}\n\nbody\n\n{message}")
    return git("rev-parse", "HEAD")


def p0y_trailers_parse() -> bool:
    """`python -m harness.claims trailers <base>..HEAD` refuses a non-merge commit with no `Proposer:` trailer as git
    parses it, or with a `Proposer:` or `Instruction:` line outside its trailer block; `harness/hooks/pre-push`,
    installed by `core.hooksPath`, refuses the push of such a commit and accepts a parseable one; the real branch's
    commits parse (instruction #110 Part C)."""
    expect, ok = _expecter()
    work = Path(tempfile.mkdtemp(prefix="assize-p0y-", dir=context.scratch))
    repo = work / "repo"
    git = _git_fixture(repo)
    repo.mkdir(parents=True)
    git("init", "-q", "-b", "master")
    base = _commit_as(git, repo, 0, PARSED)
    for n, (what, message, want) in enumerate(TRAILERS_FIXTURE, 1):
        sha = _commit_as(git, repo, n, message)
        got = {f.code for f in claims.trailer_findings(repo, f"{sha}~1..{sha}")}
        expect(got == want, f"{what}: findings {sorted(got)}, want {sorted(want)}")
    git("checkout", "-q", "-b", "side", base)
    _commit_as(git, repo, 90, PARSED, path="g")
    git("checkout", "-q", "master")
    git("merge", "-q", "--no-ff", "-m", "Merge side", "side")
    expect(not claims.trailer_findings(repo, "HEAD~1..HEAD") and claims.trailer_findings(repo, f"{base}..HEAD"),
           "a merge needs no trailer; the range's own commits are still read")
    out = subprocess.run([sys.executable, "-B", "-m", "harness.claims", "trailers", f"{base}..HEAD", "--repo",
                          str(repo)], cwd=ROOT, capture_output=True, text=True)
    expect(out.returncode == 1, f"the command exits non-zero on findings ({out.returncode}: {out.stderr.strip()[-200:]})")

    # The hook, from this tree, refuses a push of an unparseable commit, on a new branch and on one with an upstream.
    git("init", "-q", "--bare", str(work / "remote.git"))
    git("remote", "add", "origin", str(work / "remote.git"))
    git("push", "-q", "origin", "master")
    git("config", "core.hooksPath", str(ROOT / "harness" / "hooks"))

    def push(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(repo), "push", "-q", *args], capture_output=True, text=True,
                              env=os.environ | claims.GIT_ENV | FIXTURE_GIT)

    git("checkout", "-q", "-b", "work")
    _commit_as(git, repo, 100, SPLIT)
    refused_new = push("-u", "origin", "work")
    _commit_as(git, repo, 100, PARSED, amend=True)
    accepted_new = push("-u", "origin", "work")
    _commit_as(git, repo, 101, SPLIT)
    refused_up = push()
    _commit_as(git, repo, 101, PARSED, amend=True)
    accepted_up = push()
    said = [(p.returncode, p.stderr.strip()[-160:]) for p in (refused_new, accepted_new, refused_up, accepted_up)]
    print(f"    pushes: {said}")
    expect(refused_new.returncode != 0 and refused_up.returncode != 0,
           "the hook refuses a push of a commit whose Proposer line a blank line splits from the trailer block")
    expect(accepted_new.returncode == 0 and accepted_up.returncode == 0
           and git("rev-parse", "origin/work") == git("rev-parse", "HEAD"),
           "the hook accepts the push once the session's own commit is amended to parse")
    shutil.rmtree(work, ignore_errors=True)

    root = _real_root()
    base_real = _branch_base(root)
    found = claims.trailer_findings(root, f"{base_real}..HEAD") if base_real else []
    expect(base_real is not None and not found,
           f"real branch {base_real and base_real[:12]}..HEAD: every commit parses ({[str(f) for f in found]})")
    return ok()


FAILED_EVENTS = (  # (what, workflow, conclusion, selects the report job) -- instruction #110 Part C
    ("a pins run concluded failure", "pins", "failure", True),
    ("a build run concluded failure", "build", "failure", True),
    ("a review run timed out", "review", "timed_out", True),
    ("a pins run concluded success", "pins", "success", False),
    ("a measure run concluded failure", "measure", "failure", False),
)


def p0z_red_pins_routes() -> bool:
    """`failed.yml`'s trigger, evaluated on a synthetic `workflow_run` completed event, selects its report job for a
    failed `pins` run as for a failed build or review, and not for a success or an unwatched workflow; the issue for a
    pins run names its pull request and quotes the `CLEAN FAILED:` line (instruction #110 Part C)."""
    expect, ok = _expecter()
    text = (ROOT / ".github" / "workflows" / "failed.yml").read_text()
    watched = re.search(r"^  workflow_run:\n    workflows: \[([^\]]*)\]\n    types: \[([^\]]*)\]", text, re.M)
    condition = re.search(r"^  report:\n    if: (.*)$", text, re.M)
    expect(watched is not None and condition is not None, "the workflow_run trigger and the report job's `if:` are found")
    workflows = [w.strip() for w in watched.group(1).split(",")] if watched else []
    types = [t.strip() for t in watched.group(2).split(",")] if watched else []
    for what, wf, conclusion, want in FAILED_EVENTS:
        got = (wf in workflows and "completed" in types and condition is not None
               and _github_condition(condition.group(1), {"github.event.workflow_run.conclusion": conclusion}))
        expect(got is want, f"{what}: {'selects' if got else 'does not select'} the report job (must "
                            f"{'select' if want else 'not select'})")
    expect('title="pins run $RUN_ID $CONCLUSION on PR #' in text and "CLEAN FAILED: " in text,
           "a pins issue's title names the pull request and its body quotes the CLEAN FAILED: line")
    return ok()


HELD_PRS = (claims.OpenPR(201, (110,), ()),
            claims.OpenPR(202, (), ("# STATUS — L2 — 2026-10-12 — abc1234 — PR #202 — brief-2 A7 item 3",)))
HELD_FIXTURE = (  # (what, candidates in order, chosen, skipped) -- instruction #110 Part A item 2
    ("an instruction an open PR cites is skipped for the next", ("#110", "#111"), "#111", (("#110", 201),)),
    ("a brief item an open PR's STATUS header names is skipped", ("brief-2 A7 item 3", "#112"), "#112",
     (("brief-2 A7 item 3", 202),)),
    ("an item no PR holds is taken", ("#113", "#110"), "#113", ()),
    ("every candidate held: none", ("#110",), None, (("#110", 201),)),
)


def p0aa_held_item_skipped() -> bool:
    """On master, an item an open pull request holds (an instruction its commits cite by `Instruction:`, a brief item
    its own STATUS header names) is not a candidate: the selector takes the next and names the skipped item and its
    pull request; a pull request is read from its branch against master (instruction #110 Part A item 2)."""
    expect, ok = _expecter()
    for what, candidates, want, skipped in HELD_FIXTURE:
        got = claims.next_item(candidates, HELD_PRS)
        expect(got == (want, skipped), f"{what}: took {got[0]!r}, skipped {got[1]}; want {want!r}, {skipped}")
    work = Path(tempfile.mkdtemp(prefix="assize-p0aa-", dir=context.scratch))
    repo = work / "repo"
    git = _git_fixture(repo)
    repo.mkdir(parents=True)
    git("init", "-q", "-b", "master")
    _append(repo, "reports/L2/STATUS.md", "# STATUS — L2 — 2026-10-01 — 1111111 — PR #1\n")
    _commit_as(git, repo, 0, "Instruction: #7\nProposer: guy\n")
    git("checkout", "-q", "-b", "held")
    _commit_as(git, repo, 1, "Instruction: #110\nProposer: guy\n")
    (repo / "reports/L2/STATUS.md").write_text(HELD_PRS[1].headers[0] + "\n")
    _commit_as(git, repo, 2, "Instruction: #110\nProposer: guy\n")
    git("checkout", "-q", "-b", "untouched", "master")
    _commit_as(git, repo, 3, "Proposer: guy\n")
    git("init", "-q", "--bare", str(work / "remote.git"))
    git("remote", "add", "origin", str(work / "remote.git"))
    git("push", "-q", "origin", "master", "held", "untouched")
    git("fetch", "-q", "origin")
    prs = [claims.open_pr(repo, 201, "held"), claims.open_pr(repo, 203, "untouched")]
    expect(prs == [claims.OpenPR(201, (110, 110), HELD_PRS[1].headers), claims.OpenPR(203, (), ())],
           f"a pull request is read from its own commits and its own STATUS, not master's: {prs}")
    shutil.rmtree(work, ignore_errors=True)
    return ok()


def _call(n: int, tool: str, error: bool = False, **input_: str) -> list[dict]:
    """A tool call and its result, as `claude --output-format stream-json` logs them."""
    return [{"type": "assistant", "message": {"content": [{"type": "tool_use", "id": f"t{n}", "name": tool,
                                                           "input": input_}]}},
            {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": f"t{n}",
                                                      "is_error": error, "content": "ok"}]}}]


def _log(*calls_: tuple) -> list[dict]:
    return [{"type": "system", "subtype": "init"}] + [e for n, (tool, error, input_) in enumerate(calls_)
                                                      for e in _call(n, tool, error, **input_)]


BRANCHED = ("Bash", False, {"command": "git checkout -b instr-1-x"})
OPENED_PR = ("Bash", False, {"command": "gh pr create --title t --body b"})
SESSION_FIXTURE = (  # (what, calls, findings wanted) -- instruction #110 Part D
    ("Edit on .github/, then a pull request", (BRANCHED, ("Edit", False, {"file_path": ".github/workflows/build.yml"}),
                                               OPENED_PR), set()),
    ("an inline python heredoc rewriting build.yml (build run 38152587119)",
     (BRANCHED, ("Bash", False, {"command": "python3 - <<'EOF'\nimport pathlib\np = pathlib.Path("
                                            "'.github/workflows/build.yml')\np.write_text('x')\nEOF"}), OPENED_PR),
     {"shell_edit"}),
    ("sed -i on harness/claims.py", (BRANCHED, ("Bash", False, {"command": "sed -i 's/a/b/' harness/claims.py"}),
                                     OPENED_PR), {"shell_edit"}),
    ("a redirection into harness/proposer.toml",
     (BRANCHED, ("Bash", False, {"command": "printf 'kind = 1' > harness/proposer.toml"}), OPENED_PR), {"shell_edit"}),
    ("reading harness/ and writing elsewhere is not an edit",
     (BRANCHED, ("Bash", False, {"command": "grep -n x harness/pins.py > /tmp/out; cat .github/workflows/build.yml"}),
      OPENED_PR), set()),
    ("ends on master with no pull request and no issue", (("Bash", False, {"command": "git status"}),),
     {"silent_master_stop"}),
    ("ends on master after filing an issue", (("Bash", False, {"command": "gh issue create --title t --assignee g"}),),
     set()),
    ("ends on master; the issue was denied", (("Bash", True, {"command": "gh issue create --title t"}),),
     {"silent_master_stop"}),
    ("returns to master after opening a pull request", (BRANCHED, OPENED_PR, ("Bash", False,
                                                                             {"command": "git checkout -q master"})),
     set()),
    ("branches, then returns to master, and opens nothing", (BRANCHED, ("Bash", False, {
        "command": "git checkout master && git branch -D instr-1-x"})), {"silent_master_stop"}),
    ("a pull-request session that opens nothing", (("Bash", False, {"command": "gh pr checkout 63"}),), set()),
)


def p0ab_session_logs() -> bool:
    """A session log in which a file under `.github/` or `harness/` changes through a Bash call fails, as does one
    ending on master with no pull request and no issue; one that uses Edit and Write, or opens either, passes
    (instruction #110 Part D)."""
    from harness import sessions

    expect, ok = _expecter()
    for what, calls_, want in SESSION_FIXTURE:
        got = {f.code for f in sessions.session_findings(_log(*calls_))}
        expect(got == want, f"{what}: findings {sorted(got)}, want {sorted(want)}")
    text = "\n".join(json.dumps(e) for e in _log(*SESSION_FIXTURE[1][1])) + "\nstderr noise\n"
    expect({f.code for f in sessions.session_findings(sessions.parse(text))} == {"shell_edit"},
           "the log is read from stream-json text, other lines skipped")
    return ok()


DECLARE_TEXT = "build run 9 started 2026-10-12T09:00:00Z on #112: expected 60 minutes"
DECLARE = ("Bash", False, {"command": f"gh issue comment 112 --body '{DECLARE_TEXT}; model m'"})
STATUS_WRITTEN = ("Write", False, {"file_path": "reports/L2/STATUS.md", "content": "# STATUS\n"})
STOP_COMMENT = ("Bash", False, {"command": "gh pr comment 63 --body 'build run 9 stopped 2026-10-12T10:00:00Z: no item'"})
FORECAST_ROW = '{"id": "f1", "claim": "pins green", "p": 0.6}'
RESOLUTION_ROW = '{"id": "f0", "outcome": true}'


def _ledger_edit(row: str) -> tuple:
    return ("Edit", False, {"file_path": "reports/L2/forecasts.jsonl", "old_string": "{}\n", "new_string": f"{{}}\n{row}\n"})


DECLARED_FIXTURE = (  # (what, branch the workflow checked out, calls, findings wanted) -- instruction #112 Parts A, D
    ("declares, branches, writes STATUS", "master", (DECLARE, BRANCHED, STATUS_WRITTEN), set()),
    ("reads to name its item, then declares", "master",
     (("Bash", False, {"command": "uv run --frozen python -m harness.claims next '#112'"}), DECLARE, BRANCHED,
      STATUS_WRITTEN), set()),
    ("no declaration", "master", (BRANCHED, STATUS_WRITTEN), {"undeclared_session"}),
    ("commits before declaring", "master", (BRANCHED, ("Bash", False, {"command": "git commit -m x"}), DECLARE,
                                            STATUS_WRITTEN), {"undeclared_session"}),
    ("edits a file before declaring", "master", (("Edit", False, {"file_path": "harness/x.py"}), DECLARE,
                                                 STATUS_WRITTEN), {"undeclared_session"}),
    ("a declaration naming no model", "master",
     (("Bash", False, {"command": f"gh issue comment 112 --body '{DECLARE_TEXT}'"}), STATUS_WRITTEN),
     {"undeclared_session"}),
    ("a denied declaration, then a commit", "master", (("Bash", True, DECLARE[2]), BRANCHED,
                                                       ("Bash", False, {"command": "git commit -m x"}), STATUS_WRITTEN),
     {"undeclared_session"}),
    ("takes no item: the stop issue carries the declaration and the stop", "master",
     (("Bash", False, {"command": f"gh issue create --assignee gfrmin --title t --body '{DECLARE_TEXT}; model m\n"
                                  "build run 9 stopped 2026-10-12T09:01:00Z: nothing to do'"}),), set()),
    ("a new branch adds forecast rows", "master", (DECLARE, BRANCHED, _ledger_edit(FORECAST_ROW), STATUS_WRITTEN),
     set()),
    ("a PR-branch session adds a forecast row (run 38133974898)", "instr-109-x",
     (DECLARE, _ledger_edit(FORECAST_ROW), STATUS_WRITTEN), {"pr_branch_forecast"}),
    ("checks out a PR, then adds a forecast row", "master",
     (DECLARE, ("Bash", False, {"command": "gh pr checkout 63"}), _ledger_edit(FORECAST_ROW), STATUS_WRITTEN),
     {"pr_branch_forecast"}),
    ("a PR-branch session appends a forecast row by shell", "instr-109-x",
     (DECLARE, ("Bash", False, {"command": f"echo '{FORECAST_ROW}' >> reports/L2/forecasts.jsonl"}), STATUS_WRITTEN),
     {"pr_branch_forecast"}),
    ("a PR-branch session appends a resolution", "instr-109-x", (DECLARE, _ledger_edit(RESOLUTION_ROW),
                                                                 STATUS_WRITTEN), set()),
    ("stops on a PR branch with a stop comment", "instr-109-x", (DECLARE, STOP_COMMENT), set()),
    ("writes a review file", "master", (DECLARE, ("Write", False, {"file_path": "reports/L2/review-abc.md"})), set()),
    ("stops silently (PR #109's fix session)", "instr-109-x",
     (DECLARE, ("Bash", False, {"command": "make pins"})), {"silent_stop"}),
    ("its stop comment was denied", "instr-109-x", (DECLARE, ("Bash", True, STOP_COMMENT[2])), {"silent_stop"}),
)


RUN_ANSWERS = {  # (run id) -> the Actions API run, in the shape the observer returns
    1: {"status": "completed", "conclusion": "success", "run_started_at": AFTER_TS, "updated_at": "2026-01-11T00:30:00Z"},
    2: {"status": "completed", "conclusion": "failure", "run_started_at": AFTER_TS, "updated_at": "2026-01-11T01:30:00Z"},
    3: {"status": "in_progress", "conclusion": None, "run_started_at": AFTER_TS, "updated_at": AFTER_TS},
    4: {"status": "completed", "conclusion": "cancelled", "run_started_at": AFTER_TS,
        "updated_at": "2026-01-11T05:00:00Z"},
}
# (forecast, outcome wanted, void wanted): run 1 took 30 minutes against 60; run 2 took 90 against 60; run 3 is in
# progress, open; run 4 was cancelled, void.
MINUTES_FIXTURE = (
    (_typed("build run 1 ends within 60 minutes of its start", 0.7, "session_minutes", {"run": 1, "bound": 60}), True,
     False),
    (_typed("build run 2 ends within 60 minutes of its start", 0.7, "session_minutes", {"run": 2, "bound": 60}), False,
     False),
    (_typed("build run 3 ends within 60 minutes of its start", 0.7, "session_minutes", {"run": 3, "bound": 60}), None,
     False),
    (_typed("build run 4 ends within 60 minutes of its start", 0.7, "session_minutes", {"run": 4, "bound": 600}),
     None, True),
)
LIMIT_RUNS = (  # (workflow, conclusion, steps): only a session run whose LIMIT_STEP failed is lost to the limit
    (".github/workflows/build.yml", "failure", (("usage limit", "failure"),)),
    (".github/workflows/review.yml", "failure", (("usage limit", "success"), ("claude", "failure"))),
    (".github/workflows/build.yml", "success", (("usage limit", "success"),)),
    (claims.PINS_WORKFLOW, "failure", (("usage limit", "failure"),)),
)
USAGE_LOG = (  # the same message id repeated once per content block counts once
    {"type": "assistant", "message": {"id": "m1", "usage": {"input_tokens": 10, "output_tokens": 5,
                                                             "cache_read_input_tokens": 100}}},
    {"type": "assistant", "message": {"id": "m1", "usage": {"input_tokens": 10, "output_tokens": 5,
                                                             "cache_read_input_tokens": 100}}},
    {"type": "assistant", "message": {"id": "m2", "usage": {"input_tokens": 1, "output_tokens": 2,
                                                             "cache_creation_input_tokens": 3}}},
)
DECLARATION_FORM = "run <run id> started <ISO time> on #<n>: expected <m> minutes; model <your model id>"
SESSION_COMMANDS = ("build", "review", "audit", "vizier")


def p0ak_session_declared() -> bool:
    """A session's first act is its declaration comment, naming the model; a log without it fails. The declaration's
    `session_minutes` forecast resolves from the Actions API run: within its bound true, beyond it false, in progress
    open, cancelled void; the price counts runs over their own bound and runs lost to the usage limit (instruction
    #112 Part A)."""
    from harness import ledger, sessions

    expect, ok = _expecter()
    for what, start, calls_, want in DECLARED_FIXTURE:
        got = {f.code for f in sessions.undeclared(sessions.calls(_log(*calls_)))}
        want_a = want & {"undeclared_session"}
        expect(got == want_a, f"{what}: findings {sorted(got)}, want {sorted(want_a)}")

    def observe(kind: str, *key: object) -> object:
        if kind != "run" or int(key[0]) not in RUN_ANSWERS:
            raise ledger.Unreadable(f"fixture has no answer to {(kind, *key)}")
        return RUN_ANSWERS[int(key[0])]

    rows = [f for f, _, _ in MINUTES_FIXTURE]
    got, unread = ledger.resolve(rows, observe, OUTCOME_NOW, "p0ak")
    by_id = {r["id"]: r for r in got}
    for f, want, void in MINUTES_FIXTURE:
        r = by_id.get(f["id"])
        said = "open" if r is None else ("void" if r.get("void") else r["outcome"])
        wanted = "void" if void else ("open" if want is None else want)
        expect(said == wanted, f"{f['claim']!r}: resolved {said}, want {wanted}")
    expect(not unread, f"every run read ({unread})")
    k, n = ledger.over_bound(rows + got, BEFORE_TS, LATER_TS)
    expect((k, n) == (1, 4), f"sessions-over-bound {k}/{n}, want 1/4 (run 2 over; run 3 open and run 4 void counted)")
    runs = [{"id": 200 + i, "path": w, "conclusion": c, "created_at": _h(1), "run_started_at": _h(1),
             "updated_at": _h(2), "steps": [{"name": s, "conclusion": sc} for s, sc in steps]}
            for i, (w, c, steps) in enumerate(LIMIT_RUNS)]
    priced = ledger.price([], {}, runs, T0, _h(PRICE_UNTIL))
    expect(priced.lost_to_limit == 1, f"sessions-lost-to-limit {priced.lost_to_limit}, want 1 (the build run whose "
                                      f"`{ledger.LIMIT_STEP}` step failed)")
    line = dataclasses.replace(priced, over_bound=k, bounded=n).status_line()
    expect(line.endswith("; sessions-over-bound 1/4; sessions-lost-to-limit 1"), f"STATUS price line {line!r}")
    expect(sessions.tokens(list(USAGE_LOG)) == 121, f"tokens {sessions.tokens(list(USAGE_LOG))}, want 121")
    expect(sessions.limit_reached([{"type": "result", "subtype": "error", "error": "usage_limit_reached"}])
           and not sessions.limit_reached([{"type": "result", "subtype": "success", "result": "done"}]),
           "a log whose last result carries usage_limit_reached is lost to the limit; one ending otherwise is not")
    for w, log in (("build.yml", "build.log"), ("review.yml", "review.log")):
        text = (ROOT / ".github" / "workflows" / w).read_text()
        expect(re.search(rf"- if: always\(\)\n\s+name: {re.escape(ledger.LIMIT_STEP)}\n\s+run: uv run --frozen python "
                         rf"-m harness\.sessions limit {re.escape(log)}\n", text) is not None,
               f"{w} runs `harness.sessions limit {log}` as the always-run step `{ledger.LIMIT_STEP}`")
    for c in SESSION_COMMANDS:
        text = (ROOT / ".claude" / "commands" / f"{c}.md").read_text()
        expect(f"`{c} {DECLARATION_FORM}`" in text and "session_minutes" in text and "harness.sessions tokens" in text,
               f"{c}.md: the first act is the declaration `{c} {DECLARATION_FORM}`, a session_minutes forecast, and "
               f"the tokens added at the end")
    return ok()


def p0an_session_routed() -> bool:
    """A session on a pull-request branch adds no forecast row; a session that writes no STATUS, review or audit file
    and posts no stop comment fails as an unrouted exit; each procedure says both (instruction #112 Part D)."""
    from harness import sessions

    expect, ok = _expecter()
    for what, start, calls_, want in DECLARED_FIXTURE:
        got = {f.code for f in sessions.declared_findings(_log(*calls_), start)}
        expect(got == want, f"{what}: findings {sorted(got)}, want {sorted(want)}")
    for c in SESSION_COMMANDS:
        text = (ROOT / ".claude" / "commands" / f"{c}.md").read_text()
        expect(f"`{c} run <run id> stopped <ISO time>:`" in text, f"{c}.md: a session that stops posts "
                                                                  f"`{c} run <run id> stopped <ISO time>:`")
    build = (ROOT / ".claude" / "commands" / "build.md").read_text()
    expect("On a pull-request branch, append no forecast row" in build,
           "build.md step 2: a pull-request branch takes no forecast row")
    return ok()


ROUTE_FIXTURE = (  # (what, event, prior `labeled blocked` rounds, mergeable, decision) -- instruction #126 item 3
    ("red pins, 0 rounds", "pins_red", 0, "UNKNOWN", "label"),
    ("red pins, 3 rounds", "pins_red", 3, "UNKNOWN", "issue"),
    ("conflicting pull request, 1 round", "pushed", 1, "CONFLICTING", "label"),
    ("clean pull request", "pushed", 0, "MERGEABLE", "nothing"),
)


def p0aq_red_returns_to_builder() -> bool:
    """A red pins run on a pull request, or a pull request in conflict after a push to master, is labelled `blocked`
    (its Builder restarts) while fewer than three `blocked` rounds stand, then files the issue to Guy; a clean pull
    request gets nothing (`harness.route.decide`, which `failed.yml` calls; instruction #126)."""
    from harness import route

    expect, ok = _expecter()
    for what, event, rounds, mergeable, want in ROUTE_FIXTURE:
        got = route.decide(event, rounds, mergeable)
        expect(got == want, f"{what}: {got}, want {want}")
    text = (ROOT / ".github" / "workflows" / "failed.yml").read_text()
    expect("python3 -m harness.route pins_red" in text and "python3 -m harness.route pushed" in text,
           "failed.yml decides both cases by harness.route")
    return ok()


def _job_blocks(text: str) -> dict[str, str]:
    """Each job's text in a workflow file, by job id: the lines from `  <id>:` under `jobs:` to the next job, or to the
    next top-level key or the file's end."""
    text = "\n" + text
    after = text.split("\njobs:\n", 1)[1] if "\njobs:\n" in text else ""
    body = re.split(r"^\S", after, maxsplit=1, flags=re.M)[0]
    heads = list(re.finditer(r"^  ([A-Za-z0-9_-]+):[ \t]*$", body, re.M))
    ends = [m.start() for m in heads[1:]] + [len(body)]
    return {m.group(1): body[m.start():end] for m, end in zip(heads, ends)}


def _job_permissions(job: str) -> dict[str, str] | str | None:
    """A job's `permissions:`: None if it sets none, the scalar (`read-all`, `write-all`) if one is given, else the
    scope-to-access map, in block or flow form."""
    m = re.search(r"^    permissions:[ \t]*(.*)$", job, re.M)
    if m is None:
        return None
    inline = m.group(1).split("#")[0].strip()
    if inline.startswith("{"):
        pairs = (p.split(":", 1) for p in inline.strip("{} ").split(",") if ":" in p)
        return {k.strip(): v.strip() for k, v in pairs}
    if inline:
        return inline
    rest = job[m.end():].split("\n")[1:]
    block = []
    for line in rest:
        if line.strip() and not line.startswith("      "):
            break
        block.append(line)
    pairs = (re.match(r"^      ([A-Za-z-]+):[ \t]*([A-Za-z-]+)", line) for line in block)
    return {p.group(1): p.group(2) for p in pairs if p}


def _checkout_ungranted(text: str) -> list[str]:
    """The jobs of a workflow file that set `permissions:` and use `actions/checkout` but grant no `contents` access:
    a job-level `permissions:` replaces the default token's, so such a checkout fails with "repository not found"."""
    def granted(perms) -> bool:
        return (perms in ("read-all", "write-all") if isinstance(perms, str)
                else perms.get("contents") in ("read", "write"))
    jobs = _job_blocks(text)
    return [name for name, job in jobs.items()
            if re.search(r"uses:\s*actions/checkout@", job) and (perms := _job_permissions(job)) is not None
            and not granted(perms)]


CHECKOUT_FIXTURE = (  # (what, workflow text, ungranted jobs) -- instruction #162
    ("a block grant without contents is flagged",
     "jobs:\n  a:\n    permissions:\n      issues: write\n    steps:\n      - uses: actions/checkout@v5\n", ["a"]),
    ("a block grant with contents: read passes",
     "jobs:\n  a:\n    permissions:\n      issues: write\n      contents: read\n    steps:\n"
     "      - uses: actions/checkout@v5\n", []),
    ("a flow grant without contents is flagged",
     "jobs:\n  a:\n    permissions: { issues: write }\n    steps:\n      - uses: actions/checkout@v5\n", ["a"]),
    ("read-all passes", "jobs:\n  a:\n    permissions: read-all\n    steps:\n      - uses: actions/checkout@v5\n", []),
    ("a job setting no permissions passes",
     "jobs:\n  a:\n    steps:\n      - uses: actions/checkout@v5\n", []),
    ("a job with no checkout passes", "jobs:\n  a:\n    permissions:\n      issues: write\n    steps:\n      - run: x\n",
     []),
    ("only the offending job of two is flagged",
     "jobs:\n  a:\n    permissions:\n      contents: write\n    steps:\n      - uses: actions/checkout@v5\n"
     "  b:\n    permissions:\n      issues: write\n    steps:\n      - uses: actions/checkout@v5\n", ["b"]),
)


def p0aw_checkout_granted() -> bool:
    """Every job in every workflow file that sets `permissions:` and uses `actions/checkout` grants `contents` access
    (instruction #162: since #153 merged, both `failed.yml` jobs failed at checkout with "repository not found")."""
    expect, ok = _expecter()
    for what, text, want in CHECKOUT_FIXTURE:
        got = _checkout_ungranted(text)
        expect(got == want, f"{what}: {got}, want {want}")
    files = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
    expect(bool(files), f"workflow files read: {len(files)}")
    for f in files:
        text = f.read_text()
        bad = _checkout_ungranted(text)
        expect(not bad, f"{f.name}: jobs {sorted(_job_blocks(text))}; checking out without contents: {bad}")
    return ok()


PINS_MASTER = ".github/workflows/pins-master.yml"
REGISTRY_PRELUDE = ("class Mutant:\n    def __init__(self, name, edits):\n        self.name = name\n"
                    "class Pin:\n    def __init__(self, name, protects, check, mutants, witnesses):\n"
                    "        self.name, self.mutants = name, mutants\n"
                    "f = g = e = W = None\n")
MASTER_REGISTRY = (REGISTRY_PRELUDE + 'PINS = [\n    Pin("A", "a", f, (Mutant("m1", e), Mutant("m2", e)), W),\n'
                   '    Pin("B", "b", g, (Mutant("m3", e),), W),\n]\n')
HEAD_REGISTRY = REGISTRY_PRELUDE + 'PINS = [\n    Pin("A", "a", f, (Mutant("m1", e), Mutant("m2", e)), W),\n]\n'
MASTER_NAMES = frozenset({"A", "A/m1", "A/m2", "B", "B/m3"})
HEAD_NAMES = frozenset({"A", "A/m1", "A/m2"})


def _step_run(text: str, name: str) -> str | None:
    """The script of the workflow step called `name` (a `run: |` block), or None."""
    m = re.search(rf"^      - name: {re.escape(name)}\n(?:        .*\n)*?        run: \|\n((?:          .*\n|\n)+)", text, re.M)
    return textwrap.dedent(m.group(1)) if m else None


def _accused_repo(root: Path) -> tuple[Path, str, str]:
    """A fixture origin whose master registers pins A (mutants m1, m2) and B (m3), and a pull request branch that
    deletes B and rewrites master's other harness file. Returns the clone on the branch, master's sha and the head's."""
    env = os.environ | claims.GIT_ENV | FIXTURE_GIT
    origin, work = root / "origin.git", root / "work"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True, capture_output=True, env=env)
    subprocess.run(["git", "clone", "-q", str(origin), str(work)], check=True, capture_output=True, env=env)
    git = _git_fixture(work)
    git("checkout", "-q", "-B", "master")
    for path, text in ((claims.REGISTRY_PATH, MASTER_REGISTRY), ("harness/judge.py", "master's judge\n"),
                       ("harness/proposer.d/old.toml", "old\n"), ("Makefile", "pins:\n"), ("pyproject.toml", "p\n"),
                       ("uv.lock", "l\n"), ("judge/world.py", "world\n")):
        _append(work, path, text)
    git("add", "-A")
    git("commit", "-q", "-m", "master")
    git("push", "-q", "origin", "master")
    base = git("rev-parse", "HEAD")
    git("checkout", "-q", "-b", "pr")
    (work / claims.REGISTRY_PATH).write_text(HEAD_REGISTRY)
    (work / "harness/judge.py").write_text("a judge that passes everything\n")
    _append(work, "harness/rogue.py", "import sitecustomize\n")
    _append(work, "harness/proposer.d/new.toml", "new\n")
    git("add", "-A")
    git("commit", "-q", "-m", "the accused")
    return work, base, git("rev-parse", "HEAD")


def p0ax_judge_from_master() -> bool:
    """The `pins-master` workflow checks out the pull request's head and restores master's harness/, Makefile,
    pyproject.toml and uv.lock over it, keeping only the pull request's proposer rows, before it runs the full `make
    pins` and the monotone check (instruction #176 items 1 and 3a). A fixture pull request that deletes pin B passes
    its own registry, fails master's, and is refused by `pins-monotone`."""
    expect, ok = _expecter()
    text = (ROOT / PINS_MASTER).read_text()
    expect(re.search(r"^on:\n  pull_request_target:\n    types: \[opened, synchronize, reopened, labeled\]\n", text, re.M)
           is not None and "\n  pull_request:" not in text, "the workflow runs on pull_request_target, not pull_request")
    expect(list(_job_blocks(text)) == ["pins-master"], f"its one job is pins-master ({list(_job_blocks(text))})")
    expect("ref: ${{ github.event.pull_request.head.sha }}" in text, "it checks out the pull request's head")
    expect("run: make pins PINS_OUT=out/pins\n" in text and "PINS_SINCE" not in text, "it runs the full `make pins`")
    expect("pins-monotone" in text, "it runs the monotone check")
    expect("pins-monotone" in (ROOT / ".github/workflows/pins.yml").read_text(), "pins.yml runs the monotone check")
    script = _step_run(text, "Restore the judge from master")
    expect(script is not None, "the restore step is found")
    root = Path(tempfile.mkdtemp(prefix="assize-p0ax-", dir=context.scratch))
    work, base, head = _accused_repo(root)
    git = _git_fixture(work)
    own = claims.registry_names_at(work)
    expect("B" not in own, f"the accused passes its own registry: B absent from {sorted(own)}")
    if script is not None:
        done = subprocess.run(["bash", "-c", script], cwd=work, capture_output=True, text=True,
                              env=os.environ | claims.GIT_ENV | FIXTURE_GIT)
        expect(done.returncode == 0, f"the restore step runs ({done.returncode}: {done.stderr.strip()[-200:]})")
        judged = claims.registry_names_at(work)  # a restore that deleted the head's harness leaves none
        expect("B" in judged and "B/m3" in judged, f"the judge's registry is master's: {sorted(judged)}")
        judge = work / "harness/judge.py"
        expect(judge.is_file() and judge.read_text() == "master's judge\n", "master's harness file replaces the head's")
        expect(not (work / "harness/rogue.py").exists(), "a harness file only the head has is gone")
        expect((work / "harness/proposer.d/new.toml").exists(), "the head's proposer row is kept")
    git("checkout", "-q", "-f", head)
    got = {f.where for f in claims.pins_monotone(work, base, head)}
    expect(got == {"B", "B/m3"}, f"pins-monotone refuses the deletion of B: {sorted(got)}")
    expect(not claims.pins_monotone(work, base, base), "a head equal to the base is monotone")
    return ok()


def p0ay_pins_monotone() -> bool:
    """A pin or mutant at the base and absent at the head is refused unless a head commit cites an instruction that
    carries Guy's authority and has a `Removes:` line naming it; adding pins is free (instruction #176 items 2 and 3b)."""
    expect, ok = _expecter()
    signed = claims.Issue("gfrmin", ("instruction",), "open", "gfrmin", SIGNED_AT, (), "Delete B.\nRemoves: B\n")
    cases = (
        ("no instruction", (), {}, {"B", "B/m3"}),
        ("instruction naming the pin", (5,), {5: signed}, set()),
        ("instruction naming only the mutant", (5,), {5: dataclasses.replace(signed, body="Removes: B/m3\n")}, {"B"}),
        ("instruction naming both, comma separated", (5,),
         {5: dataclasses.replace(signed, body="Removes: B/m3, B\n")}, set()),
        ("instruction not signed by gfrmin", (5,), {5: dataclasses.replace(signed, labeled_by="assize-builder")},
         {"B", "B/m3"}),
        ("issue not cited by the commit", (6,), {5: signed}, {"B", "B/m3"}),
        ("prose, not a Removes line", (5,), {5: dataclasses.replace(signed, body="Please delete B.\n")}, {"B", "B/m3"}),
        ("another pin named", (5,), {5: dataclasses.replace(signed, body="Removes: A\n")}, {"B", "B/m3"}),
    )
    for what, cited, issues, want in cases:
        commits = [claims.Commit("c" * 40, ("guy",), (), instructions=cited)]
        removed = claims.declared_removals(commits, issues)
        got = {f.where for f in claims.monotone_findings(MASTER_NAMES, HEAD_NAMES, removed)}
        expect(got == want, f"{what}: refused {sorted(got)}, want {sorted(want)}")
    got = {f.where for f in claims.monotone_findings(HEAD_NAMES, MASTER_NAMES, frozenset())}
    expect(not got, f"a head adding pin B is monotone ({sorted(got)})")
    expect(claims.registry_names(MASTER_REGISTRY) == MASTER_NAMES, "the registry loads as the names it holds")
    # Registries that spell the names and do not hold them: the check reads the registry as loaded (review F1 of PR #183).
    master = REGISTRY_PRELUDE + 'PINS = [\n    Pin("A", "a", f, (Mutant("m1", e), Mutant("m2", e)), W),\n'
    evasions = (
        ("a mutant commented out", master + '    Pin("B", "b", g, (),  # Mutant("m3", e)\n        W),\n]\n', {"B/m3"}),
        ("a pin parked in a string", master + ']\nNOTE = """\n    Pin("B", "b", g, (Mutant("m3", e),), W),\n"""\n',
         {"B", "B/m3"}),
        ("a mutant tuple sliced", master + '    Pin("B", "b", g, (Mutant("m3", e),)[:0], W),\n]\n', {"B/m3"}),
        ("the list filtered after it is built",
         master + '    Pin("B", "b", g, (Mutant("m3", e),), W),\n]\nPINS = [p for p in PINS if p.name != "B"]\n',
         {"B", "B/m3"}),
        ("a registry that does not load", master + '    Pin("B", "b", g, (Mutant("m3", e),), W),\n]\nraise SystemExit\n',
         None),
    )
    for what, text, want in evasions:
        head = claims.registry_names(text)
        got = {f.where for f in claims.monotone_findings(MASTER_NAMES, head, frozenset())}
        want = {claims.REGISTRY_PATH} if want is None else want
        expect(got == want, f"{what}: refused {sorted(got)}, want {sorted(want)}")
    got = {f.code for f in claims.monotone_findings(MASTER_NAMES, frozenset(), frozenset({"A", "B"}))}
    expect(got == {"registry_unreadable"}, f"a head registering no pin is refused even if all are named ({sorted(got)})")
    return ok()


def _workflow_privileges(text: str) -> list[str]:
    """What a workflow grants beyond read: a missing top-level `permissions:`, any scope not `read` or `none`, a scalar
    grant, a job-level grant, or any use of `secrets.` outside a comment."""
    found = []
    top = re.search(r"^permissions:[ \t]*(\S*)[ \t]*\n((?:  .*\n)*)", text, re.M)
    if top is None:
        found.append("no top-level permissions")
    elif top.group(1):
        found.append(f"scalar permissions {top.group(1)}")
    else:
        found += [f"{m.group(1)}: {m.group(2)}" for m in re.finditer(r"^  ([\w-]+):[ \t]*(\S+)", top.group(2), re.M)
                  if m.group(2) not in ("read", "none")]
    for job, block in _job_blocks(text).items():
        perms = _job_permissions(block)
        if perms is not None:
            found.append(f"job {job} sets permissions")
    found += [f"secret {m}" for line in text.splitlines() for m in re.findall(r"secrets\.\w+", line.split("#")[0])]
    return found


PRIVILEGE_FIXTURE = (
    ("read scopes", "permissions:\n  contents: read\n  issues: none\njobs:\n  j:\n    steps: []\n", []),
    ("a write scope", "permissions:\n  contents: read\n  issues: write\njobs:\n  j:\n    steps: []\n", ["issues: write"]),
    ("write-all", "permissions: write-all\njobs:\n  j:\n    steps: []\n", ["scalar permissions write-all"]),
    ("no permissions", "jobs:\n  j:\n    steps: []\n", ["no top-level permissions"]),
    ("a job grant", "permissions:\n  contents: read\njobs:\n  j:\n    permissions:\n      contents: write\n",
     ["job j sets permissions"]),
    ("a secret", "permissions:\n  contents: read\njobs:\n  j:\n    env: ${{ secrets.T }}\n", ["secret secrets.T"]),
    ("a secret in a comment", "permissions:\n  contents: read\n# no secrets.T\njobs:\n  j:\n    steps: []\n", []),
)


def p0az_pins_master_unprivileged() -> bool:
    """`pins-master` runs the pull request's code, so it grants no write scope, sets no job-level grant and uses no
    secret (instruction #176 item 3c)."""
    expect, ok = _expecter()
    for what, text, want in PRIVILEGE_FIXTURE:
        got = _workflow_privileges(text)
        expect(got == want, f"{what}: {got}, want {want}")
    got = _workflow_privileges((ROOT / PINS_MASTER).read_text())
    expect(not got, f"{PINS_MASTER} grants beyond read: {got}")
    return ok()


def _session_branch(git, repo: Path, base: str, branch: str, session: str, date: str) -> str:
    """A synthetic branch off `base` doing what one Builder session does: a forecast, a STATUS and a proposer row, each
    at the path `claims.session_files` gives. Returns the branch's name."""
    git("checkout", "-q", "-b", branch, base)
    files = claims.session_files(2, session, branch)
    row = {"id": session, "ts": "2026-10-01T00:00:00Z", "claim": f"{branch} is green", "p": 0.5}
    # The shared files are appended to or rewritten, as a session writing them does: a shared path collides.
    for path, text in ((files["forecasts"], json.dumps(row) + "\n"),
                       (files["status"], f"# STATUS — L2 — {date} — {branch[:7]:7} — PR #1\n"),
                       (files["proposer"], f'kind = "builder"\nmodel = "m"\nsession = "{session}"\n')):
        if path.endswith("STATUS.md"):
            (repo / path).write_text(text)
        else:
            _append(repo, path, text)
    git("add", "-A")
    git("commit", "-q", "-m", branch)
    return branch


def _merge_in_order(git, repo: Path, base: str, name: str, order: tuple[str, ...]) -> str | None:
    """Merge the branches into a fresh branch off `base`, in order, as pull requests: None if all merge, else the
    branch that conflicted."""
    git("checkout", "-q", "-b", name, base)
    for n, branch in enumerate(order, 1):
        try:
            git("merge", "-q", "--no-ff", "-m", f"Merge pull request #{n} from x/{branch}", branch)
        except subprocess.CalledProcessError:
            git("merge", "--abort")
            return branch
    return None


def p0ar_per_pr_files() -> bool:
    """Two pull requests each doing what one Builder session does (a forecast, a STATUS, a proposer row) merge with no
    conflict in either order; the ledger, the registry and the master STATUS view then read both pull requests' rows,
    the STATUS view being the file of the pull request merged last (instruction #135)."""
    from harness import ledger, registries

    expect, ok = _expecter()
    work = Path(tempfile.mkdtemp(prefix="assize-p0ar-", dir=context.scratch))
    repo = work / "repo"
    git = _git_fixture(repo)
    repo.mkdir()
    git("init", "-q", "-b", "master")
    _append(repo, "reports/L2/forecasts.jsonl", json.dumps({"id": "old", "ts": "2026-09-01T00:00:00Z", "claim": "c"}) + "\n")
    _append(repo, "reports/L2/STATUS.md", "# STATUS — L2 — 2026-09-01 — 0000000 — PR #0\n")
    _append(repo, "harness/proposer.toml", 'kind = "builder"\nmodel = "m"\nsession = "frozen"\n')
    git("add", "-A")
    git("commit", "-q", "-m", "base")
    base = git("rev-parse", "HEAD")
    # a's header is the later date, b's the earlier: the master view follows merge order, not the date
    a = _session_branch(git, repo, base, "branch-a", "sess-a", "2026-10-02")
    b = _session_branch(git, repo, base, "branch-b", "sess-b", "2026-10-01")
    for order in ((a, b), (b, a)):
        name = "merged-" + "-".join(order)
        conflict = _merge_in_order(git, repo, base, name, order)
        expect(conflict is None, f"merging {order} gives no conflict ({conflict!r} conflicted)")
        if conflict is not None:
            continue
        ids = {r["id"] for r in ledger.ledger_rows(repo)}
        expect({"old", "sess-a", "sess-b"} <= ids, f"{order}: the ledger reads the frozen row and both sessions' ({ids})")
        sessions = set(registries.proposers(repo))
        expect(sessions == {"frozen", "sess-a", "sess-b"}, f"{order}: the registry reads all three proposer rows ({sessions})")
        view = ledger.status_view(repo)
        expect(view is not None and view[0] == f"reports/L2/status/{order[-1]}.md",
               f"{order}: the master STATUS is the file of the pull request merged last, {order[-1]} "
               f"({view[0] if view else None})")
    git("checkout", "-q", "-b", "twin", base)
    _append(repo, "harness/proposer.d/other.toml", 'kind = "builder"\nmodel = "m"\nsession = "frozen"\n')
    try:
        registries.proposers(repo)
        expect(False, "a proposer row keyed twice across files is a registry error")
    except RegistryError as e:
        expect(e.code == "proposer_keyed_twice", f"a proposer row keyed twice across files is a registry error ({e})")
    shutil.rmtree(work, ignore_errors=True)
    return ok()


DRAFT_FORECAST_TS = "2026-01-10T00:00:00Z"
DRAFT_EVENT = {  # draft -> its timeline (the events the resolver reads)
    21: [{"event": "labeled", "actor": {"login": "gfrmin"}, "label": {"name": "instruction"}, "created_at": AFTER_TS}],
    22: [{"event": "labeled", "actor": {"login": "gfrmin"}, "label": {"name": "instruction"}, "created_at": LATER_TS}],
    23: [{"event": "labeled", "actor": {"login": "gfrmin"}, "label": {"name": "instruction"}, "created_at": LATER_TS}],
    24: [{"event": "closed", "actor": {"login": "assize-reviewer"}, "created_at": AFTER_TS}],
    25: [{"event": "labeled", "actor": {"login": "gfrmin"}, "label": {"name": "instruction"}, "created_at": AFTER_TS}],
    26: [{"event": "labeled", "actor": {"login": "assize-reviewer"}, "label": {"name": "needs-draft-check"},
          "created_at": AFTER_TS}],
}
DRAFT_EDITS = {  # draft -> its body's edits (None: the history cannot be read); the creation is the author's
    21: [{"editor": "assize-reviewer", "at": DRAFT_FORECAST_TS}],
    22: [{"editor": "assize-reviewer", "at": DRAFT_FORECAST_TS}, {"editor": "gfrmin", "at": AFTER_TS}],
    23: [{"editor": "assize-reviewer", "at": DRAFT_FORECAST_TS}, {"editor": "assize-reviewer", "at": AFTER_TS}],
    24: [],
    25: None,
    26: [],
}
DRAFT_WISH = 30


def _draft_forecast(claim: str, item: int, answer: str, kind: str = "vizier", cls: str = "draft") -> dict:
    f = _typed(claim, 0.7, "guy_answers", {"item": item, "answer": answer}, ts=DRAFT_FORECAST_TS)
    return f | {"proposer": f["proposer"] | {"kind": kind}, "class": cls, "mode": "recommend"}


# (forecast, outcome wanted or None for open, outcome_detail wanted)
DRAFT_RESOLUTION_FIXTURE = (
    (_draft_forecast("sign 21, signed as drafted", 21, "labeled:instruction"), True, "signed-as-drafted"),
    (_draft_forecast("sign 22, Guy edited first", 22, "labeled:instruction"), False, "signed-after-edit"),
    (_draft_forecast("edit 22", 22, "signed-after-edit", "reviewer", "draft-check"), True, "signed-after-edit"),
    (_draft_forecast("sign 23, edited by another account only", 23, "labeled:instruction"), True, "signed-as-drafted"),
    (_draft_forecast("sign 24, closed unsigned", 24, "labeled:instruction"), False, "declined"),
    (_draft_forecast("decline 24", 24, "closed", "reviewer", "draft-check"), True, "declined"),
    (_draft_forecast("sign 25, edits unreadable", 25, "labeled:instruction"), None, None),
    (_draft_forecast("sign 26, not yet answered", 26, "labeled:instruction"), None, None),
    (_draft_forecast(f'Guy answers sign on the draft "Twenty-one" of wish #{DRAFT_WISH}', DRAFT_WISH,
                     "labeled:instruction"), True, "signed-as-drafted"),
)
# the Vizier's class `draft`: 21, 23 and the wish's (21) signed as drafted; 22 after edit; 24 declined; 25, 26 open
DRAFT_RECORD_WANT = {"draft": (3, 1, 1), "draft-check": (0, 1, 1)}


def _draft_observe(kind: str, *key: object) -> object:
    from harness import ledger

    n = int(key[0])
    if kind == "issue":
        return {"number": n, "title": "x", "labels": ["wish"] if n == DRAFT_WISH else ["draft"]}
    if kind == "timeline" and n in DRAFT_EVENT:
        return DRAFT_EVENT[n]
    if kind == "edits" and n in DRAFT_EDITS:
        return DRAFT_EDITS[n]
    if kind == "drafts" and n == DRAFT_WISH:
        return [{"number": 22, "title": "Twenty-two", "body": f"Wish: #{DRAFT_WISH}\n"},
                {"number": 21, "title": "Twenty-one", "body": f"Wish: #{DRAFT_WISH}\n"}]
    raise ledger.Unreadable(f"fixture has no answer to {(kind, *key)}")


def p0al_draft_outcomes() -> bool:
    """A `guy_answers` forecast on a draft resolves to signed-as-drafted, signed-after-edit or declined, read from the
    draft's timeline and edit history; `labeled:instruction` is true only on signed-as-drafted; another account's edit
    is not gfrmin's; an unreadable edit history leaves it open; `ledger proposer` counts the three per class
    (instruction #112 Part B)."""
    from harness import ledger

    expect, ok = _expecter()
    rows = [f for f, _, _ in DRAFT_RESOLUTION_FIXTURE]
    got, unread = ledger.resolve(rows, _draft_observe, OUTCOME_NOW, "p0al")
    by_id = {r["id"]: r for r in got}
    for f, want, detail in DRAFT_RESOLUTION_FIXTURE:
        r = by_id.get(f["id"], {})
        expect((r.get("outcome"), r.get("outcome_detail")) == (want, detail),
               f"{f['claim']!r}: resolved {r.get('outcome', 'open')} / {r.get('outcome_detail')}, want "
               f"{'open' if want is None else want} / {detail}")
    expect(not unread, f"every draft read ({unread})")
    for kind, cls in (("vizier", "draft"), ("reviewer", "draft-check")):
        rec = {r.cls: r for r in ledger.record(rows + got, kind)}
        print(f"    {rec.get(cls)}")
        expect(cls in rec and rec[cls].details == DRAFT_RECORD_WANT[cls],
               f"{kind} {cls}: drafts {rec[cls].details if cls in rec else None} by outcome, want "
               f"{DRAFT_RECORD_WANT[cls]}")
        expect(cls in rec and "signed-as-drafted=" in str(rec[cls]) and "declined=" in str(rec[cls]),
               f"{kind} {cls}: the record prints the three outcomes")
    return ok()


DRAFT_CHECK_EVENTS = (  # (what, sender, event, action, label, must start a review) -- instruction #112 Part C
    ("needs-draft-check on an issue", "assize-reviewer", "issues", "labeled", "needs-draft-check", True),
    ("draft on an issue", "assize-reviewer", "issues", "labeled", "draft", False),
    ("needs-review on a pull request by assize-builder", "assize-builder", "pull_request", "labeled", "needs-review",
     True),
)


def p0am_draft_check_trigger() -> bool:
    """A `needs-draft-check` label on an issue starts a review session in the draft-check mode on that issue; a
    `draft` label does not; `needs-review` on a pull request still does (instruction #112 Part C)."""
    expect, ok = _expecter()
    text = (ROOT / ".github" / "workflows" / "review.yml").read_text()
    condition = _review_condition(text)
    expect(condition is not None, "the review job's `if:` is found")
    for what, sender, event, action, label, want in DRAFT_CHECK_EVENTS:
        got = condition is not None and _github_condition(condition, {
            "github.event.sender.login": sender, "github.event_name": event, "github.event.action": action,
            "github.event.label.name": label})
        expect(got is want, f"{what}: {'starts' if got else 'does not start'} a review (must "
                            f"{'start' if want else 'not start'})")
    expect('issues:needs-draft-check) run="review /review draft $ISSUE"' in text,
           "the chosen procedure on needs-draft-check is `/review draft <issue>`")
    expect("needs-draft-check" in text.split("jobs:")[0] and "draft-check mode" in text.split("jobs:")[0],
           "the workflow states that needs-draft-check starts a draft check")
    review = (ROOT / ".claude" / "commands" / "review.md").read_text()
    vizier = (ROOT / ".claude" / "commands" / "vizier.md").read_text()
    expect("## Draft-check mode: `/review draft <issue number>`" in review
           and "`Draft check: sign | edit | decline — p=<p> that Guy agrees — <reason>`" in review,
           "review.md has the draft-check mode and its comment")
    expect("add the label `needs-draft-check`" in vizier and "until a `Draft check:` comment exists" in vizier,
           "vizier.md labels each draft needs-draft-check and does not address Guy before the check")
    return ok()


DRAFT_SINCE, DRAFT_AFTER, DRAFT_BEFORE = "2026-03-01T00:00:00Z", "2026-03-02T00:00:00Z", "2026-02-01T00:00:00Z"
DRAFT_AMEND = "Wish: #{w}\nBrief amendment to `docs/briefs/brief-2-nethack.md`, titled `Wish #{t}`:\n\n## Amendment: x\n"
DRAFT_BECAUSE = "Instruction because: it blocks the queue today.\n"
DRAFT_FIXTURE = (  # (what, body, opened, rule merged, findings wanted) -- instruction #111 Part A
    ("a brief amendment", DRAFT_AMEND.format(w=5, t=5), DRAFT_AFTER, DRAFT_SINCE, set()),
    ("an instruction with its reason", "Wish: #6\n" + DRAFT_BECAUSE + "Do the thing.\n", DRAFT_AFTER, DRAFT_SINCE, set()),
    ("neither form", "Wish: #7\nDo the thing.\n", DRAFT_AFTER, DRAFT_SINCE, {"no_form"}),
    ("both forms", DRAFT_AMEND.format(w=8, t=8) + DRAFT_BECAUSE, DRAFT_AFTER, DRAFT_SINCE, {"both_forms"}),
    ("no wish on the first line", DRAFT_BECAUSE, DRAFT_AFTER, DRAFT_SINCE, {"no_wish"}),
    ("an amendment titled for another wish", DRAFT_AMEND.format(w=9, t=10), DRAFT_AFTER, DRAFT_SINCE, {"wrong_wish"}),
    ("the reason twice", "Wish: #11\n" + DRAFT_BECAUSE * 2, DRAFT_AFTER, DRAFT_SINCE, {"repeated_form"}),
    ("opened before the rule merged", "Wish: #12\nDo the thing.\n", DRAFT_BEFORE, DRAFT_SINCE, set()),
    ("the rule has not merged", "Do the thing.\n", DRAFT_AFTER, None, set()),
)


def p0ac_draft_form() -> bool:
    """A `draft` issue opened after the rule merged (claims.draft_from, the merge dated from git as the price rule's is)
    opens `Wish: #<n>` and carries exactly one of an `Instruction because:` line and a brief amendment titled for that
    wish; a draft with neither or both is out of order (instruction #111 Part A item 4). The real drafts are read in CI
    once the rule has merged."""
    expect, ok = _expecter()
    for what, body, at, since, want in DRAFT_FIXTURE:
        got = {f.code for f in claims.draft_findings(1, body, at, since)}
        expect(got == want, f"{what}: findings {sorted(got)}, want {sorted(want)}")
    root = _real_root()
    base = _branch_base(root)
    since = claims.draft_from(root, base) if base else None
    expect(base is not None, f"master's merge base with HEAD read ({base})")
    if since is None:
        print("    real: the draft rule has not merged on master's first-parent line; the real-tree check covers no draft")
        return ok()
    try:
        real = claims.load_drafts(root, since)
    except (OSError, subprocess.SubprocessError) as e:
        real, _ = {}, expect(False, f"real drafts not read ({e})")
    found = [f for n, (body, at) in sorted(real.items()) for f in claims.draft_findings(n, body, at, since)]
    print(f"    real: rule merged {since}; {len(real)} drafts opened since: {sorted(real)}")
    expect(not found, f"real drafts: findings {[str(f) for f in found]}")
    return ok()


PICK_PROPOSER = {"kind": "mechanism", "model": "chooser:p0", "session": "p0"}
PICK_TS, PICK_UNTIL, PICK_WITHIN, PICK_AFTER = ("2026-01-10T00:00:00Z", "2026-01-20T00:00:00Z", "2026-01-15T00:00:00Z",
                                                "2026-01-25T00:00:00Z")
PICK_NOW = "2026-02-01T00:00:00Z"
CHOOSE_ACT = ("--model", "m", "--pr", "7", "--p-kept", "0.8", "--p-merged", "0.6")  # the acting Builder's


def _pick(entrant: str, cands: list, chose: str, shown: str | None = None, rid: str = "r", dist: dict | None = None,
          ts: str = PICK_TS) -> dict:
    from harness import chooser

    return chooser.pick_row(entrant, cands, dist or chooser.point(cands, chose), chose, shown or chose, PICK_UNTIL, rid,
                            ts, "0" * 40, PICK_PROPOSER)


def _commit(git, message: str = "x") -> str:
    git("add", "-A")
    git("commit", "-q", "-m", message)
    return git("rev-parse", "HEAD")


def _status_with(row: dict, over: list | None = None, chose: str | None = None) -> str:
    from harness import chooser

    a = row["args"]
    return ("# STATUS — L2 — 2026-10-12 — abc1234 — PR #1\n"
            + chooser.chose_line(chose or a["chose"], over or a["candidates"], {"fixed-order": 0.5, "priorities-literal": 0.5},
                                 a["hash"], "chooser") + "\n")


def _chose_repo(repo: Path):
    """A fixture history of `chose:` lines: R1 sealed before its line; R2 added in the same commit as its line; R3
    added after its line; R4's line omits a candidate; R5 has no forecast at all; R6's line chose outside the
    candidates. Returns the git helper and the rows by name."""
    git = _git_fixture(repo)
    repo.mkdir(parents=True)
    git("init", "-q", "-b", "master")
    status, ledger_path = "reports/L2/STATUS.md", "reports/L2/forecasts.jsonl"
    rows = {n: _pick("mixture", ["#1", "#2", "#3"], "#1", rid=n) for n in ("R1", "R2", "R3", "R4", "R6")}
    rows["R5"] = _pick("mixture", ["#1", "#2", "#3"], "#1", rid="R5")
    _append(repo, ledger_path, json.dumps(rows["R1"]) + "\n")
    _commit(git, "forecast R1")
    (repo / status).write_text(_status_with(rows["R1"]))
    _commit(git, "act on R1")
    _append(repo, ledger_path, json.dumps(rows["R2"]) + "\n")
    (repo / status).write_text(_status_with(rows["R2"]))
    _commit(git, "forecast and act on R2")
    (repo / status).write_text(_status_with(rows["R3"]))
    _commit(git, "act on R3")
    _append(repo, ledger_path, json.dumps(rows["R3"]) + "\n")
    _commit(git, "forecast R3, late")
    _append(repo, ledger_path, json.dumps(rows["R4"]) + "\n")
    _commit(git, "forecast R4")
    (repo / status).write_text(_status_with(rows["R4"], over=["#1", "#2"]))
    _commit(git, "act on R4, omitting #3")
    (repo / status).write_text(_status_with(rows["R5"]))
    _commit(git, "act on R5, never forecast")
    _append(repo, ledger_path, json.dumps(rows["R6"]) + "\n")
    _commit(git, "forecast R6")
    (repo / status).write_text(_status_with(rows["R6"], chose="#9"))
    _commit(git, "act on R6, choosing outside the candidates")
    return git, rows


CHOSE_WANT = {"R1": set(), "R2": {"late"}, "R3": {"late"}, "R4": {"candidates"}, "R5": {"no_forecast"},
              "R6": {"not_a_candidate"}}


def p0ad_chooser_sealed() -> bool:
    """A `guy_picks` forecast row is first present in a strict ancestor of the commit where the STATUS `chose:` line
    citing its hash first appears; a row first present in the same commit or later is late. The line lists exactly the
    candidates its forecast declares and chooses one of them. `python -m harness.chooser choose` prints rows that
    pass the ledger check, a mixture row whose hash the line cites, and a line that passes all of these once committed
    in order (instruction #111 Part B items 1, 3 and 9a, 9e)."""
    import contextlib
    import io

    from harness import chooser

    expect, ok = _expecter()
    work = Path(tempfile.mkdtemp(prefix="assize-p0ad-", dir=context.scratch))
    repo = work / "repo"
    _, rows = _chose_repo(repo)
    by_hash = {r["args"]["hash"][:12]: n for n, r in rows.items()}
    got: dict[str, set] = {n: set() for n in rows}
    for f in chooser.chose_findings(repo):
        got[by_hash[f.where.split()[1]]].add(f.code)
    for n, want in CHOSE_WANT.items():
        expect(got[n] == want, f"{n}: findings {sorted(got[n])}, want {sorted(want)}")
    cli = work / "cli"
    git = _git_fixture(cli)
    cli.mkdir()
    git("init", "-q", "-b", "master")
    _append(cli, "harness/entrants.toml", 'sovereign = ["fixed-order", "priorities-literal"]\n[bound]\nloss = 5.0\n')
    _append(cli, chooser.SEED_PATH, "seed0\n")
    _append(cli, "reports/L2/forecasts.jsonl", json.dumps(_forecast("open", 0.5)) + "\n")
    _commit(git)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = chooser.main(["choose", "#1", "#2", "#3", *CHOOSE_ACT, "--until", PICK_UNTIL, "--ts", PICK_TS,
                           "--session", "p0ad", "--repo", str(cli)])
    lines = out.getvalue().splitlines()
    printed = [json.loads(line) for line in lines[:-1]]
    picks = [r for r in printed if r.get("type") == "guy_picks"]
    line = chooser.CHOSE.match(lines[-1]) if lines else None
    expect(rc == 0 and line is not None and len(picks) == 2, f"choose exits 0 and prints two guy_picks rows and a line "
                                                            f"({rc}, {len(picks)} rows)")
    if line is None or len(picks) != 2:
        return False
    mixture = next(r for r in picks if r["args"]["entrant"] == chooser.MIXTURE)
    expect([f.code for f in claims.ledger_findings([json.dumps(r) for r in printed])] == [],
           "the printed rows pass the ledger check")
    expect(all(r["args"]["hash"] == chooser.forecast_hash(r["args"]) for r in picks), "each row's hash is its SHA-256")
    expect(line["hash"] == mixture["args"]["hash"] and [c.strip() for c in line["over"].split(",")] == ["#1", "#2", "#3"],
           "the line cites the mixture row's hash and lists every candidate")
    expect(line["regime"] == chooser.regime_at("seed0", 0), "the line names the regime the seed assigns the first choice")
    _append(cli, "reports/L2/forecasts.jsonl", "".join(json.dumps(r) + "\n" for r in printed))
    _commit(git, "forecasts")
    (cli / "reports/L2/STATUS.md").write_text("# STATUS — L2 — 2026-10-12 — abc1234 — PR #1\n" + lines[-1] + "\n")
    _commit(git, "act")
    (cli / "reports/L2/STATUS.md").unlink()
    _commit(git, "withdraw")

    def findings(repo: Path) -> list[str]:
        """The check's findings, or the git failure it raised reading history, as one finding."""
        try:
            return [str(f) for f in chooser.chose_findings(repo)]
        except subprocess.CalledProcessError as e:
            return [f"raised: {e}"]

    found = findings(cli)
    expect(not found, f"the printed rows, committed first, then the line, pass the check, a later commit deleting the "
                      f"STATUS read as no text ({found})")
    root = _real_root()
    found = findings(root)
    print(f"    real: {'?' if found else len(chooser.chose_history(root))} chose lines in history")
    expect(not found, f"real chose lines: findings {found}")
    shutil.rmtree(work, ignore_errors=True)
    return ok()


def _ev(event: str, actor: str, at: str, label: str | None = None) -> dict:
    return {"event": event, "actor": {"login": actor}, "created_at": at} | ({"label": {"name": label}} if label else {})


def _picks_case(base: int, events: dict[int, list]) -> tuple[dict, dict]:
    cands = [f"#{base + 1}", f"#{base + 2}"]
    return _pick("fixed-order", cands, cands[0], rid=f"c{base}"), {("timeline", base + i): events.get(i, []) for i in (1, 2)}


# (what, item number base, events by offset, resolution wanted); None = open
PICKS_FIXTURE = (
    ("next on another candidate", 110, {2: [_ev("labeled", "gfrmin", PICK_WITHIN, "next")]},
     {"outcome": False, "answer": "next", "pick": {"kind": "item", "item": "#112"}}),
    ("later on the item chosen", 120, {1: [_ev("labeled", "gfrmin", PICK_WITHIN, "later")]},
     {"outcome": False, "answer": "later", "pick": {"kind": "not", "item": "#121"}}),
    ("next on the item chosen", 130, {1: [_ev("labeled", "gfrmin", PICK_WITHIN, "next")]},
     {"outcome": True, "answer": "next", "pick": {"kind": "item", "item": "#131"}}),
    ("silence after he saw it", 140, {1: [_ev("labeled", "gfrmin", PICK_WITHIN, "seen")]},
     {"outcome": True, "answer": "silent-default", "pick": {"kind": "item", "item": "#141"}}),
    ("silence, never seen", 150, {}, {"outcome": False, "void": "unexposed"}),
    ("seen by another account", 160, {1: [_ev("labeled", "assize-reviewer", PICK_WITHIN, "seen")]},
     {"outcome": False, "void": "unexposed"}),
    ("seen after the silence was counted", 170, {1: [_ev("labeled", "gfrmin", PICK_AFTER, "seen")]},
     {"outcome": False, "void": "unexposed"}),
    ("a next by another account", 180, {2: [_ev("labeled", "assize-reviewer", PICK_WITHIN, "next")]},
     {"outcome": False, "void": "unexposed"}),
    ("a comment saying next", 190, {1: [_ev("commented", "gfrmin", PICK_WITHIN)]}, {"outcome": False, "void": "unexposed"}),
)
SILENT_FIXTURE = (  # (forecast type, args, events by item, resolution wanted)
    ("guy_answers", {"item": 31, "answer": "silent-default", "until": PICK_UNTIL}, {31: [_ev("labeled", "gfrmin", PICK_WITHIN, "seen")]},
     {"outcome": True}),
    ("guy_answers", {"item": 32, "answer": "silent-default", "until": PICK_UNTIL}, {32: []},
     {"outcome": False, "void": "unexposed"}),
    ("guy_answers", {"item": 33, "answer": "silent-default", "until": PICK_UNTIL},
     {33: [_ev("labeled", "gfrmin", PICK_TS, "seen"), _ev("reopened", "gfrmin", PICK_WITHIN)]}, {"outcome": False}),
    ("not_overturned", {"item": 41, "until": PICK_UNTIL, "exposure": "seen"}, {41: [_ev("labeled", "gfrmin", PICK_WITHIN, "seen")]},
     {"outcome": True}),
    ("not_overturned", {"item": 42, "until": PICK_UNTIL, "exposure": "seen"}, {42: []}, {"outcome": False, "void": "unexposed"}),
    ("not_overturned", {"item": 43, "until": PICK_UNTIL, "exposure": "seen"},
     {43: [_ev("labeled", "gfrmin", PICK_TS, "seen"), _ev("labeled", "gfrmin", PICK_WITHIN, "later")]}, {"outcome": False}),
    ("not_overturned", {"item": 44, "until": PICK_UNTIL}, {44: []}, {"outcome": True}),  # made before the regime
)


def p0ae_exposure_and_labels() -> bool:
    """Guy's pick is resolved by code from the labels he applies (`next`, `later`), never by a comment; silence picks the
    item shown only if gfrmin applied `seen` before it was counted, and otherwise is void -- answered, not scored, and
    counted in the denominator; the same holds for `silent-default` on `guy_answers` and for a `not_overturned`
    forecast made under the exposure regime (instruction #111 Part B items 2 and 5, 9b)."""
    from harness import ledger

    expect, ok = _expecter()
    rows, answers = [], {}
    for what, base, events, want in PICKS_FIXTURE:
        f, seen_by_api = _picks_case(base, events)
        rows.append(f)
        answers.update(seen_by_api)
    for n, (ftype, args, events, want) in enumerate(SILENT_FIXTURE):
        rows.append(_typed(f"{ftype} {n}", 0.7, ftype, args))
        answers.update({("timeline", item): ev for item, ev in events.items()})
    early = _pick("fixed-order", ["write the brief", "audit"], "write the brief", rid="early")

    def observe(kind: str, *key: object) -> object:
        if (kind, *key) not in answers:
            raise ledger.Unreadable(f"fixture has no answer to {(kind, *key)}")
        return answers[(kind, *key)]

    got, unread = ledger.resolve(rows + [early], observe, PICK_NOW, "p0ae")
    by_id = {r["id"]: r for r in got}
    wants = [(f["claim"], f["id"], w) for f, (_, _, _, w) in zip(rows[:len(PICKS_FIXTURE)], PICKS_FIXTURE)]
    wants += [(f["claim"], f["id"], w) for f, (_, _, _, w) in zip(rows[len(PICKS_FIXTURE):], SILENT_FIXTURE)]
    for claim, i, want in wants:
        r = by_id.get(i, {})
        have = {k: r.get(k) for k in want}
        expect(have == want, f"{claim}: resolved {have}, want {want}")
    expect(not unread, f"nothing unread ({unread})")
    expect(all(r["proposer"]["kind"] == "mechanism" and r.get("witness") for r in got), "each is the mechanism's, witnessed")
    expect(early["id"] in by_id and by_id[early["id"]].get("void") == "unexposed",
           "silence on an item with no issue to be seen on is void")
    before, _ = ledger.resolve([early], observe, PICK_WITHIN, "p0ae")
    expect(not before, f"silence before the count is open ({before})")
    all_rows = rows + [early] + got
    voids = {r["id"] for r in got if r.get("void")}
    expect(voids and not (voids & ledger.outcomes(all_rows).keys()), "a void resolution is not a scored outcome")
    again, _ = ledger.resolve(all_rows, observe, PICK_NOW, "p0ae")
    expect(not again, f"a void forecast is answered, not resolved again ({again})")
    counts = ledger.pick_counts(all_rows)
    made = sum(1 for r in all_rows if r.get("type") == "guy_picks" and "claim" in r)
    expect(counts == {"scored": 4, "void": 6, "open": 0} and sum(counts.values()) == made,
           f"guy_picks: {counts} over {made} made (voids counted in the denominator)")
    findings = claims.ledger_findings(_ledger(*rows, early, *got))
    expect(not findings, f"forecasts and resolutions pass the ledger check ({[str(f) for f in findings]})")
    return ok()


def _fixed_share_by_definition(entrants: list, rounds: list, alpha: float) -> dict:
    """The forward algorithm of the hidden Markov model whose state is the best entrant: stay with probability 1 -
    alpha + alpha / K, move to each other entrant with alpha / K. Per round the state's weight is multiplied by the
    likelihood of Guy's pick under that entrant's forecast (an abstainer by that of the mixture of those that made
    one), renormalised (left alone if every likelihood is zero), then pushed through the transition matrix."""
    k = len(entrants)
    trans = [[(1 - alpha) * (i == j) + alpha / k for j in range(k)] for i in range(k)]
    w = [1.0 / k] * k
    for r in rounds:
        live = [i for i, e in enumerate(entrants) if e in r.dists]
        if not live:
            continue
        z = sum(w[i] for i in live)

        def lik(e: str) -> float:
            kind, x = r.pick
            m = r.dists[e].get(x, 0.0)
            return m if kind == "item" else 1 - m

        mixed = sum(w[i] / z * lik(entrants[i]) for i in live)
        v = [w[i] * (lik(e) if e in r.dists else mixed) for i, e in enumerate(entrants)]
        if sum(v) > 0:
            w = [x / sum(v) for x in v]
        w = [sum(w[i] * trans[i][j] for i in range(k)) for j in range(k)]
    return dict(zip(entrants, w))


def p0af_fixed_share() -> bool:
    """The chooser's weights are Fixed Share over the sovereign entrants' log-loss on Guy's resolved picks, with alpha
    derived from the switching-regret bound (s / (T - 1), s the declared change-points); `fixed-order` is a required
    entrant and the choice until a sovereign act follows the last change-point; the priorities entrant abstains
    without an ordering (instruction #111 Part B items 4, 7 and 9c, 9d)."""
    import contextlib
    import io
    import tomllib

    from harness import chooser, ledger

    expect, ok = _expecter()
    for (s, t), want in (((1, 11), 0.1), ((2, 5), 0.5), ((0, 11), 0.1), ((5, 3), 1.0), ((1, 1), 1.0)):
        expect(math.isclose(chooser.derived_alpha(s, t), want), f"alpha(s={s}, T={t}) = {chooser.derived_alpha(s, t)}, want {want}")
    a, b = chooser.point(["a", "b"], "a"), chooser.point(["a", "b"], "b")
    half = {"a": 0.5, "b": 0.5}
    entrants = [chooser.FIXED, chooser.PRIORITIES, "llm"]
    day = "2026-01-{:02d}T00:00:00Z".format
    both = {chooser.FIXED: a, chooser.PRIORITIES: b}
    rounds = [chooser.Round(day(1), both | {"llm": half}, ("item", "b"), True), chooser.Round(day(2), both, ("item", "b"), True),
              chooser.Round(day(3), both, ("item", "b"), True), chooser.Round(day(4), both | {"llm": half}, ("item", "a"), True),
              chooser.Round(day(5), both, ("not", "b"), True),
              chooser.Round(day(6), {chooser.FIXED: a, chooser.PRIORITIES: a, "llm": a}, ("item", "b"), True)]
    alpha = 2 / (len(rounds) - 1)
    want = _fixed_share_by_definition(entrants, rounds, alpha)
    have = chooser.weights(entrants, rounds, chooser.derived_alpha(2, len(rounds)))
    expect(all(math.isclose(have[e], want[e], abs_tol=1e-12) for e in entrants),
           f"weights {have}, by the definition at alpha {alpha}: {want}")
    expect(all(w >= alpha / len(entrants) - 1e-12 for w in have.values()) and math.isclose(sum(have.values()), 1.0),
           "every entrant keeps at least alpha / K of the weight, and the weights sum to 1: one that was wrong "
           "(with infinite loss) can come back")
    # (d) fixed-order is the choice until a sovereign act follows the last change-point
    past = [chooser.Round(day(i), both, ("item", "b"), True) for i in (1, 2, 3)]
    silent = [chooser.Round(day(7), both, ("item", "b"), False)]
    for what, rs, cps, regime, wantc, via in (
            ("no act since the change-point", past, [day(5)], "chooser", "a", chooser.FIXED),
            ("an act after the change-point", past, [day(1)], "chooser", "b", chooser.MIXTURE),
            ("the fixed-order regime", past, [day(1)], chooser.FIXED, "a", chooser.FIXED),
            ("silence is no act", silent, [day(5)], "chooser", "a", chooser.FIXED)):
        got = chooser.choose(["a", "b"], both, rs, cps, regime)
        expect((got.chose, got.via) == (wantc, via), f"{what}: chose {got.chose} via {got.via}, want {wantc} via {via}")
    ordering = chooser.ordering_of("Priorities\n1. #12 the chooser\n- #7\n* later\n")
    expect(ordering == ["#12 the chooser", "#7", "later"], f"ordering read from list items: {ordering}")
    expect(chooser.priorities_literal(["#7", "#9", "#12"], ordering) == chooser.point(["#7", "#9", "#12"], "#12")
           and chooser.priorities_literal(["#9"], ordering) is None and chooser.priorities_literal(["#9"], []) is None,
           "priorities-literal puts all the mass on the first candidate the ordering names, and abstains otherwise")
    root = _real_root()
    listed = tomllib.loads((root / ledger.ENTRANTS).read_text()).get(chooser.SOVEREIGN)
    expect(isinstance(listed, list) and chooser.FIXED in listed, f"the checkout's sovereign list ({listed}) holds {chooser.FIXED}")
    work = Path(tempfile.mkdtemp(prefix="assize-p0af-", dir=context.scratch))
    repo = work / "repo"
    git = _git_fixture(repo)
    repo.mkdir()
    git("init", "-q", "-b", "master")
    _append(repo, ledger.ENTRANTS, 'sovereign = ["priorities-literal"]\n[bound]\nloss = 5.0\n')
    _commit(git)
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        rc = chooser.main(["choose", "a", *CHOOSE_ACT, "--until", PICK_UNTIL, "--ts", PICK_TS, "--session", "p0af",
                           "--repo", str(repo)])
    expect(rc == 2 and "is not a sovereign entrant" in err.getvalue(), f"a sovereign list without {chooser.FIXED} is refused "
                                                                      f"({rc}: {err.getvalue().strip()})")
    shutil.rmtree(work, ignore_errors=True)
    return ok()


def p0ag_switchback() -> bool:
    """The switchback's schedule is recomputed from the committed seed -- the parity of its SHA-256 fixes the first
    regime and the rest alternate -- and equals the regimes the STATUS `chose:` lines record; a choice with no seed, or
    a seed committed after the first choice, fails (instruction #111 Part C, the pin)."""
    from harness import chooser

    expect, ok = _expecter()
    import hashlib

    def parity(s: str) -> int:  # the definition, written out here: the first regime is the SHA-256's parity
        return int(hashlib.sha256(s.encode()).hexdigest(), 16) % 2

    seeds = {r: next(s for s in (f"seed{i}" for i in range(64)) if chooser.REGIMES[parity(s)] == r)
             for r in chooser.REGIMES}
    for r, s in seeds.items():
        schedule = [chooser.regime_at(s, i) for i in range(5)]
        expect(schedule[0] == r and all(schedule[i] != schedule[i + 1] for i in range(4)),
               f"seed {s!r} starts with {r} and alternates: {schedule}")
        lines = [{"regime": x} for x in schedule]
        expect(not chooser.switchback_findings(s, lines), f"{s!r}: the recorded regimes equal the schedule")
        swapped = [lines[0] | {"regime": schedule[1]}] + lines[1:]
        expect({f.code for f in chooser.switchback_findings(s, swapped)} == {"regime"},
               f"{s!r}: a first choice in the other regime is a finding")
    expect({f.code for f in chooser.switchback_findings(None, [{"regime": "chooser"}])} == {"unseeded"}
           and not chooser.switchback_findings(None, []), "a choice with no seed is unseeded; no choice, no finding")
    work = Path(tempfile.mkdtemp(prefix="assize-p0ag-", dir=context.scratch))
    for name, seed_first, want in (("seed_first", True, set()), ("seed_late", False, {"late"})):
        repo = work / name
        git = _git_fixture(repo)
        repo.mkdir()
        git("init", "-q", "-b", "master")
        row = _pick("mixture", ["#1", "#2"], "#1", rid=name)
        seed = seeds["chooser"]
        _append(repo, "reports/L2/forecasts.jsonl", json.dumps(row) + "\n")
        _commit(git, "forecast")
        if seed_first:
            _append(repo, chooser.SEED_PATH, seed + "\n")
            _commit(git, "seed")
        text = _status_with(row).replace("regime chooser", f"regime {chooser.regime_at(seed, 0)}")
        (repo / "reports/L2/STATUS.md").write_text(text)
        _commit(git, "act")
        if not seed_first:
            _append(repo, chooser.SEED_PATH, seed + "\n")
            _commit(git, "seed, after the act")
        got = {f.code for f in chooser.seed_findings(repo)}
        expect(got == want, f"{name}: findings {sorted(got)}, want {sorted(want)}")
    root = _real_root()
    found = chooser.seed_findings(root)
    print(f"    real: {len(chooser.chose_history(root))} chose lines in history")
    expect(not found, f"real switchback: findings {[str(f) for f in found]}")
    shutil.rmtree(work, ignore_errors=True)
    return ok()


def _observer(answers: dict):
    from harness import ledger

    def observe(kind: str, *key: object) -> object:
        if (kind, *key) not in answers:
            raise ledger.Unreadable(f"fixture has no answer to {(kind, *key)}")
        return answers[(kind, *key)]

    return observe


ACT_RESOLVES = (  # (what, events on the chosen issue, the not_overturned resolution wanted)
    ("seen, then silence", [_ev("labeled", "gfrmin", PICK_WITHIN, "seen")], {"outcome": True}),
    ("silence, never seen", [], {"outcome": False, "void": "unexposed"}),
    ("seen, then later", [_ev("labeled", "gfrmin", PICK_TS, "seen"), _ev("labeled", "gfrmin", PICK_WITHIN, "later")],
     {"outcome": False}),
)


def p0ah_chooser_files_act() -> bool:
    """`python -m harness.chooser choose` files, beside the `guy_picks` rows, `not_overturned {item: <chose>, until}`
    under the exposure regime -- the item is the instruction's issue, or for a brief item the pull request that carries
    it -- and #77's `merged {pr}`, both with the acting Builder's p and proposer; and they resolve by code: silence after
    gfrmin's `seen` keeps the choice, silence unseen is void, `later` overturns it, the merge resolves `merged`
    (instruction #111 Part B item 3)."""
    import contextlib
    import io

    from harness import chooser, ledger

    expect, ok = _expecter()
    work = Path(tempfile.mkdtemp(prefix="assize-p0ah-", dir=context.scratch))
    repo = work / "repo"
    git = _git_fixture(repo)
    repo.mkdir()
    git("init", "-q", "-b", "master")
    _append(repo, ledger.ENTRANTS, 'sovereign = ["fixed-order", "priorities-literal"]\n[bound]\nloss = 5.0\n')
    _append(repo, chooser.SEED_PATH, "seed0\n")
    _commit(git)

    def run(cands: list, *extra: str) -> tuple[int, list[dict]]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            rc = chooser.main(["choose", *cands, *CHOOSE_ACT, *extra, "--until", PICK_UNTIL, "--ts", PICK_TS,
                               "--session", "p0ah", "--repo", str(repo)])
        return rc, [json.loads(line) for line in out.getvalue().splitlines() if line.startswith("{")]

    builder = {"kind": "builder", "model": "m", "session": "p0ah"}
    acts: dict[str, list[dict]] = {}
    for cands, item in ((["#41", "#42"], 41), (["write the brief", "#42"], 7)):
        rc, rows = run(cands)
        kept = [r for r in rows if r.get("type") == "not_overturned"]
        merged = [r for r in rows if r.get("type") == "merged"]
        acts[cands[0]] = kept + merged
        want = {"item": item, "until": PICK_UNTIL, "exposure": "seen", "chose": cands[0]}
        expect(rc == 0 and len(kept) == 1 and {k: kept[0]["args"].get(k) for k in want} == want and kept[0]["p"] == 0.8,
               f"{cands[0]}: one not_overturned {want} at p 0.8 ({[r['args'] | {'p': r['p']} for r in kept]})")
        expect(len(merged) == 1 and merged[0]["args"].get("pr") == 7 and merged[0]["p"] == 0.6,
               f"{cands[0]}: one merged {{pr: 7}} at p 0.6 ({[r['args'] for r in merged]})")
        expect(all(r["proposer"] == builder for r in kept + merged), "the act's rows are the acting Builder's")
        found = claims.ledger_findings([json.dumps(r) for r in rows])
        expect(not found, f"{cands[0]}: the printed rows pass the ledger check ({[str(f) for f in found]})")
    for bad in (("--p-kept", "1"), ("--p-merged", "0")):
        rc, rows = run(["#41"], *bad)
        expect(rc == 2 and not rows, f"{' '.join(bad)} is refused, nothing printed (exit {rc})")
    rows = acts["#41"]
    if len(rows) != 2:
        shutil.rmtree(work, ignore_errors=True)
        return False
    kept, merged = rows
    for what, events, want in ACT_RESOLVES:
        observe = _observer({("timeline", 41): events, ("pr", 7): {"merged": True, "merged_at": PICK_WITHIN}})
        got, unread = ledger.resolve(rows, observe, PICK_NOW, "p0ah")
        by = {r["id"]: r for r in got}
        have = {k: by.get(kept["id"], {}).get(k) for k in want}
        expect(have == want and not unread, f"{what}: not_overturned resolved {have}, want {want} ({unread})")
        expect(by.get(merged["id"], {}).get("outcome") is True, f"{what}: merged resolved true on the merge")
    shutil.rmtree(work, ignore_errors=True)
    return ok()


PROBE_BRIEF = "### Constants, pre-stated here\nk (probes per boundary brief) = 2. Switchback length = the rest.\n"


def _act(n: int, exposure: bool = True) -> dict:
    return _typed(f"act on #{n}", 0.8, "not_overturned", {"item": n, "until": PICK_UNTIL}
                  | ({"exposure": "seen"} if exposure else {}))


def _answered(f: dict, outcome: bool, void: str | None = None) -> dict:
    return {"id": f["id"], "ts": PICK_NOW, "proposer": {"kind": "mechanism", "model": "harness.ledger", "session": "r"},
            "outcome": outcome, **({"void": void} if void else {})}


# The acts on #51-#54 were seen and kept; #55 was void (never seen); #56 was overturned; #57 is open; #58 was made
# before the exposure regime; #59 was seen and kept but is already probed.
PROBE_ACTS = {n: _act(n, exposure=n != 58) for n in range(51, 60)}
PROBE_ROWS = ([*PROBE_ACTS.values()]
              + [_answered(PROBE_ACTS[n], True) for n in (51, 52, 53, 54, 58, 59)]
              + [_answered(PROBE_ACTS[55], False, "unexposed"), _answered(PROBE_ACTS[56], False)])
PROBE_POOL = {51, 52, 53, 54}


def p0ai_probes() -> bool:
    """At a boundary brief, `python -m harness.ledger probe` draws k act-alone choices (k as the brief pre-states it)
    from the exposed-and-silent set -- acts made under the exposure regime, kept, not void, not overturned, not open,
    not probed -- ranked by the SHA-256 of `<ledger head>:<id>`; each probe is a `not_overturned` forecast that defaults
    to keep and is resolved false by gfrmin's overturn; every probe is a guy-item of the price (instruction #111 Part B
    item 6)."""
    import contextlib
    import hashlib
    import io

    from harness import ledger

    expect, ok = _expecter()
    expect(ledger.probe_k(PROBE_BRIEF) == 2, "k is read from the brief's pre-stated constant")
    try:
        ledger.probe_k("no constant here\n")
        expect(False, "a brief that states no k is refused")
    except ValueError:
        expect(True, "a brief that states no k is refused")
    real = (ROOT / "docs/briefs/brief-2-nethack.md").read_text()
    expect(ledger.probe_k(real) == 2, "brief 2 pre-states k = 2")
    vizier = {"kind": "vizier", "model": "m", "session": "p0ai"}
    already = ledger.probe_row(PROBE_ACTS[59], "s", PICK_UNTIL, PICK_TS, "0" * 40, vizier)
    rows = PROBE_ROWS + [already]
    pool = ledger.exposed_and_silent(rows)
    have = {f["args"]["item"] for f in pool}
    expect(have == PROBE_POOL, f"exposed-and-silent: {sorted(have)}, want {sorted(PROBE_POOL)}")

    def by_definition(seed: str, k: int) -> list[int]:
        ranked = sorted(pool, key=lambda f: hashlib.sha256(f"{seed}:{f['id']}".encode()).hexdigest())
        return [f["args"]["item"] for f in ranked[:k]]

    draws = {s: [f["args"]["item"] for f in ledger.draw_probes(pool, s, 2)] for s in (f"head{i}" for i in range(8))}
    expect(all(d == by_definition(s, 2) for s, d in draws.items()), f"each draw is the SHA-256 ranking ({draws})")
    expect(len({tuple(d) for d in draws.values()}) > 1, "the draw depends on the ledger head")
    expect([f["args"]["item"] for f in ledger.draw_probes(pool, "s", 9)] == by_definition("s", 9),
           "a pool smaller than k is drawn whole")
    probes = [ledger.probe_row(f, "head0", PICK_UNTIL, PICK_TS, "0" * 40, vizier) for f in ledger.draw_probes(pool, "head0", 2)]
    found = claims.ledger_findings(_ledger(*rows, *probes))
    expect(not found, f"the probe rows pass the ledger check ({[str(f) for f in found]})")
    expect(all(p["p"] == PROBE_ACTS[p["args"]["item"]]["p"] for p in probes), "a probe's p is its act's")
    probe = probes[0]
    item = probe["args"]["item"]
    for what, events, want in (
            ("left alone", [], True),
            ("later by gfrmin", [_ev("labeled", "gfrmin", PICK_WITHIN, "later")], False),
            ("later by another account", [_ev("labeled", "assize-reviewer", PICK_WITHIN, "later")], True)):
        got, unread = ledger.resolve([probe], _observer({("timeline", item): events}), PICK_NOW, "p0ai")
        have = [(r["outcome"], r.get("void")) for r in got]
        expect(have == [(want, None)] and not unread, f"probe {what}: resolved {have}, want {[(want, None)]}")
    reached = ledger.probes_reached(rows + probes)
    priced = ledger.price(reached, {}, [], PICK_TS, PICK_NOW)
    want_items = tuple(sorted({59, *(p["args"]["item"] for p in probes)}))
    expect(priced.items == want_items, f"probes are guy-items of the price: {priced.items}, want {want_items}")
    work = Path(tempfile.mkdtemp(prefix="assize-p0ai-", dir=context.scratch))
    repo = work / "repo"
    git = _git_fixture(repo)
    repo.mkdir()
    git("init", "-q", "-b", "master")
    _append(repo, "brief.md", PROBE_BRIEF)
    _append(repo, "none.md", "no constant\n")
    _append(repo, "reports/L2/forecasts.jsonl", "".join(json.dumps(r) + "\n" for r in rows))
    _commit(git)
    for brief, want_rc, want_n in (("brief.md", 0, 2), ("none.md", 2, 0)):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            rc = ledger.main(["probe", "--brief", str(repo / brief), "--until", PICK_UNTIL, "--ts", PICK_TS,
                              "--session", "p0ai", "--model", "m", "--repo", str(repo)])
        printed = [json.loads(line) for line in out.getvalue().splitlines() if line.startswith("{")]
        seed = ledger.probe_seed(repo)
        expect(rc == want_rc and len(printed) == want_n
               and [p["args"]["item"] for p in printed] == by_definition(seed, want_n)
               and all(p["args"]["seed"] == seed for p in printed),
               f"probe --brief {brief}: exit {rc}, {len(printed)} rows drawn at the ledger head (want {want_rc}, {want_n})")
    shutil.rmtree(work, ignore_errors=True)
    return ok()


WITNESS_PINS = frozenset({"fixture/a", "fixture/all", "fixture/docs"})
WITNESS_CASES = (  # (what, branch of the fixture repository, the pins that run) -- instruction #108 item 5
    ("(i) a change to reports/L2/STATUS.md alone", "status", {"fixture/all"}),
    ("(ii) a change under src/a/", "src_a", {"fixture/a", "fixture/all"}),
    ("(iii) a change under harness/", "harness", WITNESS_PINS),
)
WITNESS_SINCE_RUN = 7


def _witness_repo(repo: Path) -> tuple[str, str]:
    """A fixture repository: a base commit; one branch per WITNESS_CASES case changing its path; `side`, a commit off
    the base that no case branch descends from; `verdict` adding a REPORT.md verdict line and `brief` a brief.
    Returns the base and the side commit."""
    git = _git_fixture(repo)
    repo.mkdir(parents=True)
    git("init", "-q", "-b", "master")
    for path in ("src/a/x.py", "docs/d.md", "reports/L2/STATUS.md", "harness/h.py", "REPORT.md"):
        _append(repo, path, "0\n")
    git("add", "-A")
    git("commit", "-q", "-m", "base")
    base = git("rev-parse", "HEAD")
    for branch, path in (("status", "reports/L2/STATUS.md"), ("src_a", "src/a/x.py"), ("harness", "harness/h.py"),
                         ("side", "docs/d.md"), ("verdict", "REPORT.md"), ("brief", "docs/briefs/brief-3-x.md")):
        git("checkout", "-q", "-b", branch, base)
        _append(repo, path, "- L2 — FIT\n" if branch == "verdict" else "1\n")
        git("add", "-A")
        git("commit", "-q", "-m", branch)
    return base, git("rev-parse", "side")


def p0w_witnessed_paths() -> bool:
    """`python -m harness run --since <sha>` runs a pin, clean and every mutant, only if a path changed since that sha
    matches one of its witnesses, and every pin if a changed path is under harness/; it records every other pin as
    skipped, citing the sha and its pins run, and never counts a skip as ok. `runner.choose_base` takes the newest
    successful run whose head is an ancestor of HEAD and whose report skipped nothing; `runner.boundary` reads a layer
    verdict or a new brief, on which every pin runs (instruction #108)."""
    expect, ok = _expecter()
    try:
        validate([dataclasses.replace(witness.PINS[0], witnesses=())])
        expect(False, "a pin witnessing nothing is refused")
    except RegistryError as e:
        expect(e.code == "no_witnesses", f"a pin witnessing nothing is refused ({e.code})")
    globs = (("src/a/b/c.py", "src/a/**", True), ("src/ab.py", "src/a/**", False), ("Makefile", "**/Makefile", True),
             ("reports/L2/STATUS.md", "**", True), ("docs/d.md", "docs/*", True), ("docs/x/d.md", "docs/*", False))
    for path, glob, want in globs:
        expect(runner.matches(path, glob) is want, f"{path} {'matches' if want else 'does not match'} {glob}")
    work = Path(tempfile.mkdtemp(prefix="assize-p0w-", dir=context.scratch))
    repo = work / "repo"
    base, side = _witness_repo(repo)
    git = _git_fixture(repo)
    fast = ROOT / "harness" / "fixtures" / "fast.toml"
    since = ("--since", base, "--since-run", str(WITNESS_SINCE_RUN), "--repo", str(repo))
    git("checkout", "-q", "status")
    full = run_nested("witness-full", "fixture.witness", "all", config=fast)
    expect(full.exit_code == 0 and {r["pin"] for r in full.runs("clean")} == WITNESS_PINS
           and full.summary.get("skipped") == 0 and not full.runs("skipped"),
           f"without --since every pin runs ({full.summary})")
    reports = {}
    for what, branch, want in WITNESS_CASES:
        git("checkout", "-q", branch)
        n = run_nested(f"witness-{branch}", "fixture.witness", "all", config=fast, extra=since)
        reports[branch] = n.rows
        skipped = n.runs("skipped")
        s = n.summary
        expect(n.exit_code == 0 and {r["pin"] for r in n.runs("clean")} == want
               and {r["pin"] for r in n.runs("mutant")} == want == {r["pin"] for r in n.runs("twin")},
               f"{what}: ran {sorted(r['pin'] for r in n.runs('clean'))}, clean and every mutant; want {sorted(want)}")
        expect({r["pin"] for r in skipped} == WITNESS_PINS - want == set(n.registry.get("skipped", ()))
               and all(r.get("verdict") == "skipped" and r.get("since") == base
                       and r.get("since_run") == WITNESS_SINCE_RUN for r in skipped),
               f"{what}: skipped {sorted(r['pin'] for r in skipped)}, each citing {base[:7]} and run "
               f"{WITNESS_SINCE_RUN}; want {sorted(WITNESS_PINS - want)}")
        expect(s.get("clean_ok") == s.get("clean_total") == len(want) == s.get("killed") == s.get("mutants_total")
               and s.get("skipped") == s.get("skipped_mutants") == len(WITNESS_PINS - want)
               and s.get("since") == base and s.get("since_run") == WITNESS_SINCE_RUN,
               f"{what}: clean {s.get('clean_ok')}/{s.get('clean_total')}, mutants {s.get('killed')}/"
               f"{s.get('mutants_total')}, skipped {s.get('skipped')} pins {s.get('skipped_mutants')} mutants; want "
               f"{len(want)}/{len(want)}, {len(want)}/{len(want)}, {len(WITNESS_PINS - want)}")
    expect(runner.full_report(full.rows) and not runner.full_report(reports["status"]),
           "a full report is a base; one that skipped a pin is not")
    git("checkout", "-q", "status")
    runs = ({"id": 3, "head_sha": side, "conclusion": "success"}, {"id": 2, "head_sha": base, "conclusion": "success"},
            {"id": 1, "head_sha": base, "conclusion": "success"})
    by_id = {3: full.rows, 2: reports["status"], 1: full.rows}
    got, refused = runner.choose_base(repo, runs, by_id.get)
    expect(got == (base, 1), f"(iv) the base passes over a run off HEAD's ancestry and one whose report skipped a pin: "
                             f"chose {got}, refused {refused}; want ({base[:7]}, run 1)")
    got, refused = runner.choose_base(repo, runs[:2], by_id.get)
    expect(got is None, f"(iv) with no usable base, none is chosen and every pin runs: chose {got}, refused {refused}")
    for branch, want in (("status", False), ("verdict", True), ("brief", True)):
        git("checkout", "-q", branch)
        got = runner.boundary(repo, "master")
        expect(got is want, f"branch {branch}: {'a' if got else 'no'} layer boundary (a REPORT.md verdict line or a "
                            f"new brief is one)")
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
    disjoint from every issued seed (brief 1 section 2). The CSPRNG is witnessed, not assumed: every issued seed must be
    one that `secrets.randbelow` returned during the request (review 9d8e7336a6b9 F1, L2a obligation 7)."""
    import secrets

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

    real, drawn = secrets.randbelow, []  # every CSPRNG draw, recorded as it is made (review 9d8e7336a6b9 F1)

    def recorded(bound: int) -> int:
        drawn.append((bound, real(bound)))
        return drawn[-1][1]

    secrets.randbelow = recorded
    issued: list[int] = []
    try:
        for rid in ("request-a", "request-b"):  # each from the store as the files left it, no state carried over
            try:
                got = seeds.issue(root, world, key, n, rid)
            except seeds.SeedError as e:
                got = []
                print(f"    issue({rid!r}) raised {e}")
            print(f"    {rid}: {got}")
            expect(len(got) == n, f"{rid}: {n} seeds issued")
            issued += got
    finally:
        secrets.randbelow = real
    from_csprng = {s for bound, s in drawn if bound == seeds.SEED_SPACE}
    expect(bool(issued) and set(issued) <= from_csprng,
           f"every issued seed is a draw of secrets.randbelow(SEED_SPACE) ({len(set(issued) - from_csprng)} of "
           f"{len(issued)} are not; {len(drawn)} draws)")
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
    end as the World ends them. Each record is yielded by `episodes.played` once final, before the World after the next
    is drawn (reports/L1/REPORT.md obligation 4 on L2). No candidate container is left listed (brief 1 section 2)."""
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
            records: list[dict] = []
            drawn: list[int] = []

            def worlds():
                for w in _short_crafter(n):
                    drawn.append(len(records))
                    yield w

            records.extend(r for r in episodes.played(rt, image, worlds(), binding.manifest(),
                                                      command=candidates.command(behaviour), t=tt))
            say(f"  {rt.name} {behaviour}: {json.dumps(records)}")
            expect(all(d >= i - 1 for i, d in enumerate(drawn)),
                   f"{rt.name} {behaviour}: each record is yielded before the World after next is drawn, so it can "
                   f"be written as its episode ends (records yielded at each draw: {drawn})")
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


def p22_replay_verified() -> bool:
    """Replay checks a request's records against its signed head (brief 2 A2, L2a obligation 3; review 6debf231b630 F2).
    Of two signed requests, `evaluate._recorded` returns the first's records exactly as written and an unknown request
    as None; and refuses `ledger_unverified` when a utility is altered, a record is dropped, a record is added, the
    head's signature is forged, or the heads file is not JSONL (review c1ef406 F4)."""
    from judge import evaluate, ledger, registry

    expect, ok = _expecter()
    work = Path(tempfile.mkdtemp(prefix="assize-p22-", dir=context.scratch))
    try:
        led, private = work / "ledger.jsonl", work / "private"
        (a_id, a), (b_id, b) = P9_REQUESTS
        held_a = ledger.append(led, private, a_id, a)
        ledger.append(led, private, b_id, b)
        written, heads = led.read_bytes(), (private / ledger.HEADS).read_bytes()
        rows = [json.loads(line) for line in written.splitlines()]

        def replay(name: str, want) -> None:
            try:
                got = evaluate._recorded(led, private, a_id)
            except registry.Refused as e:
                got = e.code
            expect(got == want, f"{name}: replay gives {want if isinstance(want, str) else 'the records as written'} "
                                f"(got {got if isinstance(got, str) else 'records'})")

        def put(path: Path, out: list[dict]) -> None:
            path.write_bytes(b"".join(ledger.canonical(r) + b"\n" for r in out))

        tampers = (
            ("a utility altered", lambda: put(led, [r | {"utility": r["utility"] + 99} if i == 0 else r
                                                    for i, r in enumerate(rows)])),
            ("a record dropped", lambda: put(led, [r for i, r in enumerate(rows) if i != 1])),
            ("a record added", lambda: put(led, rows[:3] + [rows[0]] + rows[3:])),
            ("the head's signature forged", lambda: put(private / ledger.HEADS, [
                json.loads(h) | {"mac": "0" * 64} for h in heads.splitlines()])),
            ("the heads file not JSONL", lambda: (private / ledger.HEADS).write_bytes(heads + b"{not json\n")),
        )
        replay("untouched", held_a)
        expect(evaluate._recorded(led, private, "p22-unknown") is None, "a request never signed replays as None")
        for name, act in tampers:
            act()
            replay(name, "ledger_unverified")
            led.write_bytes(written)
            (private / ledger.HEADS).write_bytes(heads)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return ok()

# P23's child judge (brief 2 A2, L2a obligation 4): `evaluate()` as written, over Crafter, with the runtime, the image
# check and the episode loop faked so no container starts. The fake loop keeps `episodes.played`'s contract, each
# record yielded once the next World is drawn, and the judge kills itself with SIGKILL on drawing episode KILL_AT's
# World. Prints the request's records, or its refusal code.
P23_RUN = """
import json, os, signal, sys, types
from pathlib import Path
from judge import episodes, evaluate, registry
private, ledgers, party, rid, n, kill_at, image = (Path(sys.argv[1]), Path(sys.argv[2]), json.loads(sys.argv[3]),
                                                   sys.argv[4], int(sys.argv[5]), int(sys.argv[6]), sys.argv[7])
try:
    registry.proposer_of(private, image)
except registry.Refused:
    registry.register(private, image, registry.credential(private, party))

def played(rt, image, worlds, manifest, **kw):
    pending = []
    for i, w in enumerate(worlds):
        yield from pending
        if i == kill_at:
            os.kill(os.getpid(), signal.SIGKILL)
        pending = [{"episode": i, "termination": "terminal", "detail": "", "steps": w.t, "utility": w.utility}]
    yield from pending

episodes.played = played
evaluate._usable = lambda name: types.SimpleNamespace(name=name)
evaluate._present = lambda rt, image: None
try:
    print(json.dumps(evaluate.evaluate(image, "crafter", n, rid, private=private, ledgers=ledgers, runtime_name="fake")))
except registry.Refused as e:
    print(json.dumps(e.code))
"""
P23_PARTY = {"kind": "builder", "model": "claude-opus-5-5", "session": "p23-fixture-party"}
P23_IMAGE = "sha256:" + "c" * 64
P23_ASKED, P23_KILL_AT = 3, 2  # the killed request asks 3 episodes and dies drawing the third's World: 2 played


def p23_interrupted_recorded() -> bool:
    """An interrupted request's played episodes are in the ledger (brief 2 A2, L2a obligation 4; review 6debf231b630
    F3). A child judge asked for 3 Crafter episodes is killed by SIGKILL drawing the third's World: the ledger then holds
    the 2 episodes it played, unsigned. A second request, from another child, first seals the killed one: its 2 records
    and one closing record stating `interrupted`, 3 seeds issued and 2 recorded, signed; it is then killed drawing its
    own first World, so it played nothing. The next request seals that one too (1 seed issued, 0 recorded), then writes
    its own 2 records. Every record, each closing record included, carries the image and the registering `proposer`
    (A1.7; review 0a2c02c F2), which for the request that played nothing only its issuance can supply. The ledger
    verifies at its last head and holds exactly these. The killed request asked again is refused `interrupted`,
    changing nothing. No container starts: the runtime and loop are faked, keeping `episodes.played`'s contract, which
    P3 pins on the real loop."""
    from judge import evaluate, ledger

    expect, ok = _expecter()
    work = Path(tempfile.mkdtemp(prefix="assize-p23-", dir=context.scratch))
    try:
        private, ledgers = work / "private", work / "ledgers"
        led = evaluate.ledger_path(ledgers, "crafter")

        def child(rid: str, n: int, kill_at: int = -1) -> tuple[int, object]:
            r = subprocess.run(proc.python("-c", P23_RUN, str(private), str(ledgers), json.dumps(P23_PARTY), rid,
                                           str(n), str(kill_at), P23_IMAGE),
                               cwd=ROOT, env=proc.child_env(), capture_output=True, text=True, timeout=120)
            return r.returncode, json.loads(r.stdout) if r.stdout.strip() else r.stderr.strip()[-500:]

        def rows() -> list[tuple]:
            return [(r["request_id"], r.get("episode"), r.get("interrupted"), r.get("issued"), r.get("recorded"),
                     r.get("image") == P23_IMAGE and r.get("proposer") == P23_PARTY)
                    for r in ledger._lines(led)] if led.exists() else []

        code, out = child("p23-killed", P23_ASKED, P23_KILL_AT)
        print(f"  killed child: exit {code}; ledger {rows()}")
        expect(code == -signal.SIGKILL, f"the child judge died by SIGKILL mid-request (exit {code}: {out})")
        played = [("p23-killed", i, None, None, None, True) for i in range(P23_KILL_AT)]
        expect(rows() == played, f"the ledger holds the {P23_KILL_AT} episodes the killed request played ({rows()})")

        code, out = child("p23-unplayed", 1, 0)
        print(f"  unplayed child: exit {code}; ledger {rows()}")
        sealed = played + [("p23-killed", None, True, P23_ASKED, P23_KILL_AT, True)]
        expect(code == -signal.SIGKILL and rows() == sealed,
               f"a second child seals the killed request, {P23_ASKED} seeds issued and {P23_KILL_AT} recorded, "
               f"attributed, and dies by SIGKILL before playing (exit {code}; {rows()})")

        code, out = child("p23-next", 2)
        print(f"  next child: exit {code}; ledger {rows()}")
        want = sealed + [("p23-unplayed", None, True, 1, 0, True)] + [("p23-next", i, None, None, None, True)
                                                                      for i in range(2)]
        expect(code == 0 and rows() == want,
               f"the next request seals the unplayed one, 1 seed issued and 0 recorded, attributed to its image and "
               f"proposer, before its own 2 records (exit {code}; {rows()})")
        anchor = out[-1]["sha256"] if code == 0 and out else ""
        found = ledger.verify(led, private, anchor)
        expect(found == [], f"the ledger verifies at the next request's head ({found})")

        was = led.read_bytes()
        code, out = child("p23-killed", P23_ASKED)
        expect(code == 0 and out == "interrupted" and led.read_bytes() == was,
               f"the killed request asked again is refused interrupted, the ledger unchanged (exit {code}: {out})")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return ok()


# P24's episode counts (brief 2 A2, L2a obligation 5): written as the judge's CLI receives them. Each of the first
# five satisfies `str.isdigit` yet is no count `int` reads as one; the rest are not digits at all or are not positive.
P24_BAD = ("²", "٣", "①", "0", "00", "-1", "+3", "2.5", " 3", "")
P24_GOOD = (("1", 1), ("3", 3), ("007", 7), ("12", 12))


def p24_episode_guard() -> bool:
    """The judge's `evaluate` refuses an episode count that is not a positive ASCII integer with the code
    `bad_episodes`, exit 1 and no traceback; it reads every positive ASCII integer as itself (brief 2 A2, L2a
    obligation 5; review 6debf231b630 F4). The guard runs before any path, so the CLI is given none that exists."""
    from judge import __main__ as cli

    expect, ok = _expecter()
    for bad in P24_BAD:
        r = subprocess.run(proc.python("-m", "judge", "evaluate", "/nonexistent/private", "/nonexistent/ledgers", "fake",
                                       "sha256:" + "d" * 64, "crafter", bad, "p24-request"),
                           cwd=ROOT, env=proc.child_env(), capture_output=True, text=True, timeout=120)
        expect(r.returncode == 1 and r.stderr.startswith("refused: bad_episodes") and "Traceback" not in r.stderr,
               f"{bad!r} is refused bad_episodes with exit 1 and no traceback (exit {r.returncode}: "
               f"{r.stderr.strip().splitlines()[-1:]})")
    for text, want in P24_GOOD:
        got = cli._episodes(text)
        expect(got == want, f"{text!r} is read as {want} (got {got})")
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
    signed is refused `interrupted`, and sealed into the ledger as such. The judge hash changes when any of judge config and code, the interface, the
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
                try:
                    evaluate.evaluate(image, "crafter", 1, "p17-b", private=private, ledgers=ledgers,
                                      runtime_name=rt.name)
                    code = "evaluated"
                except registry.Refused as e:
                    code = e.code
                sealed = ledger._lines(led)[len(got):]
                expect(code == "interrupted" and [(r["request_id"], r.get("interrupted"), r.get("issued"),
                                                   r.get("recorded")) for r in sealed] == [("p17-b", True, 1, 0)]
                       and ledger.verify(led, private, sealed[-1]["sha256"]) == [],
                       f"{rt.name} seeds issued, records never signed: refused interrupted ({code}), and sealed into "
                       f"the ledger as interrupted with its 1 seed issued and 0 episodes recorded, verifying "
                       f"({[{k: r.get(k) for k in ('request_id', 'interrupted', 'issued', 'recorded')} for r in sealed]})")
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


# Witnesses (instruction #108 item 1): the paths each pin's check or mutants read. A change under harness/, or to
# Makefile, pyproject.toml or uv.lock, runs every pin whatever it witnesses (runner.FORCE_ALL); a pin that reads the
# real branch, the ledgers or the GitHub API witnesses ALWAYS.
HARNESS = ("harness/**",)
# The judge side: every pin playing or reading the judge, a World, an incumbent, the pilot or the host scripts.
JUDGE_SIDE = ("judge/**", "worlds/**", "incumbents/**", "pilot/**", "scripts/**")
# P0b scans every code file of the tree (scan.code_files).
CODE_FILES = ("**/*.py", "**/*.sh", "**/*.yml", "**/*.yaml", "**/Makefile", "**/Dockerfile", "**/Containerfile")

PINS = [
    Pin("P0", "surviving mutants are reported and fail the suite",
        p0_survivors_reported, (Mutant("survivors_ignored", _edits("P0_survivors_ignored")),), HARNESS),
    Pin("P0b", "no code reads a mutant or test variable from the environment",
        p0b_no_switches, (Mutant("env_switch", _edits("P0b_env_switch")),
                         Mutant("judge_imports_mutants", _edits("P0b_judge_imports_mutants"))), CODE_FILES),
    Pin("P0c", "a failing clean check is recorded and fails the suite",
        p0c_clean_failure, (Mutant("clean_failures_ignored", _edits("P0c_clean_failures_ignored")),), HARNESS),
    Pin("P0d", "errors and timeouts are INCONCLUSIVE, counted in the denominator, and fail the suite",
        p0d_inconclusive, (Mutant("inconclusive_dropped", _edits("P0d_inconclusive_dropped")),), HARNESS),
    Pin("P0e", "a registry with a mutant-less pin, a duplicated name or a malformed edit is refused",
        p0e_registry_validation, (Mutant("validation_off", _edits("P0e_validation_off")),), HARNESS),
    Pin("P0f", "a mutant whose twin fails is NON-CAUSAL and fails the suite",
        p0f_non_causal, (Mutant("twin_ignored", _edits("P0f_twin_ignored")),), HARNESS),
    Pin("P0g", "an anchor that does not occur exactly once is STALE and fails the suite",
        p0g_stale, (Mutant("stale_ignored", _edits("P0g_stale_ignored")),), HARNESS),
    Pin("P0h", P0H_SCOPE,
        p0h_timeouts_leave_nothing, (Mutant("death_signal_reverted", _edits("P0h_death_signal_reverted")),
                                     Mutant("scratch_kept", _edits("P0h_scratch_kept")),
                                     Mutant("leaked_not_counted", _edits("P0h_leaked_not_counted")),
                                     Mutant("subreaper_not_set", _edits("P0h_subreaper_not_set")),
                                     Mutant("sweep_skipped", _edits("P0h_sweep_skipped"))), HARNESS),
    Pin("P0i", "a same-length edit landing in the second a bytecode cache recorded takes effect in a copy",
        p0i_no_stale_bytecode, (Mutant("pycache_top_level_only", _edits("P0i_pycache_top_level_only")),
                                 Mutant("pycache_prefix_unset", _edits("P0i_pycache_prefix_unset"))), HARNESS),
    Pin("P0j", "host facts lacking load averages, cpuset, runner version or podman runtime are not a measurement",
        p0j_host_facts_complete, (Mutant("incomplete_facts_accepted", _edits("P0j_incomplete_facts_accepted")),),
        ("scripts/**",)),
    Pin("P0k", "a forecasts.jsonl resolution lacking id, ts, proposer or outcome, matching no forecast, or by its "
        "forecast's session, is rejected",
        p0k_forecast_ledger, (Mutant("proposer_check_dropped", _edits("P0k_proposer_check_dropped")),
                              Mutant("self_resolution_admitted", _edits("P0k_self_resolution_admitted"))), ALWAYS),
    Pin("P0l", "a verdict citing a pins run on another sha, or one not concluded success, is rejected",
        p0l_ci_claims, (Mutant("sha_comparison_skipped", _edits("P0l_sha_comparison_skipped")),
                        Mutant("obligation_registry_skipped", _edits("P0l_obligation_registry_skipped"))), ALWAYS),
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
                                Mutant("inert_exemption_admitted", _edits("P0m_inert_exemption_admitted"))), ALWAYS),
    Pin("P0n", "merged pull requests are ranked by the Builder's cumulative log-loss on their forecasts, largest first",
        p0n_surprise_ranking, (Mutant("ranking_reversed", _edits("P0n_ranking_reversed")),), HARNESS),
    Pin("P0o", "a proposer's record per class counts an overturned act as a failure, never a success",
        p0o_proposer_record, (Mutant("overturned_scored_success", _edits("P0o_overturned_scored_success")),), HARNESS),
    Pin("P0q", "a commit removing a line of a ledger, review, audit or REPORT.md is rejected; a merge of appends is not",
        p0q_append_only, (Mutant("ledger_rewrite_admitted", _edits("P0q_ledger_rewrite_admitted")),
                          Mutant("draws_not_append_only", _edits("P0q_draws_not_append_only"))), ALWAYS),
    Pin("P0r", "a forecast row a pull request adds after the head of its first pins run is late",
        p0r_claims_precede_scoring, (Mutant("late_forecast_admitted", _edits("P0r_late_forecast_admitted")),), ALWAYS),
    Pin("P0s", "typed forecasts are resolved by code from what the API shows; free ones never by the mechanism",
        p0s_outcomes_by_code, (Mutant("outcome_inverted", _edits("P0s_outcome_inverted")),
                               Mutant("free_resolved_by_mechanism", _edits("P0s_free_resolved_by_mechanism")),
                               Mutant("branch_most_recent_pr", _edits("P0s_branch_most_recent_pr"))), HARNESS),
    Pin("P0t", "every item that reached Guy is counted once, with its latency, answered or not",
        p0t_price, (Mutant("latency_dropped", _edits("P0t_latency_dropped")),
                    Mutant("guy_items_undercounted", _edits("P0t_guy_items_undercounted")),
                    Mutant("wish_from_instruction", _edits("P0t_wish_from_instruction")),
                    Mutant("first_entrant_only", _edits("P0t_first_entrant_only")),
                    Mutant("costless_session_dropped", _edits("P0t_costless_session_dropped")),
                    Mutant("cost_pooled", _edits("P0t_cost_pooled")),
                    Mutant("first_result_charged", _edits("P0t_first_result_charged")),
                    Mutant("result_per_session", _edits("P0t_result_per_session"))), HARNESS),
    Pin("P0u", "a procedure's model is drawn by EXP3 over its entrants, weighted by the recorded draw probability",
        p0u_election, (Mutant("argmin_election", _edits("P0u_argmin_election")),
                       Mutant("hedge_election", _edits("P0u_hedge_election")),
                       Mutant("unweighted_estimate", _edits("P0u_unweighted_estimate")),
                       Mutant("draw_not_published", _edits("P0u_draw_not_published")),
                       Mutant("draw_push_forced", _edits("P0u_draw_push_forced")),
                       Mutant("entrants_from_head", _edits("P0u_entrants_from_head")),
                       Mutant("entrants_beyond_second_ignored", _edits("P0u_entrants_beyond_second_ignored"))), HARNESS),
    Pin("P0v", "a needs-review label applied by the reviewer account starts a review; a review session's awaits-guy does not",
        p0v_review_trigger, (Mutant("reviewer_label_excluded", _edits("P0v_reviewer_label_excluded")),),
        (".github/workflows/review.yml",)),
    Pin("P0w", "a pins run since a green head runs every pin witnessing a changed path, and records the rest skipped",
        p0w_witnessed_paths, (Mutant("witness_ignored", _edits("P0w_witness_ignored")),
                              Mutant("harness_change_skips", _edits("P0w_harness_change_skips")),
                              Mutant("skip_counted_ok", _edits("P0w_skip_counted_ok")),
                              Mutant("non_ancestor_base", _edits("P0w_non_ancestor_base"))), HARNESS),
    Pin("P0x", "an instruction signed after instruction #70 merged declares the price quantity it moves, or that it only records",
        p0x_price_declared, (Mutant("price_line_dropped", _edits("P0x_price_line_dropped")),
                             Mutant("none_on_workflow_admitted", _edits("P0x_none_on_workflow_admitted")),
                             Mutant("scoped_by_number", _edits("P0x_scoped_by_number"))), ALWAYS),
    Pin("P0y", "a commit whose Proposer or Instruction trailers git does not parse is refused, and its push with it",
        p0y_trailers_parse, (Mutant("split_trailer_block_admitted", _edits("P0y_split_trailer_block_admitted")),
                             Mutant("hook_unconditioned", _edits("P0y_hook_unconditioned"))), ALWAYS),
    Pin("P0z", "a failed pins run routes to an issue naming its pull request, as a failed build or review does",
        p0z_red_pins_routes, (Mutant("pins_failure_unrouted", _edits("P0z_pins_failure_unrouted")),),
        (".github/workflows/failed.yml",)),
    Pin("P0aa", "a master Builder skips an item an open pull request holds and takes the next",
        p0aa_held_item_skipped, (Mutant("held_item_retaken", _edits("P0aa_held_item_retaken")),), HARNESS),
    Pin("P0ab", "a session log that edits .github/ or harness/ through Bash, or ends on master opening nothing, fails",
        p0ab_session_logs, (Mutant("shell_edit_admitted", _edits("P0ab_shell_edit_admitted")),
                            Mutant("silent_master_stop_admitted", _edits("P0ab_silent_master_stop_admitted"))),
        HARNESS),
    Pin("P0ac", "a wish is drafted as a brief amendment unless the draft says in one line why it cannot wait",
        p0ac_draft_form, (Mutant("instruction_without_because_admitted",
                                 _edits("P0ac_instruction_without_because_admitted")),
                          Mutant("both_forms_admitted", _edits("P0ac_both_forms_admitted"))), ALWAYS),
    Pin("P0ad", "the chooser's forecast is committed before the STATUS line that acts on it, and the line lists every candidate",
        p0ad_chooser_sealed, (Mutant("seal_after_act", _edits("P0ad_seal_after_act")),
                              Mutant("seal_same_commit_admitted", _edits("P0ad_seal_same_commit_admitted")),
                              Mutant("candidate_omitted_admitted", _edits("P0ad_candidate_omitted_admitted")),
                              Mutant("deleted_status_read", _edits("P0ad_deleted_status_read"))),
        ALWAYS),
    Pin("P0ae", "Guy's pick is resolved by the labels he applies; silence counts only after a declared exposure, else void",
        p0ae_exposure_and_labels, (Mutant("exposure_inferred", _edits("P0ae_exposure_inferred")),
                                   Mutant("void_scored", _edits("P0ae_void_scored")),
                                   Mutant("void_not_counted", _edits("P0ae_void_not_counted")),
                                   Mutant("later_label_ignored", _edits("P0ae_later_label_ignored")),
                                   Mutant("label_by_anyone", _edits("P0ae_label_by_anyone"))), HARNESS),
    Pin("P0af", "the chooser elects by Fixed Share with the derived alpha; fixed-order is an entrant and the default choice",
        p0af_fixed_share, (Mutant("alpha_zero", _edits("P0af_alpha_zero")),
                           Mutant("fixed_order_dropped", _edits("P0af_fixed_order_dropped")),
                           Mutant("fixed_order_not_required", _edits("P0af_fixed_order_not_required")),
                           Mutant("silence_is_an_act", _edits("P0af_silence_is_an_act"))), HARNESS),
    Pin("P0ag", "the switchback's regimes equal the schedule recomputed from the committed seed, which precedes the first choice",
        p0ag_switchback, (Mutant("regime_after_seed", _edits("P0ag_regime_after_seed")),
                          Mutant("seed_after_act_admitted", _edits("P0ag_seed_after_act_admitted"))), ALWAYS),
    Pin("P0ah", "the chooser files not_overturned under the exposure regime and merged for the item it acts on",
        p0ah_chooser_files_act, (Mutant("kept_not_filed", _edits("P0ah_kept_not_filed")),
                                 Mutant("merged_not_filed", _edits("P0ah_merged_not_filed")),
                                 Mutant("kept_without_exposure", _edits("P0ah_kept_without_exposure")),
                                 Mutant("item_always_pr", _edits("P0ah_item_always_pr"))), HARNESS),
    Pin("P0ai", "a boundary brief's k probes are drawn by the ledger head from the exposed-and-silent acts, and priced",
        p0ai_probes, (Mutant("probe_from_unkept", _edits("P0ai_probe_from_unkept")),
                      Mutant("probe_unseeded", _edits("P0ai_probe_unseeded")),
                      Mutant("probe_needs_exposure", _edits("P0ai_probe_needs_exposure")),
                      Mutant("probe_not_priced", _edits("P0ai_probe_not_priced"))),
        HARNESS + ("docs/briefs/brief-2-nethack.md",)),
    Pin("P0aj", "an awaits-guy label starts a Builder on master; blocked still builds on the PR; needs-review starts none",
        p0aj_awaits_guy_builds_master, (Mutant("awaits_guy_clause_removed", _edits("P0aj_awaits_guy_clause_removed")),),
        (".github/workflows/build.yml",)),
    Pin("P0ak", "a session's first act is its declaration; its duration forecast resolves from the run; the price counts overruns and limits",
        p0ak_session_declared, (Mutant("undeclared_session_admitted", _edits("P0ak_undeclared_session_admitted")),
                                Mutant("duration_misresolved", _edits("P0ak_duration_misresolved")),
                                Mutant("cancelled_scored", _edits("P0ak_cancelled_scored")),
                                Mutant("over_bound_uncounted", _edits("P0ak_over_bound_uncounted")),
                                Mutant("limit_uncounted", _edits("P0ak_limit_uncounted"))),
        HARNESS + (".github/workflows/build.yml", ".github/workflows/review.yml", ".claude/commands/**")),
    Pin("P0al", "a forecast on a draft resolves as signed-as-drafted, signed-after-edit or declined, and is counted so",
        p0al_draft_outcomes, (Mutant("after_edit_as_drafted", _edits("P0al_after_edit_as_drafted")),
                              Mutant("other_editor_counted", _edits("P0al_other_editor_counted")),
                              Mutant("unreadable_edits_resolved", _edits("P0al_unreadable_edits_resolved")),
                              Mutant("detail_uncounted", _edits("P0al_detail_uncounted"))), HARNESS),
    Pin("P0am", "a needs-draft-check label on an issue starts a draft check; a draft label does not",
        p0am_draft_check_trigger, (Mutant("draft_check_clause_removed", _edits("P0am_draft_check_clause_removed")),),
        (".github/workflows/review.yml", ".claude/commands/review.md", ".claude/commands/vizier.md")),
    Pin("P0an", "a session on a pull-request branch adds no forecast row; one ending with no STATUS and no stop comment fails",
        p0an_session_routed, (Mutant("pr_branch_forecast_admitted", _edits("P0an_pr_branch_forecast_admitted")),
                              Mutant("silent_stop_admitted", _edits("P0an_silent_stop_admitted"))),
        HARNESS + (".claude/commands/**",)),
    Pin("P0aq", "a red pins run or a conflicted pull request is labelled blocked for three rounds, then filed to Guy",
        p0aq_red_returns_to_builder, (Mutant("label_branch_removed", _edits("P0aq_label_branch_removed")),
                                      Mutant("round_cap_removed", _edits("P0aq_round_cap_removed")),
                                      Mutant("conflict_as_clean", _edits("P0aq_conflict_as_clean"))),
        HARNESS + (".github/workflows/failed.yml",)),
    Pin("P0ar", "two pull requests, each writing its own forecast, STATUS and proposer row, merge without conflict in "
                "either order and are read together",
        p0ar_per_pr_files, (Mutant("forecasts_shared", _edits("P0ar_forecasts_shared")),
                            Mutant("status_shared", _edits("P0ar_status_shared")),
                            Mutant("registry_frozen_only", _edits("P0ar_registry_frozen_only")),
                            Mutant("status_by_date", _edits("P0ar_status_by_date")),
                            Mutant("duplicate_overrides", _edits("P0ar_duplicate_overrides"))),
        HARNESS + (".claude/commands/**", "reports/**")),
    Pin("P0aw", "a workflow job that sets permissions and checks out the repository grants contents access",
        p0aw_checkout_granted, (Mutant("checkout_without_contents", _edits("P0aw_checkout_without_contents")),),
        HARNESS + (".github/workflows/**",)),
    Pin("P0ax", "master's harness judges every pull request: the pins-master workflow restores it over the head's, and "
                "a deleted pin fails",
        p0ax_judge_from_master, (Mutant("accused_judges_itself", _edits("P0ax_accused_judges_itself")),
                                 Mutant("head_files_kept", _edits("P0ax_head_files_kept"))),
        HARNESS + (".github/workflows/pins-master.yml", ".github/workflows/pins.yml")),
    Pin("P0ay", "a pin or mutant absent at the head is refused unless a signed instruction a head commit cites names it "
                "removed",
        p0ay_pins_monotone, (Mutant("monotone_ignores_instruction", _edits("P0ay_monotone_ignores_instruction")),
                             Mutant("removal_unsigned_admitted", _edits("P0ay_removal_unsigned_admitted")),
                             Mutant("registry_read_as_text", _edits("P0ay_registry_read_as_text"))), HARNESS),
    Pin("P0az", "the workflow that runs a pull request's code under master's harness grants no write scope and no secret",
        p0az_pins_master_unprivileged, (Mutant("pins_master_privileged", _edits("P0az_pins_master_privileged")),
                                        Mutant("pins_master_secret", _edits("P0az_pins_master_secret"))),
        HARNESS + (".github/workflows/pins-master.yml",)),
    Pin("P1","evaluation seeds come from a CSPRNG, are recorded privately, and are never reissued or training seeds",
        p1_seed_issuance, (Mutant("seed_reissued", _edits("P1_seed_reissued")),
                           Mutant("reuse_check_skipped", _edits("P1_reuse_check_skipped")),
                           Mutant("domain_check_skipped", _edits("P1_domain_check_skipped")),
                           Mutant("training_undomained", _edits("P1_training_undomained")),
                           Mutant("csprng_replaced", _edits("P1_csprng_replaced"))), JUDGE_SIDE),
    Pin("P2", "a candidate container cannot read judge paths or reach the network; root read-only; config limits",
        p2_peek, (Mutant("network_enabled", _edits("P2_network_enabled")),
                  Mutant("judge_mounted", _edits("P2_judge_mounted")),
                  Mutant("rootfs_writable", _edits("P2_rootfs_writable")),
                  Mutant("memory_limit_dropped", _edits("P2_memory_limit_dropped"))), JUDGE_SIDE),
    Pin("P3", "every requested episode is recorded with its termination code, failures included",
        p3_survivorship, (Mutant("failures_dropped", _edits("P3_failures_dropped")),
                          Mutant("played_at_end", _edits("P3_played_at_end"))), JUDGE_SIDE),
    Pin("P4", "an episode's CPU and peak memory are measured from its container's cgroup, never self-reported",
        p4_measured_compute, (Mutant("self_reported", _edits("P4_self_reported")),
                              Mutant("client_rusage", _edits("P4_client_rusage")),
                              Mutant("not_differenced", _edits("P4_not_differenced")),
                              Mutant("peak_from_current", _edits("P4_peak_from_current"))), JUDGE_SIDE),
    Pin("P5", "a clairvoyant candidate gains nothing over the predictive floor: no observation is sent early",
        p5_commitment_order, (Mutant("next_sent_early", _edits("P5_next_sent_early")),), JUDGE_SIDE),
    Pin("P14", "the random incumbent's image plays uniformly over legal actions and records exactly the predictive floor",
        p14_random_incumbent, (Mutant("first_legal_action", _edits("P14_first_legal_action")),
                               Mutant("floor_unsmoothed", _edits("P14_floor_unsmoothed")),
                               Mutant("seen_not_reset", _edits("P14_seen_not_reset"))), JUDGE_SIDE),
    Pin("P15", "time-to-learn finds the episodes per arm a known shift needs, counts both arms, and states the verdict",
        p15_time_to_learn, (Mutant("abs_difference", _edits("P15_abs_difference")),
                            Mutant("shift_dropped", _edits("P15_shift_dropped")),
                            Mutant("one_arm", _edits("P15_one_arm")),
                            Mutant("budget_one_arm", _edits("P15_budget_one_arm"))), JUDGE_SIDE),
    Pin("P7", "zero mass on a realised outcome is recorded +inf, never clipped; missing is never imputed",
        p7_infinite_loss, (Mutant("clipped", _edits("P7_clipped")),
                           Mutant("missing_imputed", _edits("P7_missing_imputed")),
                           Mutant("sum_unchecked", _edits("P7_sum_unchecked"))), JUDGE_SIDE),
    Pin("P13", "every scored step, +inf included, enters each support value's reliability row; entropy is never imputed",
        p13_calibration, (Mutant("infinite_dropped", _edits("P13_infinite_dropped")),
                          Mutant("realised_row_only", _edits("P13_realised_row_only")),
                          Mutant("entropy_missing_imputed", _edits("P13_entropy_missing_imputed"))), JUDGE_SIDE),
    Pin("P9", "a ledger record dropped, altered or rechained, a head forged, or the tail truncated, fails the judge's "
              "verification",
        p9_ledger_tamper, (Mutant("record_dropped", _edits("P9_record_dropped")),
                           Mutant("utility_altered", _edits("P9_utility_altered")),
                           Mutant("chain_update_skipped", _edits("P9_chain_update_skipped")),
                           Mutant("opened_for_rewrite", _edits("P9_opened_for_rewrite")),
                           Mutant("genesis_empty", _edits("P9_genesis_empty")),
                           Mutant("signature_unchecked", _edits("P9_signature_unchecked")),
                           Mutant("independent_heads", _edits("P9_independent_heads"))), JUDGE_SIDE),
    Pin("P16", "a candidate's proposer comes from the judge-issued credential that registered it, or it is refused",
        p16_proposer_from_credential, (Mutant("unattributed_admitted", _edits("P16_unattributed_admitted")),
                                       Mutant("any_credential", _edits("P16_any_credential")),
                                       Mutant("registration_taken_over", _edits("P16_registration_taken_over"))), JUDGE_SIDE),
    Pin("P17", "evaluate() stamps every record with its registered proposer, issues no seed unregistered, is idempotent",
        p17_evaluate, (Mutant("fixed_proposer", _edits("P17_fixed_proposer")),
                       Mutant("seeds_before_proposer", _edits("P17_seeds_before_proposer")),
                       Mutant("idempotency_dropped", _edits("P17_idempotency_dropped")),
                       Mutant("conflict_unchecked", _edits("P17_conflict_unchecked")),
                       Mutant("hash_partial", _edits("P17_hash_partial"))), JUDGE_SIDE),
    Pin("P18", "the pilot records every episode, stops at the cap, and reports the records' proposer and throughput",
        p18_pilot, (Mutant("cap_ignored", _edits("P18_cap_ignored")),
                    Mutant("failures_dropped", _edits("P18_failures_dropped")),
                    Mutant("throughput_from_episodes", _edits("P18_throughput_from_episodes")),
                    Mutant("proposer_from_config", _edits("P18_proposer_from_config")),
                    Mutant("mixed_proposers_admitted", _edits("P18_mixed_proposers_admitted")),
                    Mutant("infinite_pooled_finite", _edits("P18_infinite_pooled_finite")),
                    Mutant("short_request_admitted", _edits("P18_short_request_admitted"))), JUDGE_SIDE),
    Pin("P12", "every episode's compute is priced by the committed rule; peak memory's scope is stated and followed",
        p12_compute_price, (Mutant("peak_differenced", _edits("P12_peak_differenced")),
                            Mutant("unmeasured_free", _edits("P12_unmeasured_free"))), JUDGE_SIDE),
    Pin("P19", "a World is bound by its directory alone, a manifest beside a binding; no manifest, no binding",
        p19_world_discovery, (Mutant("world_table_hardcoded", _edits("P19_world_table_hardcoded")),), JUDGE_SIDE),
    Pin("P20", "a World is priced from its own manifest; evaluate() refuses one that commits no price",
        p20_world_price, (Mutant("crafter_price_fallback", _edits("P20_crafter_price_fallback")),), JUDGE_SIDE),
    Pin("P22", "replay returns a request's records only if they match its signed head, else refuses ledger_unverified",
        p22_replay_verified, (Mutant("replay_unchecked", _edits("P22_replay_unchecked")),), JUDGE_SIDE),
    Pin("P23", "an interrupted request's played episodes and spent seeds are sealed into the ledger by the next "
               "request of its World, charged to the image and proposer they were issued to",
        p23_interrupted_recorded, (Mutant("partial_dropped", _edits("P23_partial_dropped")),
                                   Mutant("interrupted_unsealed", _edits("P23_interrupted_unsealed")),
                                   Mutant("closing_unattributed", _edits("P23_closing_unattributed"))), JUDGE_SIDE),
    Pin("P24", "the judge's evaluate refuses an episode count that is not a positive ASCII integer, with the code "
               "bad_episodes and no traceback",
        p24_episode_guard, (Mutant("isdigit_guard", _edits("P24_isdigit_guard")),), JUDGE_SIDE),
    Pin("P10", "a candidate container ignoring SIGTERM is killed and removed on timeout; the runtime lists nothing",
        p10_container_teardown, (Mutant("removal_skipped", _edits("P10_removal_skipped")),), JUDGE_SIDE),
    Pin("P6", "no manifest vocabulary token appears in an interface schema file",
        p6_schema_purity, (Mutant("crafter_field_in_schema", _edits("P6_crafter_field_in_schema")),), JUDGE_SIDE),
    Pin("P11", "the same seed and actions give an identical Crafter trajectory hash; emitted observations conform",
        p11_crafter_determinism, (Mutant("set_order_restored", _edits("P11_set_order_restored")),
                                  Mutant("seed_ignored", _edits("P11_seed_ignored")),
                                  Mutant("hash_constant", _edits("P11_hash_constant")),
                                  Mutant("field_dropped", _edits("P11_field_dropped")),
                                  Mutant("chunks_replaced_after_worldgen", _edits("P11_chunks_replaced_after_worldgen")),
                                  Mutant("golden_hash_altered", _edits("P11_golden_hash_altered"))), JUDGE_SIDE),
]
