"""Orchestrator (`run`) and child check runner (`check`).

Every (pin, mutant) runs in its own child process. The clean build must pass;
each mutant must make its pin fail. Results are exported as JSONL rows; the
transcript of each child is kept beside them. Nothing is dropped: errors and
timeouts are recorded as INCONCLUSIVE and counted in the denominator.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path

from harness import config as config_mod
from harness import mutants, registries
from harness.pin import ROOT, Mutant, Pin, RegistryError

EXIT_PASS, EXIT_FAIL, EXIT_ERROR, EXIT_LEAK = 0, 1, 2, 3
EXIT_REFUSED = 4
OBSERVED = {EXIT_PASS: "pass", EXIT_FAIL: "fail", EXIT_LEAK: "leak"}

# Never copied into a patch mutant's temporary repository.
COPY_IGNORE = {".git", ".venv", "out", "reports", "__pycache__", ".pytest_cache"}


# --------------------------------------------------------------------- child


def check(registry: str, pin_name: str, mutant_name: str | None, clean: bool) -> int:
    flags = mutants.active_set()
    if clean and flags and not mutants.active("P0b/guard_off"):
        print(f"MUTANT LEAK: {mutants.ENV}={','.join(sorted(flags))} is set during a clean run")
        return EXIT_LEAK
    try:
        pins = {p.name: p for p in registries.load(registry)}
        pin = pins[pin_name]
    except Exception:
        traceback.print_exc()
        return EXIT_ERROR
    print(f"pin:       {pin.name}")
    print(f"protects:  {pin.protects}")
    print(f"mode:      {'clean' if clean else 'mutant ' + str(mutant_name)}")
    print(f"flags:     {','.join(sorted(flags)) or '(none)'}")
    print(f"cwd:       {os.getcwd()}")
    sys.stdout.flush()
    if mutants.active("P0/checks_always_pass"):
        print("result:    PASS (seeded mutant P0/checks_always_pass: check not consulted)")
        return EXIT_PASS
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


def _ignore(_dir: str, names: list[str]) -> set[str]:
    return {n for n in names if n in COPY_IGNORE}


def _spawn(cmd: list[str], env: dict[str, str], cwd: Path, timeout: float, log) -> tuple[str, int | None]:
    proc = subprocess.Popen(
        cmd, env=env, cwd=cwd, stdout=log, stderr=subprocess.STDOUT, start_new_session=True
    )
    try:
        code = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait()
        return "timeout", None
    return OBSERVED.get(code, "error"), code


def _run_one(registry: str, pin: Pin, mutant: Mutant | None, out: Path, cfg) -> dict:
    run_dir = out / "runs" / _slug(pin.name) / ("clean" if mutant is None else mutant.name)
    shutil.rmtree(run_dir, ignore_errors=True)
    run_dir.mkdir(parents=True)
    transcript = run_dir / "transcript.log"
    env = dict(os.environ)
    env["ASSIZE_RUN_DIR"] = str(run_dir.resolve())
    cmd = [sys.executable, "-m", "harness", "check", "--registry", registry, "--pin", pin.name]
    cmd += ["--clean"] if mutant is None else ["--mutant", mutant.name]
    row = {
        "kind": "run",
        "registry": registry,
        "pin": pin.name,
        "mutant": None if mutant is None else pin.flag(mutant),
        "selector": None if mutant is None else mutant.selector,
        "expected": "pass" if mutant is None else "fail",
    }
    t0 = time.monotonic()
    with transcript.open("w") as log:
        if mutant is None or mutant.selector == "env":
            if mutant is not None:
                env = mutants.with_mutants(env, pin.flag(mutant))
            observed, code = _spawn(cmd, env, ROOT, cfg.child_timeout_s, log)
        else:
            patch = ROOT / mutant.patch
            row["patch"] = mutant.patch
            row["patch_sha256"] = hashlib.sha256(patch.read_bytes()).hexdigest()
            with tempfile.TemporaryDirectory(prefix="assize-patch-") as tmp:
                copy = Path(tmp) / "repo"
                shutil.copytree(ROOT, copy, ignore=_ignore)
                log.write(f"patch copy: {copy}\n$ git apply --verbose {patch}\n")
                log.flush()
                applied = subprocess.run(
                    ["git", "apply", "--verbose", str(patch)],
                    cwd=copy, stdout=log, stderr=subprocess.STDOUT,
                )
                if applied.returncode != 0:
                    log.write(f"git apply failed with exit {applied.returncode}\n")
                    observed, code = "error", None
                else:
                    log.flush()
                    observed, code = _spawn(cmd, env, copy, cfg.child_timeout_s, log)
            row["patch_copy_discarded"] = not copy.exists()
    row["observed"] = observed
    row["exit_code"] = code
    row["duration_s"] = round(time.monotonic() - t0, 3)
    row["transcript"] = os.path.relpath(transcript, Path.cwd())
    if mutant is None:
        verdict = "ok" if observed == "pass" else "FAILED"
        if verdict == "FAILED" and mutants.active("P0c/clean_failures_ignored"):
            verdict = "ok"
    elif observed == "fail":
        verdict = "killed"
    elif observed == "pass":
        verdict = "killed" if mutants.active("P0/survivors_ignored") else "SURVIVED"
    else:
        verdict = "INCONCLUSIVE"
    row["verdict"] = verdict
    return row


def run(registry: str, phase: str, out: Path, config_path: Path | None) -> int:
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
            "inherited_flags": sorted(mutants.active_set()),
            "python": sys.version.split()[0],
        }
        try:
            pins = registries.load(registry)
        except RegistryError as e:
            emit(head | {"status": "refused", "code": e.code, "detail": e.detail})
            emit({"kind": "summary", "registry": registry, "exit_code": EXIT_REFUSED})
            print(f"REGISTRY REFUSED: {registry}: {e}")
            return EXIT_REFUSED
        emit(head | {"status": "accepted", "pins": [p.name for p in pins],
                     "mutants": [p.flag(m) for p in pins for m in p.mutants]})
        print(f"registry {registry}: {len(pins)} pins, "
              f"{sum(len(p.mutants) for p in pins)} mutants; phase={phase}; "
              f"child_timeout_s={cfg.child_timeout_s} ({os.path.relpath(cfg.path, ROOT)})")

        jobs: list[tuple[Pin, Mutant | None]] = []
        if phase in ("all", "clean"):
            jobs += [(p, None) for p in pins]
        if phase in ("all", "mutants"):
            jobs += [(p, m) for p in pins for m in p.mutants]

        counts = dict(clean_total=0, clean_ok=0, clean_failed=0,
                      mutants_total=0, killed=0, survived=0, inconclusive=0)
        for pin, mutant in jobs:
            row = _run_one(registry, pin, mutant, out, cfg)
            v = row["verdict"]
            label = pin.name if mutant is None else pin.flag(mutant)
            stage = "clean " if mutant is None else "mutant"
            if v == "INCONCLUSIVE" and mutants.active("P0d/inconclusive_dropped"):
                print(f"[{stage}] {label}: (dropped)")
                continue
            emit(row)
            print(f"[{stage}] {label}: expected {row['expected']}, observed {row['observed']} "
                  f"-> {v} ({row['duration_s']}s) {row['transcript']}")
            if mutant is None:
                counts["clean_total"] += 1
                counts["clean_ok" if v == "ok" else "clean_failed"] += 1
                if v != "ok":
                    print(f"CLEAN FAILED: {label} (observed {row['observed']})")
            else:
                counts["mutants_total"] += 1
                counts[{"killed": "killed", "SURVIVED": "survived"}.get(v, "inconclusive")] += 1
                if v == "SURVIVED":
                    print(f"MUTANT SURVIVED: {label}")
                elif v == "INCONCLUSIVE":
                    print(f"MUTANT INCONCLUSIVE: {label} (observed {row['observed']})")

        bad = counts["clean_failed"] + counts["survived"] + counts["inconclusive"]
        code = 0 if bad == 0 else 1
        emit({"kind": "summary", "registry": registry, "phase": phase, **counts, "exit_code": code})
    print(f"clean: {counts['clean_ok']}/{counts['clean_total']} passed, "
          f"{counts['clean_failed']}/{counts['clean_total']} failed")
    print(f"mutants: {counts['killed']}/{counts['mutants_total']} killed, "
          f"{counts['survived']}/{counts['mutants_total']} survived, "
          f"{counts['inconclusive']}/{counts['mutants_total']} inconclusive")
    print(f"report: {os.path.relpath(rows_path, Path.cwd())}")
    print("PINS PASSED" if code == 0 else "PINS FAILED")
    return code
