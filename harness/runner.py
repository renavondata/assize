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
import shutil
import signal
import subprocess
import sys
import time
import traceback
from pathlib import Path

from harness import config as config_mod
from harness import context, edits, registries
from harness.pin import ROOT, Mutant, Pin, RegistryError
from harness.tree import disposable_copy

EXIT_PASS, EXIT_FAIL, EXIT_ERROR = 0, 1, 2
EXIT_REFUSED = 4
OBSERVED = {EXIT_PASS: "pass", EXIT_FAIL: "fail"}


# --------------------------------------------------------------------- child


def check(registry: str, pin_name: str, role: str, invocation_root: Path, run_dir: Path) -> int:
    context.invocation_root = invocation_root.resolve()
    context.run_dir = run_dir.resolve()
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


def _spawn(cmd: list[str], cwd: Path, timeout: float, log) -> tuple[str, int | None]:
    proc = subprocess.Popen(cmd, cwd=cwd, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    try:
        code = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait()
        return "timeout", None
    return OBSERVED.get(code, "error"), code


def _child(registry: str, pin: Pin, role: str, tree: Path, run_dir: Path, cfg, log) -> tuple[str, int | None]:
    cmd = [sys.executable, "-m", "harness", "check", "--registry", registry, "--pin", pin.name,
           "--role", role, "--invocation-root", str(ROOT), "--run-dir", str(run_dir.resolve())]
    log.flush()
    return _spawn(cmd, tree, cfg.child_timeout_s, log)


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
    }


def _run_clean(registry: str, pin: Pin, out: Path, cfg) -> dict:
    run_dir = _fresh_dir(out / "runs" / _slug(pin.name) / "clean")
    row = _row(registry, pin, None, "clean", run_dir) | {"tree": "invocation"}
    t0 = time.monotonic()
    with (run_dir / "transcript.log").open("w") as log:
        observed, code = _child(registry, pin, "clean", ROOT, run_dir, cfg, log)
    verdict = "ok" if observed == "pass" else "FAILED"
    return row | {"observed": observed, "exit_code": code,
                  "duration_s": round(time.monotonic() - t0, 3), "verdict": verdict}


def _run_in_copy(registry: str, pin: Pin, mutant: Mutant, role: str, out: Path, cfg) -> dict:
    """role 'mutant': copy plus the mutant's edits. role 'twin': identical fresh copy, no edits."""
    run_dir = _fresh_dir(out / "runs" / _slug(pin.name) / mutant.name / role)
    row = _row(registry, pin, mutant, role, run_dir) | {"edits": mutant.edits}
    mutant_edits = edits.load(mutant.edits)
    row["edits_sha256"] = hashlib.sha256((ROOT / mutant.edits).read_bytes()).hexdigest()
    t0 = time.monotonic()
    with (run_dir / "transcript.log").open("w") as log, disposable_copy(ROOT) as copy:
        row["tree"] = str(copy)
        log.write(f"copy of {ROOT}\n  at {copy}\n")
        if role == "mutant":
            try:
                edits.apply(copy, mutant_edits)
                log.write(f"applied {len(mutant_edits)} edit(s) from {mutant.edits}\n")
                observed, code = _child(registry, pin, role, copy, run_dir, cfg, log)
            except edits.Stale as e:
                log.write(f"STALE: {e}\n")
                row["stale_detail"] = str(e)
                observed, code = "stale", None
        else:
            log.write("twin: no edits applied\n")
            observed, code = _child(registry, pin, role, copy, run_dir, cfg, log)
    row["copy_discarded"] = not Path(row["tree"]).exists()
    return row | {"observed": observed, "exit_code": code, "duration_s": round(time.monotonic() - t0, 3)}


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


def _run_mutant(registry: str, pin: Pin, mutant: Mutant, out: Path, cfg) -> tuple[dict, dict]:
    mrow = _run_in_copy(registry, pin, mutant, "mutant", out, cfg)
    trow = _run_in_copy(registry, pin, mutant, "twin", out, cfg)
    trow["verdict"] = "ok" if trow["observed"] == "pass" else "FAILED"
    mrow["twin_observed"] = trow["observed"]
    mrow["verdict"] = _verdict(mrow["observed"], trow["observed"])
    return mrow, trow


TALLY = {"KILLED": "killed", "SURVIVED": "survived", "INCONCLUSIVE": "inconclusive",
         "STALE": "stale", "NON-CAUSAL": "non_causal"}


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
            "invocation_root": str(ROOT),
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
                     "mutants": [p.label(m) for p in pins for m in p.mutants]})
        print(f"registry {registry}: {len(pins)} pins, "
              f"{sum(len(p.mutants) for p in pins)} mutants; phase={phase}; "
              f"child_timeout_s={cfg.child_timeout_s} ({os.path.relpath(cfg.path, ROOT)})")

        counts = dict(clean_total=0, clean_ok=0, clean_failed=0,
                      mutants_total=0, killed=0, survived=0, inconclusive=0, stale=0, non_causal=0,
                      twins_total=0, twins_ok=0, twins_failed=0)

        if phase in ("all", "clean"):
            for pin in pins:
                row = _run_clean(registry, pin, out, cfg)
                emit(row)
                print(f"[clean ] {pin.name}: observed {row['observed']} -> {row['verdict']} "
                      f"({row['duration_s']}s) {row['transcript']}")
                counts["clean_total"] += 1
                counts["clean_ok" if row["verdict"] == "ok" else "clean_failed"] += 1
                if row["verdict"] != "ok":
                    print(f"CLEAN FAILED: {pin.name} (observed {row['observed']})")

        if phase in ("all", "mutants"):
            for pin, mutant in [(p, m) for p in pins for m in p.mutants]:
                mrow, trow = _run_mutant(registry, pin, mutant, out, cfg)
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

        bad = sum(counts[k] for k in ("clean_failed", "survived", "inconclusive", "stale", "non_causal"))
        code = 0 if bad == 0 else 1
        emit({"kind": "summary", "registry": registry, "phase": phase, **counts, "exit_code": code})
    n = counts["mutants_total"]
    print(f"clean: {counts['clean_ok']}/{counts['clean_total']} passed, "
          f"{counts['clean_failed']}/{counts['clean_total']} failed")
    print(f"mutants: {counts['killed']}/{n} killed, {counts['survived']}/{n} survived, "
          f"{counts['inconclusive']}/{n} inconclusive, {counts['stale']}/{n} stale, "
          f"{counts['non_causal']}/{n} non-causal")
    print(f"twins: {counts['twins_ok']}/{counts['twins_total']} passed")
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
        cmd = [sys.executable, "-m", "harness", "run", "--registry", registry, "--phase", phase,
               "--out", str(out.resolve())]
        if config_path is not None:
            cmd += ["--config", str(config_path.resolve())]
        return subprocess.run(cmd, cwd=copy).returncode
