# L0 report — scaffold, pin harness, CI split

## Verdict
**L0: verdict pending one witness.** Two of the three pre-stated criteria are witnessed in this session (below). The third, that P0's mutant is killed in `pins.yml`, can be witnessed only by this pull request's own check run; its result is appended under *Addenda* once it exists. Posterior on PASSED is high but is not a verdict: no unwitnessed claims.

The host run of `measure.yml` is **not witnessed** and is not claimed. Guy confirms it after merge.

## Pre-stated criteria (brief 0)
| # | Criterion | Status | Witness |
|---|---|---|---|
| 1 | `make pins` passes on the clean build | MET | `make-pins.txt`: clean 5/5 passed; mutants 5/5 killed, 0/5 survived, 0/5 inconclusive; exit 0 |
| 2a | P0's mutant killed in the cloud session | MET | `make-pins.txt` row `P0/survivors_ignored -> killed`; `pins/runs/P0/survivors_ignored/transcript.log`. Raw self-kill: `negatives.txt` N1 |
| 2b | P0's mutant killed in `pins.yml` | PENDING | this PR's `pins` check run (Addenda) |
| 3 | `measure.yml` syntactically valid and targets the `measure` label | MET | `workflow-check.txt`: actionlint 1.7.12 exit 0; `runs-on: [self-hosted, measure]` |

All witnesses were produced at commit `efb4281` with a clean tree (`dirty=0` in each header), on the cloud VM. Cloud numbers are evidence for pass/fail only, never for timing.

## Pins
Denominator: every pin in registry `harness` (5), each run clean once and under each of its mutants (5 mutants, one per pin).

| Pin | Protects | Mutant (env flag) | Clean | Mutant |
|---|---|---|---|---|
| P0 | With every check returning success, the suite reports the survivors and exits non-zero | `P0/survivors_ignored` | ok | killed |
| P0b | A mutant flag leaking into the clean run is detected | `P0b/guard_off` | ok | killed |
| P0c | A failing clean check is recorded and fails the suite | `P0c/clean_failures_ignored` | ok | killed |
| P0d | Errors and timeouts are INCONCLUSIVE, counted, and fail the suite | `P0d/inconclusive_dropped` | ok | killed |
| P0e | Registries with a mutant-less pin or a duplicated pin or mutant name are refused | `P0e/validation_off` | ok | killed |

Each kill was checked for cause, not merely occurrence: the mutant transcripts show the specific assertions that fail (e.g. under `P0/survivors_ignored`, the nested all-pass run exits 0 and no row is `SURVIVED`; the control run still passes).

## Design
- **Child processes.** `python -m harness run` spawns one child per (pin, mutant). Child exit: 0 pass, 1 fail, 2 error, 3 leak; a child exceeding `child_timeout_s` (committed in `harness/config.toml`, 120 s) is killed by process group and recorded `timeout`. Clean: `pass` → ok, anything else → FAILED. Mutant: `fail` → killed, `pass` → SURVIVED (`MUTANT SURVIVED: <pin>/<mutant>`), anything else → INCONCLUSIVE. Exit 0 iff no FAILED, SURVIVED or INCONCLUSIVE.
- **Export.** `pins.jsonl`: one `registry` row (accepted/refused, config, timeout, inherited flags), one `run` row per child (`pin, mutant, selector, expected, observed, verdict, exit_code, duration_s, transcript`, plus `patch, patch_sha256, patch_copy_discarded` for patch mutants), one `summary` row with explicit denominators and the exit code.
- **Nesting.** Brief 0 requires both that `make pins` passes clean and that the suite, under an all-pass mutant, reports survivors and exits non-zero. These are reconciled by nesting: P0's check runs the orchestrator over a fixture registry with the seeded mutant `P0/checks_always_pass` active and asserts, from the exported rows, 2/2 SURVIVED and a non-zero exit. P0's own pin-level mutant, `P0/survivors_ignored`, breaks survivor detection and is killed. `negatives.txt` N1 shows the seeded all-pass mutant applied directly: 2/2 SURVIVED, exit 1.
- **Mutant flags.** `ASSIZE_MUTANT` holds a comma-separated set; nested runs take the union with the inherited set, so an outer harness mutant stays active in the harness code it spawns. Clean children inherit the environment unstripped, so a real leak is caught rather than masked: `negatives.txt` N2 runs `make pins` with a leaked flag and observes 5/5 clean FAILED (`observed leak`), exit non-zero.
- **Registries.** `harness/registries.py` maps names to modules; loading validates. Fixture registries (`harness/fixtures/`) exist only for the harness's own pins.

