"""The harness's own pins (L0, brief 0 A2). Each kills its named mutant, an anchored edit to the harness,
and each kill is causal: the mutant run fails and its unedited twin passes."""

from __future__ import annotations

import os
import shutil
import signal
from pathlib import Path

from harness import config, proc, scan, tree
from harness.fixtures import escapee, leaky
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


P0H_SCOPE = ("a timed-out child, and every descendant that either carries the parent-death signal or holds the run's "
             "scratch root, is dead or recorded LEAKED before the scratch root is deleted. Out of scope at L0: a "
             "descendant detached from both (new session, no death signal, not holding the scratch root), and the "
             "outermost orchestrator being SIGKILLed.")


def p0h_timeouts_leave_nothing() -> bool:
    """Witnessed scope: see P0H_SCOPE (brief 0 A3 item 3)."""
    cfg = config.load()
    n = run_nested("leaks", "fixture.leaks", "mutants", config=ROOT / "harness" / "fixtures" / "fast.toml")
    row = n.run("fixture/toy", "fixture/toy/leaks_and_hangs", "mutant")
    n.expect(row.get("observed") == "timeout" and row.get("verdict") == "INCONCLUSIVE",
             "leaking mutant: observed timeout, INCONCLUSIVE")
    n.expect(row.get("twin_observed") == "pass", "its twin passed")
    run_dir = Path(row.get("run_dir", "/nonexistent"))
    pid_file, copy_file = run_dir / leaky.PID_FILE, run_dir / leaky.COPY_FILE
    n.expect(pid_file.is_file() and copy_file.is_file(), "the check recorded its grandchild PID and nested copy")
    pid = int(pid_file.read_text()) if pid_file.is_file() else None
    nested_copy = Path(copy_file.read_text()) if copy_file.is_file() else None
    scratch = Path(row.get("scratch", "/nonexistent"))

    gone = pid is not None and proc.wait_until(lambda: not proc.alive(pid, leaky.MARKER), cfg.reap_grace_s,
                                                cfg.poll_step_s)
    n.expect(gone, f"grandchild {pid} (ignores SIGTERM) no longer alive")
    n.expect(not proc.holders(scratch), "no live process holds the run's scratch root")
    n.expect(row.get("scratch_quiescent") is True, "parent saw the scratch root quiescent before deleting it")
    n.expect(nested_copy is not None and not nested_copy.exists(), f"nested copy {nested_copy} removed")
    n.expect(row.get("scratch_removed") is True and not scratch.exists(), f"scratch root {scratch} removed")

    # Leave the machine clean whatever the verdict.
    if pid is not None and proc.alive(pid, leaky.MARKER):
        os.kill(pid, signal.SIGKILL)
    shutil.rmtree(scratch, ignore_errors=True)
    return n.ok and p0h_escapee()


def p0h_escapee() -> bool:
    """A descendant that escapes both kill paths but holds the scratch root makes the run LEAKED."""
    fast = config.load(escapee.FAST)
    e = run_nested("escapee", "fixture.escapee", "clean", config=escapee.FAST)
    row = e.run("fixture/escapee")
    e.expect(row.get("observed") == "timeout", "escapee: child observed timeout")
    e.expect(row.get("scratch_quiescent") is False, "escapee: scratch_quiescent false")
    e.expect(row.get("verdict") == "LEAKED", "escapee: verdict LEAKED")
    e.expect(e.summary.get("leaked") == 1, "escapee: summary leaked = 1")
    e.expect(e.exit_code not in (0, None) and e.exit_code == e.summary.get("exit_code"),
             "escapee: exit non-zero and equal to the summary's")
    pid_file = Path(row.get("run_dir", "/nonexistent")) / escapee.PID_FILE
    pid = int(pid_file.read_text()) if pid_file.is_file() else None
    e.expect(pid is not None, f"escapee: grandchild PID recorded ({pid})")
    # The grandchild exits on its own after escape_hold_s; wait for it so this pin leaves nothing behind.
    gone = pid is not None and proc.wait_until(lambda: not proc.alive(pid, escapee.MARKER),
                                                fast.escape_hold_s + fast.poll_step_s, fast.poll_step_s)
    e.expect(gone, "escapee: grandchild gone by the end (exited on its own)")
    scratch = Path(row.get("scratch", "/nonexistent"))
    e.expect(row.get("scratch_removed") is True and not scratch.exists(), f"escapee: scratch root {scratch} removed")
    if pid is not None and proc.alive(pid, escapee.MARKER):
        os.kill(pid, signal.SIGKILL)
    shutil.rmtree(scratch, ignore_errors=True)
    return e.ok


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
                                     Mutant("leaked_not_counted", _edits("P0h_leaked_not_counted")))),
]
