# Claude Code brief 0 — L0 scaffold: pin harness and CI split

## Precondition
Guy has done all of the following:
- created the repository `assize`, private until L2 is sealed;
- committed `CLAUDE.md` and `docs/briefs/brief-1-judge-and-crafter.md` and `docs/briefs/brief-2-nethack.md`;
- protected `main`: pull request required, status checks required, no direct pushes;
- registered a self-hosted GitHub Actions runner on the measurement host, running as an unprivileged user, labelled `measure`.

Read `CLAUDE.md` first. It governs this session.

## Purpose
Build the floor every later layer stands on:
- a pin harness that proves each pin can fail;
- CI that runs the pins in the cloud and reserves measurement for the host.

This session writes no World, judge or agent code.

## Scope (single session)

### 1. Scaffold
- Create the empty directories `worlds/spec/`, `worlds/crafter/`, `worlds/nethack/`, `judge/`, `incumbents/` and `harness/`, each with a one-line README stating its layer.
- Add a `pyproject.toml` managed by `uv`, with Python ≥ 3.11 and no game dependencies yet.
- Add `.claude/settings.json` with a SessionStart hook running `scripts/bootstrap.sh`, which performs an idempotent `uv sync`.

### 2. Pin harness (`harness/`)
**Declaring a pin.** A pin declares:
- a name;
- the property it protects;
- the check, as a callable;
- one or more named mutants, each a code path selected by an environment flag or a patch file, never by editing the checked code in place.

**`make pins`.** Runs every pin twice over:
- on the clean build, where every pin must pass;
- once per mutant, where that pin must fail.

A pin whose mutant survives fails the suite with the message `MUTANT SURVIVED: <pin>/<mutant>`.

**P0, the harness itself.** Seed a mutant that makes every check return success. The suite must report the surviving mutants and exit non-zero. If the harness cannot kill its own trivial mutant, nothing above it can be trusted.

**Output.** A machine-readable JSONL report: pin, mutant, expected, observed, transcript path.

### 3. CI (`.github/workflows/`)
**`pins.yml`**
- Runs on GitHub-hosted `ubuntu-latest` for every pull request.
- Runs `make pins`.
- Is a required check.

**`measure.yml`**
- Runs on `[self-hosted, measure]`, triggered by `workflow_dispatch` or by the PR label `measure`.
- For now it only records host facts (`lscpu`, `free -h`, `uname -a`, container runtime versions, rootless Podman availability) to an artefact, and runs `make pins` on the host.
- Later layers add their pilots here.

### 4. Make targets
`make pins`, `make smoke` (no-op placeholder) and `make measure` (host-only; refuses to run unless the environment variable `ASSIZE_HOST=measure` is set, which only the runner sets).

## Pre-stated criteria
**L0 PASSED** only if all of the following hold:
- `make pins` passes on the clean build;
- P0's mutant is killed in the cloud session and in `pins.yml`;
- `measure.yml` is syntactically valid and targets the `measure` label.

Guy confirms the host run of `measure.yml` after merge. The session cannot witness the host run, so it must not claim it.

## Pins
- **P0 Harness self-kill.** As above.
- **P0b Mutant isolation.** A mutant flag leaking into the clean run, i.e. the clean build accidentally running with a mutant active, is detected. The clean run asserts that no mutant flag is set.

## Refusal list
- No World, judge, agent or incumbent code.
- No secrets, tokens or credentials in any file.
- No changes to `CLAUDE.md`, branch protection, repository settings or runner registration.
- No workflow may push, merge, tag or write to `main`.
- No LLM calls.

## Stop-and-report boundaries
Stop and report:
- if `CLAUDE.md` or the briefs are missing from the repository;
- if `uv` is unavailable in the session;
- if a pin cannot be made to fail.

On completion, open a pull request containing:
- the scaffold;
- the transcript of `make pins` (clean and mutants);
- the `measure.yml` file;
- a `REPORT.md` with a verdict of L0 PASSED or NOT PASSED.