## Plan amendments
1. **P0c — clean-failure propagation.** Fixture pin `fixture/broken` (clean check `add(2,2)==5`) in registry `fixture.broken` with `fixture/toy`. P0c runs the nested orchestrator `--phase clean` and asserts from rows: `fixture/broken` observed `fail`, verdict FAILED; `fixture/toy` ok; `clean_failed`=1 of `clean_total`=2; non-zero exit. Harness mutant `P0c/clean_failures_ignored` reclassifies clean failures as ok; killed.
2. **P0d — inconclusive accounting.** Fixture mutants `fixture/toy/raises` (check raises) and `fixture/toy/hangs` (check loops past the timeout) in registry `fixture.inconclusive`, with `fixture/toy/off_by_one` as a killed control. The nested run uses the committed `harness/fixtures/fast.toml` (`child_timeout_s = 3`); no inline timeout literal. Assertions: raises observed `error`, hangs observed `timeout`, both INCONCLUSIVE; `mutants_total`=3, `inconclusive`=2, `killed`=1; hang duration ≥ configured timeout; config path recorded in the registry row; non-zero exit. Harness mutant `P0d/inconclusive_dropped` omits inconclusive rows from export and denominator; killed.
3. **P0e — registry validation.** `validate()` refuses `no_mutants`, `duplicate_pin` and `duplicate_mutant` (and malformed selectors). P0e runs the nested orchestrator over `fixture.no_mutants`, `fixture.dup_pin`, `fixture.dup_mutant` and asserts each registry row is `refused` with the matching code, no run rows, non-zero exit; control: `fixture.basic` accepted. Harness mutant `P0e/validation_off`; killed.
4. **Patch selector.** `Mutant(selector="patch", patch=<committed diff>)`: the orchestrator copies the repository (excluding `.git`, `.venv`, `out`, `reports`, caches) to a temporary directory, `git apply`s the diff, runs the child there, and discards the copy; rows record the patch's SHA-256 and `patch_copy_discarded`. A failed apply is recorded INCONCLUSIVE. Demonstrated by `fixture/toy/off_by_one_patch` (`harness/fixtures/patches/toy_off_by_one.diff`), killed in P0's control run, which asserts both selectors are present and the copy discarded. Rule carried forward: from L1, code under `judge/` and `worlds/` is mutated by patch only; env selectors stay confined to harness-internal mutants.
5. **Probes read exports.** Every nested-run assertion in P0–P0e reads `pins.jsonl` rows (`harness/nested.py`); the process exit code is also checked and must equal the summary row's `exit_code`. Nested stdout is kept only as a transcript (`nested/<label>/stdout.log`).
6. **Pinned actions.** `actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2`, `actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4.6.2`; SHAs resolved by `git ls-remote` against the upstream tags.
7. **Report layout.** This report and its witnesses live in `reports/L0/`; the root `REPORT.md` is an append-only index with one verdict line per layer.

