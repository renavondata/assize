"""The harness's own pins (L0). Each kills its named, seeded mutant."""

from __future__ import annotations

from harness.nested import run_nested
from harness.pin import ROOT, Mutant, Pin


def _all(*runs) -> bool:
    return all(r.ok for r in runs)


def p0_self_kill() -> bool:
    """With every check forced to succeed, the suite must report the survivors and exit non-zero."""
    ctrl = run_nested("control", "fixture.basic", "mutants")
    ctrl.expect(ctrl.exit_code == 0, "control exits 0")
    runs = ctrl.of("run")
    ctrl.expect(len(runs) == 2 and ctrl.summary.get("mutants_total") == 2, "control: 2 mutant rows in denominator")
    ctrl.expect({r.get("selector") for r in runs} == {"env", "patch"}, "control covers env and patch selectors")
    ctrl.expect(all(r.get("verdict") == "killed" and r.get("observed") == "fail" for r in runs),
                "control: every mutant killed")
    patch = ctrl.run("fixture/toy", "fixture/toy/off_by_one_patch")
    ctrl.expect(patch.get("verdict") == "killed" and patch.get("patch_copy_discarded") is True,
                "patch mutant killed and its repository copy discarded")

    inj = run_nested("checks_always_pass", "fixture.basic", "mutants", "P0/checks_always_pass")
    inj.expect(inj.exit_code != 0, "seeded all-pass mutant: suite exits non-zero")
    runs = inj.of("run")
    inj.expect(len(runs) == 2 and inj.summary.get("survived") == 2 == inj.summary.get("mutants_total"),
               "seeded all-pass mutant: 2/2 mutants reported SURVIVED")
    inj.expect(all(r.get("verdict") == "SURVIVED" and r.get("observed") == "pass" for r in runs),
               "every row verdict SURVIVED, observed pass")
    return _all(ctrl, inj)


def p0b_isolation() -> bool:
    """A mutant flag leaking into the clean run is detected."""
    ctrl = run_nested("no_leak", "fixture.basic", "clean")
    ctrl.expect(ctrl.exit_code == 0 and ctrl.run("fixture/toy").get("verdict") == "ok",
                "control: clean run with no flag passes")
    leak = run_nested("leak", "fixture.basic", "clean", "P0b/leak_probe")
    row = leak.run("fixture/toy")
    leak.expect(row.get("observed") == "leak" and row.get("verdict") == "FAILED",
                "leaked flag: clean row observed leak, verdict FAILED")
    leak.expect(leak.exit_code != 0 and leak.summary.get("clean_failed") == 1, "leaked flag: suite exits non-zero")
    return _all(ctrl, leak)


def p0c_clean_failure() -> bool:
    """A failing clean check makes the suite fail and is recorded."""
    n = run_nested("clean", "fixture.broken", "clean")
    row = n.run("fixture/broken")
    n.expect(row.get("observed") == "fail" and row.get("verdict") == "FAILED", "fixture/broken recorded FAILED")
    n.expect(n.run("fixture/toy").get("verdict") == "ok", "fixture/toy recorded ok")
    n.expect(n.summary.get("clean_total") == 2 and n.summary.get("clean_failed") == 1, "denominator 1/2 failed")
    n.expect(n.exit_code != 0, "suite exits non-zero")
    return n.ok


def p0d_inconclusive() -> bool:
    """Raising and hanging mutants are recorded INCONCLUSIVE, counted, and fail the suite."""
    cfg = ROOT / "harness" / "fixtures" / "fast.toml"
    n = run_nested("inconclusive", "fixture.inconclusive", "mutants", config=cfg)
    raises = n.run("fixture/toy", "fixture/toy/raises")
    hangs = n.run("fixture/toy", "fixture/toy/hangs")
    n.expect(raises.get("observed") == "error" and raises.get("verdict") == "INCONCLUSIVE",
             "raises: observed error, INCONCLUSIVE")
    n.expect(hangs.get("observed") == "timeout" and hangs.get("verdict") == "INCONCLUSIVE",
             "hangs: observed timeout, INCONCLUSIVE")
    n.expect(n.registry.get("config") == "harness/fixtures/fast.toml", "timeout taken from committed config")
    n.expect(hangs.get("duration_s", 0) >= n.registry.get("child_timeout_s", float("inf")),
             "hang ran at least the configured timeout")
    n.expect(n.summary.get("mutants_total") == 3 and n.summary.get("inconclusive") == 2
             and n.summary.get("killed") == 1, "denominator: 3 mutants, 2 inconclusive, 1 killed")
    n.expect(n.exit_code != 0, "suite exits non-zero")
    return n.ok


def p0e_registry_validation() -> bool:
    """Registries with a mutant-less pin or duplicated names are refused."""
    runs = []
    for registry, code in (("fixture.no_mutants", "no_mutants"),
                           ("fixture.dup_pin", "duplicate_pin"),
                           ("fixture.dup_mutant", "duplicate_mutant")):
        n = run_nested(registry.split(".", 1)[1], registry, "all")
        n.expect(n.registry.get("status") == "refused" and n.registry.get("code") == code,
                 f"{registry} refused with {code}")
        n.expect(not n.of("run"), "no pin was run")
        n.expect(n.exit_code != 0, "suite exits non-zero")
        runs.append(n)
    ctrl = run_nested("accepted", "fixture.basic", "clean")
    ctrl.expect(ctrl.registry.get("status") == "accepted", "control: fixture.basic accepted")
    return _all(*runs, ctrl)


PINS = [
    Pin("P0", "the harness reports surviving mutants and exits non-zero when every check returns success",
        p0_self_kill, (Mutant("survivors_ignored"),)),
    Pin("P0b", "a mutant flag leaking into the clean run is detected",
        p0b_isolation, (Mutant("guard_off"),)),
    Pin("P0c", "a failing clean check is recorded and fails the suite",
        p0c_clean_failure, (Mutant("clean_failures_ignored"),)),
    Pin("P0d", "errors and timeouts are recorded INCONCLUSIVE, counted in the denominator, and fail the suite",
        p0d_inconclusive, (Mutant("inconclusive_dropped"),)),
    Pin("P0e", "a registry with a mutant-less pin or a duplicated pin or mutant name is refused",
        p0e_registry_validation, (Mutant("validation_off"),)),
]
