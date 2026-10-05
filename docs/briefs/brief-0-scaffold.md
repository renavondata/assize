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

---

## Amendment A3: review finding F1 disposed (appended; overrides earlier text and A1–A2 where they conflict)

Review of 47af530 found (F1) that P0h is stated universally but witnessed only for cooperating processes, and that a run recording `scratch_quiescent: false` keeps its verdict and has its scratch root deleted anyway. The finding is correct. It is disposed as follows. Items 1–4 are blocking under the standing rules (nothing dropped silently; no unwitnessed claims). Item 5 is an L1 obligation and is NOT built in this session.

### 1. LEAKED verdict
- In `harness/runner.py`, a run whose row has `scratch_quiescent == false` takes the verdict `LEAKED`, whatever `observed` says. For a mutant pair, `LEAKED` on either the mutant or the twin row makes the pair's verdict `LEAKED`, never `KILLED`.
- `LEAKED` is counted in the denominator: add `leaked` to `TALLY` and to the summary row. Print `[clean ] <pin>: ... -> LEAKED` and `MUTANT LEAKED: <label>` exactly as the other verdicts are printed. Exit non-zero if `leaked > 0`.
- The scratch root is still deleted after the row is written, as now; the difference is that the row fails the suite.

### 2. Fixture: the escapee
- Registry `fixture.escapee` (`harness/fixtures/escapee.py`): a pin whose check spawns a grandchild with `start_new_session=True` and NO death signal, with its working directory inside the run's scratch root, that sleeps `escape_hold_s` seconds and then exits on its own. The check then hangs past the child timeout.
- `escape_hold_s`, `child_timeout_s` and `reap_grace_s` for this fixture are committed in `harness/fixtures/fast.toml`, with `escape_hold_s > child_timeout_s + reap_grace_s`. No inline literals.
- Expected under the nested fast config: child `timeout`, `scratch_quiescent: false`, verdict `LEAKED`, summary `leaked = 1`, non-zero exit.
- The grandchild exits by itself, so the fixture leaves nothing behind. P0h waits for it (poll `proc.alive`, bounded by `escape_hold_s` plus the configured step) before returning, and asserts no survivor and no scratch root at the end. A pin that leaks a process on every CI run would be a defect of its own.

### 3. P0h: extended check, narrowed claim, new mutant
- The check runs the nested orchestrator over `fixture.escapee` and asserts, from the exported rows: `observed == "timeout"`, `scratch_quiescent == false`, `verdict == "LEAKED"`, `leaked == 1` in the summary, exit code non-zero and equal to the summary's. The existing cooperating-grandchild assertions stay.
- New mutant `P0h/leaked_not_counted`: an anchored edit to `harness/runner.py` under which a `scratch_quiescent: false` row keeps the verdict it would otherwise have had. It must be `KILLED` with a passing twin. The existing mutants `death_signal_reverted` and `scratch_kept` stay and must still be `KILLED` with passing twins.
- Replace P0h's description with the witnessed scope: "a timed-out child, and every descendant that either carries the parent-death signal or holds the run's scratch root, is dead or recorded LEAKED before the scratch root is deleted. Out of scope at L0: a descendant detached from both (new session, no death signal, not holding the scratch root), and the outermost orchestrator being SIGKILLed."

### 4. Negative witness N6: the daemon gap
- Reproduce the reviewer's clean case on a scratch copy: a clean check that double-forks a daemon (new session, no death signal, not holding the scratch root) and returns True. Record the transcript showing verdict `ok`, `scratch_quiescent: true`, `PINS PASSED`, and the daemon alive afterwards. The probe script kills its own daemon by PID file before exiting and shows that it did.
- This is a known gap at L0, declared out of scope by item 3, and discharged at L1 by item 5. It is witnessed, not fixed, here.