## Notes and limits
- **actionlint label config is not committed.** actionlint rejects the custom label `measure` unless declared in a config file. The conventional location, `.github/actionlint.yaml`, is a `.github/` path brief 0 does not name, so it was not created. The config (three lines, reproduced in `workflow-check.txt`) was supplied from the session scratchpad. If Guy wants CI to lint workflows, a brief naming that file is required.
- **Not witnessed:** the host run of `measure.yml`, rootless Podman on the host, and `pins.yml` as a required check (Amendment A1.1: Guy adds it after this PR's run).
- **Toolchain:** uv 0.8.17 (pinned in `pins.yml`), Python 3.11 via `.python-version`; the project has no dependencies. `measure.yml` requires `uv` already installed on the host and fails loudly otherwise; it installs nothing.
- **Refusal list honoured:** no World, judge, agent or incumbent code; no secrets; no change to `CLAUDE.md` or settings; workflows have `contents: read` only and `persist-credentials: false`; no LLM calls.
- `make smoke` is a no-op placeholder; `make measure` refuses without `ASSIZE_HOST=measure` (`negatives.txt` N3).

## Witness index
| File | Content |
|---|---|
| `make-pins.txt` | full `make pins` transcript, clean and mutant runs |
| `pins/pins.jsonl` | exported rows of that run |
| `pins/runs/<pin>/<clean\|mutant>/transcript.log` | per-child transcripts, with nested runs under `nested/` |
| `negatives.txt` | N1 raw all-pass self-kill; N2 leaked flag in `make pins`; N3 `make measure` refusal; N4 `make smoke`; N5 bootstrap idempotence |
| `negatives/` | rows and transcripts of N1, N2 |
| `workflow-check.txt` | actionlint and `runs-on` evidence |
| `witness.sh` | regenerates all of the above |

## Transcript: `make pins`
```
# 2026-10-04T02:15:04Z Linux 6.18.44-fc-v64 x86_64 commit=efb4281 dirty=0
$ make pins PINS_OUT=reports/L0/pins
uv run --frozen python -m harness run --registry harness --phase all --out reports/L0/pins
registry harness: 5 pins, 5 mutants; phase=all; child_timeout_s=120.0 (harness/config.toml)
[clean ] P0: expected pass, observed pass -> ok (0.466s) reports/L0/pins/runs/P0/clean/transcript.log
[clean ] P0b: expected pass, observed pass -> ok (0.315s) reports/L0/pins/runs/P0b/clean/transcript.log
[clean ] P0c: expected pass, observed pass -> ok (0.265s) reports/L0/pins/runs/P0c/clean/transcript.log
[clean ] P0d: expected pass, observed pass -> ok (3.277s) reports/L0/pins/runs/P0d/clean/transcript.log
[clean ] P0e: expected pass, observed pass -> ok (0.365s) reports/L0/pins/runs/P0e/clean/transcript.log
[mutant] P0/survivors_ignored: expected fail, observed fail -> killed (0.566s) reports/L0/pins/runs/P0/survivors_ignored/transcript.log
[mutant] P0b/guard_off: expected fail, observed fail -> killed (0.315s) reports/L0/pins/runs/P0b/guard_off/transcript.log
[mutant] P0c/clean_failures_ignored: expected fail, observed fail -> killed (0.315s) reports/L0/pins/runs/P0c/clean_failures_ignored/transcript.log
[mutant] P0d/inconclusive_dropped: expected fail, observed fail -> killed (3.377s) reports/L0/pins/runs/P0d/inconclusive_dropped/transcript.log
[mutant] P0e/validation_off: expected fail, observed fail -> killed (1.018s) reports/L0/pins/runs/P0e/validation_off/transcript.log
clean: 5/5 passed, 0/5 failed
mutants: 5/5 killed, 0/5 survived, 0/5 inconclusive
report: reports/L0/pins/pins.jsonl
PINS PASSED
[exit 0]
```

## Transcript: N1, seeded all-pass mutant applied directly
```
## N1. Seeded mutant P0/checks_always_pass, applied directly to a fixture suite (every check returns success)
$ ASSIZE_MUTANT=P0/checks_always_pass uv run --frozen python -m harness run --registry fixture.basic --phase mutants --out reports/L0/negatives/n1
registry fixture.basic: 1 pins, 2 mutants; phase=mutants; child_timeout_s=120.0 (harness/config.toml)
[mutant] fixture/toy/off_by_one: expected fail, observed pass -> SURVIVED (0.064s) reports/L0/negatives/n1/runs/fixture__toy/off_by_one/transcript.log
MUTANT SURVIVED: fixture/toy/off_by_one
[mutant] fixture/toy/off_by_one_patch: expected fail, observed pass -> SURVIVED (0.072s) reports/L0/negatives/n1/runs/fixture__toy/off_by_one_patch/transcript.log
MUTANT SURVIVED: fixture/toy/off_by_one_patch
clean: 0/0 passed, 0/0 failed
mutants: 0/2 killed, 2/2 survived, 0/2 inconclusive
report: reports/L0/negatives/n1/pins.jsonl
PINS FAILED
[exit 1]

```

## Addenda

### A1 — 2026-10-04: pins.yml witness; verdict
**Verdict: L0 PASSED** (cloud and CI criteria). All three pre-stated criteria are now witnessed:
- 2b, P0's mutant killed in `pins.yml`: MET. PR #2 check `pins` on head `cd5cddb`, [run 37202929460](https://github.com/gfrmin/assize/actions/runs/37202929460/job/111438131029), conclusion success. Clean 5/5 passed; mutants 5/5 killed, 0/5 survived, 0/5 inconclusive; `P0/survivors_ignored -> killed`. Transcript: `pins-yml-run.txt`.
- The host run of `measure.yml` remains unwitnessed and unclaimed; Guy confirms it after merge.

Notes appended:
- **Base branch.** The repository's default branch is `master`; brief 0's precondition and `CLAUDE.md` say `main`. A PR against `main` was refused by GitHub (base invalid). The PR targets `master` on Guy's explicit instruction in this session. Whether `master` carries the protection the precondition describes was not verified by this session.
- **Runner warning.** GitHub reports that the pinned `actions/checkout` v4.2.2 and `actions/upload-artifact` v4.6.2 target Node.js 20, now forced onto Node.js 24. Not a failure; a later brief may bump the pinned SHAs.

### A2 — 2026-10-05: one mutation mechanism (brief 0 Amendment A2); verdict
**Verdict: L0 PASSED under brief 0 A2** (dev-box session and `pins.yml`). `make pins`: clean 7/7 passed; mutants 7/7 KILLED, 0/7 survived, 0/7 inconclusive, 0/7 stale, 0/7 non-causal; twins 7/7 passed. Witnessed locally at `9ab8dd1` (`a2/make-pins.txt`) and by `pins.yml` on PR #2 at `477d477`, [run 37339180067](https://github.com/gfrmin/assize/actions/runs/37339180067/job/111861576846) (`a2/pins-yml-run.txt`). The host run of `measure.yml` remains unwitnessed and unclaimed.

**Withdrawal.** The A1 verdict's causality claim for the kills of **P0b** (`P0b/guard_off`) and **P0c** (`P0c/clean_failures_ignored`) is withdrawn. Under the previous design the mutant flag was inherited by every nested clean child, which the leak guard then failed. Each of those two checks therefore failed under *any* flag, whatever the flag's code path did. Witness `a2/withdrawal.txt` replays `5f7372a` with an inert flag `<pin>/inert` that selects no code path:

| Pin | Under inert flag | Reading |
|---|---|---|
| P0 | PASS | kill not shown non-causal by this test |
| P0b | FAIL (control run trips the leak guard) | kill NON-CAUSAL; claim withdrawn |
| P0c | FAIL (both clean rows observed `leak`) | kill NON-CAUSAL; claim withdrawn |
| P0d | PASS | kill not shown non-causal by this test |
| P0e | PASS | kill not shown non-causal by this test |

The A1 verdict line is not edited. It is superseded by this addendum's verdict, which rests on the redesign below.

**Redesign** (commits `e21d1b8` briefs, `8f10cd0` refactor, `9ab8dd1` process fix):
- *One mechanism.* A mutant is a committed TOML file of `[[edit]]` tables `(path, old, new)` (`harness/edits.py`). At application, `old` must occur exactly once; otherwise the run is STALE. Unified diffs are retired (`harness/fixtures/patches/` deleted).
- *Trusted base.* Edits apply only inside `tree.disposable_copy`. That copies the tree of the running code, so edits compose, and excludes the top-level `.git`, `.venv`, `out`, `reports` and caches. Clean runs execute in the invocation tree, which never executes mutated code.
- *No switches.* The following are deleted: `harness/mutants.py`, every `mutants.active` switch, the flag variable, flag inheritance, the clean-run leak guard, the `ASSIZE_RUN_DIR` environment hand-off, and the in-child all-pass switch. The child's invocation root and run directory now arrive as command-line arguments (`harness/context.py`).
- *Causal twin.* Every mutant run is paired with a fresh unedited copy. The verdict, in order: STALE if an anchor failed; NON-CAUSAL if the twin did not pass; KILLED if the mutant failed; SURVIVED if it passed; INCONCLUSIVE otherwise. Mutant and twin rows are both exported, and STALE, NON-CAUSAL and INCONCLUSIVE all count in the denominator and fail the suite.
- *Kept:* runner structure, registries, validation (extended to `malformed_edit`), JSONL export, nested probes reading `pins.jsonl`, config, workflows, report layout.

**Pins** (each mutant is an anchored edit to the harness, in `harness/edits/`):

| Pin | Check | Mutant | Kill witnessed (mutant fails / twin passes) |
|---|---|---|---|
| P0 | inner run over `fixture.basic` in a copy carrying `P0_checks_always_pass` (every child check returns success) reports 2/2 SURVIVED and exits non-zero; control run kills 2/2 with twins passing, every mutant and twin runs in a discarded copy, and the invocation tree's `harness/` digest is unchanged | `survivors_ignored` | yes |
| P0b | static scan of 29 code files (`.py`, `.sh`, `.yml`, `.yaml`, `Makefile`, `Dockerfile`, `Containerfile`; top-level exclusions as above) finds no `ASSIZE_MUTANT` or `ASSIZE_TEST*` token, no import of a mutant-switch module, and no such module | `env_switch` (adds an environment read to `harness/config.py`) | yes: `VIOLATION harness/config.py:13` |
| P0c | `fixture/broken` recorded FAILED; 1 of 2 clean runs failed; exit non-zero | `clean_failures_ignored` | yes |
| P0d | `raises` observed error and `hangs` observed timeout (committed 3 s `fast.toml`), both INCONCLUSIVE with twins passing; 3 mutants, 2 inconclusive, 1 killed; exit non-zero | `inconclusive_dropped` | yes |
| P0e | `no_mutants`, `duplicate_pin`, `duplicate_mutant` and `malformed_edit` registries each refused, with no pin run; control accepted | `validation_off` | yes |
| P0f | `fixture/outside` passes in the invocation tree; its mutant and twin both fail in copies, giving NON-CAUSAL; 1 of 1 non-causal; exit non-zero | `twin_ignored` | yes |
| P0g | the absent anchor (0 occurrences) and the duplicated anchor (2 occurrences) are each STALE; control KILLED; 3 mutants, 2 stale, 1 killed; exit non-zero | `stale_ignored` | yes |

**Witnesses** (`reports/L0/a2/`, regenerated by `witness.sh`; stamps show `9ab8dd1`, `dirty=0`):
- `make-pins.txt`, `pins/`: every pin's clean run; every mutant run with its twin.
- `fixtures.txt`, `fixtures/`: `fixture.stale` gives 2 of 3 STALE, exit 1; `fixture.noncausal` gives 1 of 1 NON-CAUSAL with its twin failing, exit 1.
- `review-mutants.txt`, `review/`: the whole suite, run in a disposable copy carrying each unregistered review mutant (`run --under-edits`; committed 30 s child timeout in `review-mutants/config.toml`). All four went red, and the invocation tree's `harness/` digest was `db910df6b90565c5` both before and after:

| Review mutant | Exit | What turned it red |
|---|---|---|
| exit code 2 treated as pass | 1 | P0d clean FAILED (`raises` no longer INCONCLUSIVE); P0d's mutant NON-CAUSAL |
| inconclusive runs omitted from the denominator | 1 | P0d clean FAILED (denominator 3 → 1); P0d's mutant NON-CAUSAL |
| edits applied to the original tree | 1 | 6 of 7 clean FAILED; 7 of 7 mutants NON-CAUSAL; 0 of 7 twins passed |
| clean failures ignored | 1 | P0c's mutant STALE (its anchor is the line this edit replaces), and its twin also failed. P0c's own check failed, but the mutated top level records that clean failure as ok: this mutant masks its own clean signal. The red comes from the mutant and twin accounting, which the twin exists to provide. |

- `withdrawal.txt`: as above.
- `orphan-probe.txt`: see the defect below.
- `pins-yml-run.txt`: the CI transcript.

**Defect found and fixed.** Children ran in new sessions, and a timeout killed only the child's process group. A nested orchestrator's own children, in further sessions, escaped, and a hanging one ran for ever. The witness run under review mutant 3 left grandchildren running past 540 s. Since `9ab8dd1`, every spawn sets `PR_SET_PDEATHSIG` (`harness/proc.py`, Linux), so a kill cascades down the tree. `orphan-probe.txt` shows 1 process left alive at `8f10cd0` and 0 at HEAD after SIGKILLing an orchestrator whose child hangs. **No pin protects this fix.** P0d's hang runs in a direct child, so its fixtures cannot tell the two behaviours apart. A pin needs a fixture whose check hangs in a grandchild, plus a mutant that drops the parent-death signal. Proposed for a later brief; not claimed here.

**Limitations and notes.**
- *Copies left by killed children.* A child SIGKILLed on timeout cannot remove copies it created. The review-mutant-3 run left 9 in the system temp dir, all carrying the hang edit; they were deleted by hand after the run. This happens only when a child times out.
- *P0b scope.* The scan reads code files only and excludes top-level `reports/`. Historical witnesses there are records, not code: for example, `reports/L0/witness.sh` sets the withdrawn variable and no longer runs against the current harness. Documentation (`.md`) is not scanned. Brief 1 A3 extends the scan to the built judge image; that is L1 work.
- *Additions beyond the letter of A2:* P0's trusted-base assertions (the digest, and copies distinct from the invocation tree); `run --under-edits`; the parent-death signal.
- *Brief 1 A3* (appended verbatim) replaces "A2 item 2 (P8 …)". Brief 1 as committed has no A2 and no P8; its only amendment is A1. The reference does not resolve in the repository; Guy to confirm whether a brief 1 A2 is missing.
- *Where these witnesses ran.* Witnesses other than `pins-yml-run.txt` ran on Guy's development machine (Arch Linux, Python 3.11.11), not the cloud VM. They are pass/fail evidence only; no timing in them is evidence for anything.
- `pins.yml` still warns that the pinned actions target Node.js 20.
