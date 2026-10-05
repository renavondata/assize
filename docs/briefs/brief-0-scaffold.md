# Claude Code brief 0 — L0 scaffold: pin harness and CI split

## Precondition
Guy has done all of the following:
- created the repository `assize`, private until L2 is sealed;
- committed `CLAUDE.md` and `docs/briefs/brief-1-judge-and-crafter.md` and `docs/briefs/brief-2-nethack.md`;
- protected `master`: pull request required, status checks required, no direct pushes;
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
- No workflow may push, merge, tag or write to `master`.
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

---

## Amendment A1 (appended; overrides earlier text where they conflict)
1. **Required status check.** GitHub can only require a status check after it has run once. At precondition time, `master` requires a pull request and forbids direct pushes. Guy adds `pins.yml` as a required check after this session's PR has run it.
2. **Brief file names.** The briefs live in the repository as `docs/briefs/brief-0-scaffold.md`, `docs/briefs/brief-1-judge-and-crafter.md` and `docs/briefs/brief-2-nethack.md`.
3. **Workflow authority.** This brief names `.github/workflows/`. Creating `pins.yml` and `measure.yml` there is authorised.

---

## Amendment A2: one mutation mechanism (appended; overrides earlier text and A1 where they conflict)
The original brief permitted mutants "selected by an environment flag or a patch file". Two mechanisms interacted: inherited flags tripped the leak guard, which made two kills non-causal. This amendment withdraws environment-flag mutants entirely.

1. **Anchored edits only.** A mutant is a committed file listing one or more edits, each of the form `(path, old, new)`.
   - At application time, `old` must occur exactly once in `path`.
   - Zero or multiple matches make the run STALE. A STALE run is recorded, counted in the denominator, and fails the suite.
   - Unified diffs are retired.

2. **Trusted base.** Edits are applied only to a disposable copy of the repository tree. The tree from which `make pins` is invoked never executes mutated code.
   - The copy excludes top-level paths only: `.git`, `.venv`, `out`, `reports`, caches.
   - A child running in a copy that makes further copies copies its own tree, so edits compose.

3. **No switches.**
   - Delete `harness/mutants.py`, every `mutants.active(...)` switch, the `ASSIZE_MUTANT` variable, flag inheritance, and the clean-run leak guard.
   - No code in the repository may read a mutant or test variable from the environment.

4. **Causal twin.** Every mutant run is paired with a twin run: an identical fresh copy with no edits applied. The twin must pass.
   - A mutant counts as KILLED only if the mutant run fails and its twin passes.
   - A mutant whose twin fails is NON-CAUSAL; it is counted and fails the suite.
   - Both rows are exported. The twin is the ablation witness, so no separate ablation exercise is needed.

5. **L0 pins.** Each pin's own mutant is an anchored edit to the harness, and each must be causal under item 4.
   - **P0, survivors reported.** The check runs an inner orchestrator over a fixture registry in a copy carrying an edit that makes every child check return success. It must observe every fixture mutant SURVIVED and a non-zero exit.
   - **P0b, no switches.** A static scan finds no environment read of any `ASSIZE_MUTANT` or `ASSIZE_TEST*` variable, and no import of a mutant-switch module, anywhere in the repository. A mutant edit that adds one must be caught.
   - **P0c, clean failures.** Unchanged in intent: a failing clean fixture is recorded FAILED and fails the suite.
   - **P0d, inconclusive.** Fixture mutants that make the check raise, and that make it hang past the configured timeout, are recorded INCONCLUSIVE, counted, and fail the suite.
   - **P0e, registry validation.** A pin with zero mutants, duplicate pin or mutant names, and a mutant file with a malformed edit are each refused.
   - **P0f, non-causal detection.** A fixture whose check fails whenever it runs outside the invocation tree must be recorded NON-CAUSAL, with a non-zero exit.
   - **P0g, stale anchors.** A fixture mutant whose `old` string is absent, and one whose `old` occurs twice, are each recorded STALE, counted, and fail the suite.

6. **Record.** Append Addendum A2 to `reports/L0/REPORT.md` and a new line to the root index. The addendum must record:
   - the withdrawal of the causality claim for P0b and P0c under the previous design;
   - the redesign;
   - the new verdict.