### 5. L1 obligation (record verbatim in Addendum A4; do not build)
Harness: every orchestrator process sets `PR_SET_CHILD_SUBREAPER`; children run one at a time, asserted; after every child run and before its scratch root is deleted, every remaining descendant is killed, repeating until none remain, and the count is recorded as `leaked_processes`; `leaked_processes > 0` is `LEAKED`. Fixtures: the cooperating grandchild; a non-cooperating grandchild (new session, no death signal, SIGTERM ignored, hanging past the timeout); a double-forked daemon from a clean check returning True. Mutants, each an anchored edit, each `KILLED` with a passing twin: subreaper not set; sweep skipped; `LEAKED` not counted; scratch kept. If `death_signal_reverted` then survives because the subreaper makes the death signal redundant, either pin a case only the death signal covers or remove the death signal and retire the mutant, recording why; no mechanism without a killed mutant. Judge: containers started by the judge are killed and removed on timeout, witnessed by a pin (P10) with a non-cooperating process inside the container that ignores SIGTERM; a candidate container alive after teardown is an episode with termination code `LEAKED`, counted, never dropped. Process-level sweeping does not reach containerd-shim children.

### 6. Record
- Append Addendum A4 to `reports/L0/REPORT.md`: F1 quoted in full; the two reviewer probes reproduced with transcripts; the disposition of items 1–4; N6; item 5 verbatim as the L1 obligation; the verdict. Witnesses follow the A3 hygiene rule.
- Append one verdict line to the root `REPORT.md`.
- Before running `make pins` for the first time in this session, create `reports/L0/forecasts.jsonl` and append one record per claim, each a JSON object `{"id", "ts", "proposer": {"kind": "builder", "model", "session"}, "sha_before", "claim", "p", "resolves_by"}`, for at least: "pins green on the first CI run of this PR head" and "reviewer verdict ACCEPT with no blocking finding". `id` is the first 12 hex characters of the SHA-256 of `claim + ts`. Probabilities are yours; nobody checks them except the ledger.
- Add a `proposer` object (`kind`, `model`, `session`) to the `registry` row of `pins.jsonl`.
- Write `reports/L0/STATUS.md`, at most 40 lines, in this exact shape:

```
# STATUS — L0 — <date> — <sha> — PR #2
VERDICT: <L0 verdict | SESSION DONE | STOPPED: reason>
LAYER BOUNDARY: yes
pins: clean a/b; mutants c/d KILLED; twins e/f; leaked g; stale h; inconclusive i; non-causal j; exit k
changed: <paths>
did: <at most 5 lines>
decided (not asked): <decision> — p(stands on review)=<p>
forecasts: made <n>; resolved <m>; cumulative log-loss <x> vs base rate <y> over <N>
obligations added: L1: <one line pointing at A4 item 5>
NEEDS YOU (at most 1): <item or none>
next: <first item of the next session>
```

### Pre-stated criteria (this amendment is complete only if all hold)
- `make pins` passes on the clean build with every mutant, including `P0h/leaked_not_counted`, `KILLED` with a passing twin.
- The nested `fixture.escapee` run is recorded `LEAKED` with `leaked = 1` and a non-zero exit, and leaves no process and no scratch root behind.
- N6 is witnessed with its transcript, and its daemon is shown killed.
- The `pins` check is green on the PR head.
- A4, the root index line, `forecasts.jsonl`, the `proposer` field and `STATUS.md` exist as specified.

### Refusal list
- No subreaper, no sweep, no `leaked_processes`, no new fixture beyond `fixture.escapee`, no change to the death signal.
- No edits to `CLAUDE.md`, `.github/`, repository settings or runner registration.
- Do not merge. Do not open a new PR.

### Stop and report
- If `fixture.escapee` cannot be made to outlive `reap_grace_s` deterministically on the cloud VM and on `ubuntu-latest` (watch for scheduler jitter: state the margin you chose and why).
- If any mutant cannot be made to fail.
- If the daemon in N6 cannot be killed by the probe.
A stopped session with a clear STATUS is a success.
