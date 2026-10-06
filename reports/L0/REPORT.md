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

### A3 — 2026-10-05: pre-merge items (brief 1 A2 ordering, P0h, witness hygiene); verdict
**Verdict: L0 PASSED under brief 0 A2, with P0h.** `make pins`: clean 8/8 passed; mutants 9/9 KILLED, 0/9 survived, 0/9 inconclusive, 0/9 stale, 0/9 non-causal; twins 9/9 passed. Witnessed locally at `196d5b4` (`a3/make-pins.txt`) and by `pins.yml` on PR #2 at `735f357`, [run 37344138903](https://github.com/gfrmin/assize/actions/runs/37344138903/job/111878357745) (`a3/pins-yml-run.txt`). The host run of `measure.yml` remains unwitnessed and unclaimed.

**1. Brief 1 Amendment A2.** Inserted verbatim immediately before brief 1's A3 (`800969f`), with no other line changed; brief 1 now reads A1, A2, A3. This resolves the open question in Addendum A2's notes: A3's reference to "A2 item 2 (P8 …)" now has a referent. A2 and A3 are both unmerged, so this corrects their order within the PR and rewrites no signed text.

**2. P0h: timeouts leave nothing behind** (`7bf3ba8`).
- *Parent-owned scratch.* The orchestrator creates one scratch root per child run and passes it as `--scratch`, on the command line, never the environment. Every copy the child or its descendants make is created under that root: `tree.disposable_copy` defaults to it, and nested orchestrators receive `--scratch-root`. After the child exits or is killed, the parent waits up to `reap_grace_s` for no live process to hold the root, then deletes it. `reap_grace_s` = 5 s, committed in `harness/config.toml` before these runs. Rows record `scratch`, `scratch_quiescent`, `scratch_removed` and `run_dir`. This closes Addendum A2's limitation that a killed child could not remove its own copies.
- *No straggler sweep.* The parent does not kill leftover processes itself, because a sweep would hide a missing process-death fix.
- *Fixture mutant `fixture/toy/leaks_and_hangs`* (`harness/fixtures/leaky.py`):
  - it spawns a grandchild that ignores SIGTERM and sleeps for ever, spawned the way the harness spawns its own children (new session, parent-death signal), so a process-group kill cannot reach it;
  - it writes that grandchild's PID to the run directory, outside every copy;
  - it opens a nested copy and records its path;
  - it hangs past the 3 s `fast.toml` timeout.
- *P0h check.* The leaking mutant is observed `timeout` and recorded INCONCLUSIVE, and its twin passes. Then: the grandchild is no longer alive (polled up to `reap_grace_s`); no live process holds the run's scratch root; the parent saw the root quiescent before deleting it; the nested copy is removed; the scratch root is removed. Whatever the verdict, the check then kills any surviving grandchild and removes any leftover root.
- *Mutants*, each an anchored edit, each KILLED with a passing twin (`a3/make-pins.txt`; transcripts in `a3/make-pins-runs.tar.xz`):

| Mutant | Edit | Failing assertions |
|---|---|---|
| `P0h/death_signal_reverted` | `harness/proc.py`: drop the `PR_SET_PDEATHSIG` call | grandchild still alive; a live process holds the scratch root; root not quiescent |
| `P0h/scratch_kept` | `harness/runner.py`: skip deleting the scratch root | nested copy not removed; scratch root not removed |

- P0d's registered edit was re-anchored to the call this change altered, which the suite would otherwise have recorded STALE.
- Addendum A2 proposed a pin for the process-death fix. P0h is that pin, so the limitation is closed.

**3. Witness hygiene.** Branch history is not rewritten; earlier witnesses and the SHAs they cite stand. From A3 onwards, each witness run commits its top-level transcript and `pins.jsonl` uncompressed. Its per-child and nested transcripts go into one reproducible `tar.xz`: names sorted, mtime 0, owner 0, `xz -9e`. The `transcript` paths inside the jsonl name `out/a3-witness/<run>/runs/…`, which corresponds to `runs/…` inside the archive.

| Archive | SHA-256 | Compressed bytes | Uncompressed tar bytes | Files |
|---|---|---|---|---|
| `a3/make-pins-runs.tar.xz` | `b6ee6e46cac6541dc507c9afd05a31c2468942ac700c7dd271f12ede34cb242e` | 17,796 | 593,920 | 221 |
| `a3/leaks-fixture-runs.tar.xz` | `2f944fb703b816dad834da2bbe89a5f287c61be95d3de0ef3e3db3f5ee8bf9a6` | 708 | 20,480 | 6 |

The same figures are in `a3/MANIFEST.txt`; both archives pass `xz -t`.

**Witnesses** (`reports/L0/a3/`, regenerated by `witness.sh`; stamps show `196d5b4`, `dirty=0`):
- `make-pins.txt`, `make-pins.jsonl`, `make-pins-runs.tar.xz`: every pin's clean run, and every mutant with its twin. Zero `/tmp/assize-*` directories and zero marker processes, both before and after.
- `leaks-fixture.txt`, `leaks-fixture.jsonl`, `leaks-fixture-runs.tar.xz`: `fixture.leaks` run directly. `leaks_and_hangs` is recorded INCONCLUSIVE (timeout) and `off_by_one` KILLED, exit 1. Afterwards, the recorded grandchild is not alive, the recorded nested copy does not exist, and nothing is left in `/tmp`.
- `pins-yml-run.txt`: the CI transcript.

**Notes.**
- The A2 review-mutant files under `a2/review-mutants/` were written against the A2-era runner. Some anchors may no longer apply to the current code, which `--under-edits` reports as STALE. They are historical witnesses and were not re-run here.
- These witnesses, other than `pins-yml-run.txt`, ran on Guy's development machine (Arch Linux, Python 3.11.11). They are pass/fail evidence only.
- P0h relies on Linux `/proc` and `prctl`. That holds on the cloud VM, GitHub's `ubuntu-latest` (witnessed above) and the host (to be witnessed by `measure.yml`).

#### A3 correction — 2026-10-05: review mutants re-run
The A3 note saying some A2 review-mutant anchors "may no longer apply" was wrong. All four still apply exactly once to the current harness. They were re-run at `5c14c3e` (`a3/review-mutants.txt`, script `a3/review-rerun.sh`, same committed 30 s config), and all four went red:

| Review mutant | Exit | What turned it red |
|---|---|---|
| exit code 2 treated as pass | 1 | P0d clean FAILED; P0d's mutant NON-CAUSAL |
| inconclusive runs omitted from the denominator | 1 | P0d clean FAILED; P0d's mutant NON-CAUSAL |
| edits applied to the original tree | 1 | 7 of 8 clean FAILED; 9 of 9 mutants NON-CAUSAL; 0 of 9 twins passed |
| clean failures ignored | 1 | P0c's mutant STALE, with its twin failing (the self-masking case explained in Addendum A2) |

The invocation tree's `harness/` digest was `4328bce9a12ada73` both before and after. Before and after the run there were 0 `/tmp/assize-*` directories and 0 harness processes, including after review mutant 3: in the A2 round that mutant left 9 copies behind, and parent-owned scratch roots now remove them.

| Archive | SHA-256 | Compressed bytes | Uncompressed tar bytes | Files |
|---|---|---|---|---|
| `a3/review-exit2_as_pass.tar.xz` | `f360c9ba7638314511c0a99d0d0e6ffdd32c3bf64e17feeb5c87f499cd3fcd3b` | 19,244 | 624,640 | 222 |
| `a3/review-inconclusive_omitted.tar.xz` | `7703c14e0c7041f1a7b73019abdaf54ee3145b0c1c97e8f85cbf632608476761` | 19,248 | 624,640 | 222 |
| `a3/review-applied_to_original_tree.tar.xz` | `0838b12e4c9a349140e56ca4edc25f1086065739186dd093d658c679104d95b8` | 14,708 | 481,280 | 220 |
| `a3/review-clean_failures_ignored.tar.xz` | `9406c8e67061b2cf9bac0d515bc9382d082fef85fca5b42e470489d6c4c406d4` | 18,948 | 614,400 | 218 |

The verdict is unchanged.

#### A3 note — 2026-10-05: base branch decided
Guy confirmed in session that the base branch is `master`, not `main`. This settles the discrepancy noted in Addendum A1. Signed text still names `main`: `CLAUDE.md` line 35, brief 0 lines 7, 73 and 91, and brief 2 line 108. This session edited none of it, because `CLAUDE.md` reserves that file to Guy and the briefs change only by amendment. No workflow, Make target or harness code names a branch, so the change has no functional effect. Still to be confirmed by Guy: that `master` carries the protection brief 0's precondition describes, and that `pins` is a required check.

#### A3 finding — 2026-10-05: branch protection unavailable
`gh api repos/gfrmin/assize/branches/master/protection`, `.../rulesets` and `.../rules/branches/master` each return HTTP 403: "Upgrade to GitHub Pro or make this repository public to enable this feature." The repository is PRIVATE with default branch `master`. On the current plan, therefore, `master` cannot be protected and `pins` cannot be made a required check, so brief 0's precondition does not hold. The constitution's "never push or merge" rules are currently enforced by discipline alone. The remedy is Guy's: GitHub Pro, which keeps the repository private, or making the repository public, which conflicts with brief 0's "private until L2 is sealed" and would need an amendment. Neither affects the L0 verdict, whose criteria are the pins.

#### A3 note — 2026-10-05: repository transferred; master protected
On Guy's instruction:
- **Signed text.** The five `main` references were changed to `master` in `5177756`: `CLAUDE.md` line 35, brief 0 lines 7, 73 and 91, brief 2 line 108. No other line changed.
- **Transfer.** The repository was transferred from `gfrmin/assize` to `renavondata/assize`, an organisation on GitHub Enterprise. It is still PRIVATE, with default branch `master`. History, PR #2 and Actions history moved with it. Run and job links cited earlier in this report name `gfrmin/assize`; GitHub redirects them after a transfer.
- **Protection on `master`,** applied with `PUT /repos/renavondata/assize/branches/master/protection`:
  - pull request required, with 0 approvals;
  - required status check `pins` (GitHub Actions app), not strict;
  - enforced for admins;
  - force-pushes and deletion disallowed.
  Read-back: `protected: true`, `required_checks: ["pins"]`. PR #2 then reported `mergeStateStatus: CLEAN` with `pins: SUCCESS`. A direct push was not attempted, because `CLAUDE.md` forbids pushing to `master`. This resolves the A3 finding above for `renavondata/assize`, and with it brief 0 A1.1.
- **Finding: no self-hosted runner exists.** Before the transfer, `GET /repos/gfrmin/assize/actions/runners` returned `total_count: 0`. Brief 0's precondition of a runner labelled `measure` therefore did not hold, and `measure.yml` cannot run until Guy registers one, now under `renavondata`. Runner registration is Guy's alone.

### A4 — 2026-10-05: review finding F1 disposed (brief 0 Amendment A3); verdict
**Verdict: L0 PASSED under brief 0 A2 and A3.** `make pins`: clean 8/8 passed; mutants 10/10 KILLED, 0/10 survived, 0/10 inconclusive, 0/10 stale, 0/10 non-causal; 0 leaked; twins 10/10 passed; exit 0. Witnessed locally at `cea5957` (`a4/make-pins.txt`) and by `pins.yml` on PR #2 at `f07330a`, the first CI run of this session's head: [run 37358542927](https://github.com/renavondata/assize/actions/runs/37358542927/job/111927025551) (`a4/pins-yml-run.txt`). The host run of `measure.yml` remains unwitnessed and unclaimed, and needs a registered runner.

**F1, quoted in full** (as stated in brief 0 A3; no other text of the review was supplied to this session):
> Review of 47af530 found (F1) that P0h is stated universally but witnessed only for cooperating processes, and that a run recording `scratch_quiescent: false` keeps its verdict and has its scratch root deleted anyway.

**Reviewer probes, reconstructed from F1 and reproduced** (`a4/probes.txt`, `a4/probes.sh`; rows in `a4/probe-*.jsonl`). Each probe runs on a disposable copy carrying an injected probe fixture; nothing is added to `harness/`.

| Probe | Revision | Row | Suite | Afterwards |
|---|---|---|---|---|
| R1: a clean check returns True; its grandchild (new session, no death signal, cwd in the scratch root) lives 10 s | `47af530` | observed pass, `scratch_quiescent: False`, verdict **ok** | **PINS PASSED**, exit 0 (the defect) | grandchild alive right after; exited on its own within 10 s; 0 markers |
| R1 | HEAD (`cea5957`) | observed pass, `scratch_quiescent: False`, verdict **LEAKED**; summary leaked 1 | PINS FAILED, exit 1 | as above |
| N6: a clean check double-forks a daemon (new session, no death signal, cwd `/`) and returns True | HEAD (`cea5957`) | observed pass, `scratch_quiescent: True`, verdict **ok** | **PINS PASSED**, exit 0 (the declared gap) | daemon alive after the suite (ppid 1, own session, cwd `/`); `kill -9` by PID file; shown dead; 0 markers |

**Disposition of A3 items 1–4.**
1. *LEAKED verdict* (`f5be46e`, `harness/runner.py` `_leak_override`):
   - a row with `scratch_quiescent == false` is LEAKED whatever was observed;
   - LEAKED on the mutant or the twin row makes the pair LEAKED;
   - `leaked` is counted in `TALLY` and the summary row. A clean LEAKED row also counts in `clean_failed`. The summary's `leaked` covers clean and mutant rows together;
   - it is printed like the other verdicts and exits non-zero;
   - the scratch root is still deleted.
2. *`fixture.escapee`* (`harness/fixtures/escapee.py`):
   - Its grandchild starts in a new session with no death signal, works inside the run's scratch root, sleeps `escape_hold_s` and exits on its own, while the check hangs.
   - `harness/fixtures/fast.toml` commits `child_timeout_s = 3`, `reap_grace_s = 2` and `escape_hold_s = 12`.
   - **Margin: 12 − (3 + 2) = 7 s.** The grandchild starts after the child, while the parent stops waiting about 5 s after the child's start. Only a stall of over 7 s could flip the verdict; shared-runner jitter is milliseconds to hundreds of milliseconds.
   - Observed: the parent stopped waiting at 5.065 s locally and at 5.033 s on `ubuntu-latest`. The local run gave timeout, `scratch_quiescent: false`, LEAKED, leaked = 1, exit 1. Afterwards the grandchild exited on its own, the scratch root was gone, and nothing was left (`a4/escapee-fixture.txt`).
   - **Not witnessed on the cloud VM.** This session ran on Guy's development machine; `ubuntu-latest` and the development machine are witnessed.
3. *P0h:*
   - The escapee assertions (observed timeout, `scratch_quiescent == false`, verdict LEAKED, summary leaked = 1, exit non-zero and equal to the summary's) are read from exported rows. P0h then waits for the grandchild, up to `escape_hold_s` plus `poll_step_s`, and asserts no survivor and no scratch root.
   - The cooperating-grandchild assertions stay.
   - The description is replaced with the witnessed scope, verbatim from A3 item 3.
   - Mutants, each KILLED with its twin passing (`a4/make-pins-runs.tar.xz`):
     - `leaked_not_counted` fails exactly on "verdict LEAKED" and "summary leaked = 1";
     - `death_signal_reverted` now also fails the cooperating run's INCONCLUSIVE assertion, because that run is LEAKED;
     - `scratch_kept` fails on the copy and the root not being removed.
4. *N6* is witnessed as above. The daemon was killed by the probe and shown dead. This gap is out of scope at L0 by item 3 and is discharged by item 5.

Also per A3 item 6:
- `registry` rows carry `proposer` (`kind`, `model`, `session`), from committed `harness/proposer.toml`;
- `poll_step_s` = 0.05 is committed in `harness/config.toml`, and every bounded wait uses it.

**L1 obligation (brief 0 A3 item 5, verbatim; not built):**
> Harness: every orchestrator process sets `PR_SET_CHILD_SUBREAPER`; children run one at a time, asserted; after every child run and before its scratch root is deleted, every remaining descendant is killed, repeating until none remain, and the count is recorded as `leaked_processes`; `leaked_processes > 0` is `LEAKED`. Fixtures: the cooperating grandchild; a non-cooperating grandchild (new session, no death signal, SIGTERM ignored, hanging past the timeout); a double-forked daemon from a clean check returning True. Mutants, each an anchored edit, each `KILLED` with a passing twin: subreaper not set; sweep skipped; `LEAKED` not counted; scratch kept. If `death_signal_reverted` then survives because the subreaper makes the death signal redundant, either pin a case only the death signal covers or remove the death signal and retire the mutant, recording why; no mechanism without a killed mutant. Judge: containers started by the judge are killed and removed on timeout, witnessed by a pin (P10) with a non-cooperating process inside the container that ignores SIGTERM; a candidate container alive after teardown is an episode with termination code `LEAKED`, counted, never dropped. Process-level sweeping does not reach containerd-shim children.

**Correction to the A3 correction.** It reported "0 harness processes" after the review-mutant re-run, including after review mutant 3. That probe matched only `harness (run|check)` command lines. This session found **13 live P0h grandchildren** (marker `assize-p0h-grandchild`), all spawned under `out/a3-witness/review/applied_to_original_tree/...` and alive about 95 minutes. Review mutant 3 writes edits into the shared tree, so P0h's `death_signal_reverted` edit took the death signal away from every later spawn in that run. All 13 were killed by hand before any run in this session. They are an instance of exactly the class that item 5 discharges at L1. Witness scripts from A4 onwards count processes by marker as well (`leftovers:` lines).

**Forecasts** (`reports/L0/forecasts.jsonl`, created before this session's first `make pins`):

| id | Claim | p | Outcome |
|---|---|---|---|
| `876d1d05c550` | pins green on the first CI run of this PR head | 0.80 | TRUE (run 37358542927) |
| `a30e37db1152` | fixture.escapee recorded LEAKED with leaked = 1 inside P0h on ubuntu-latest in that first CI run | 0.90 | TRUE (artefact rows) |
| `ed89fc300206` | reviewer verdict ACCEPT with no blocking finding | 0.45 | open |

Cumulative log-loss over the 2 resolved forecasts is 0.329 nats, against 1.386 nats for a base rate of p = 0.5.

**Witnesses** (`reports/L0/a4/`, regenerated by `witness.sh`; stamps show `cea5957`, `dirty=0`; zero `/tmp/assize-*` directories, zero harness processes and zero marker processes before and after each):

| Archive | SHA-256 | Compressed bytes | Uncompressed tar bytes | Files |
|---|---|---|---|---|
| `a4/make-pins-runs.tar.xz` | `7d398c8904ad61f24232c8621f1ac806ca7eda1692259889e622eff33f25dbeb` | 20,072 | 686,080 | 259 |
| `a4/escapee-fixture-runs.tar.xz` | `61ec61a4d41b26d709e52708535ca56a08f25d01023686d5e00f7f8a84a4aa18` | 368 | 10,240 | 2 |
| `a4/probes-runs.tar.xz` | `9f28ef78f5aa18895fb5127f2bfbde6eee1e1e19f7141c8e00db27f549ffa24d` | 1,228 | 20,480 | 8 |

Uncompressed alongside: `make-pins.txt` and `.jsonl`, `escapee-fixture.txt` and `.jsonl`, `probes.txt` and `probe-*.jsonl`, `pins-yml-run.txt`, `MANIFEST.txt`.

**A3 pre-stated criteria:**

| Criterion | Status |
|---|---|
| `make pins` passes with every mutant, including `P0h/leaked_not_counted`, KILLED with a passing twin | MET (local and CI) |
| the nested `fixture.escapee` run is LEAKED, leaked = 1, exit non-zero, and leaves no process and no scratch root | MET (P0h transcript in the archive; CI artefact; `a4/escapee-fixture.txt`) |
| N6 witnessed, daemon shown killed | MET (`a4/probes.txt`) |
| `pins` green on the PR head | MET at `f07330a`; re-checked on the report commit |
| A4, index line, `forecasts.jsonl`, `proposer`, `STATUS.md` exist | MET |

#### A4 note — 2026-10-05: host run of measure.yml witnessed
This discharges brief 0's "Guy confirms the host run of `measure.yml` after merge" with a witness instead of a manual confirmation. The L0 verdict is unchanged and no index line is added.
- **Trigger.** PR #2 was labelled `measure` on Guy's instruction, which ran `measure.yml` on head `744868f`: [run 37369883675](https://github.com/renavondata/assize/actions/runs/37369883675/job/111964119882), conclusion success, 2026-10-05T20:27:51Z → 20:29:58Z.
- **Runner.** `steel-legend`, labels `self-hosted, measure`, running as the unprivileged user `assize-runner`. `ASSIZE_HOST=measure` was set by the workflow, and `make measure` ran host facts, then `make pins`.
- **Host facts** (`a4/host/facts.txt`, SHA-256 `fcf096331c05bf98060ff3ec01fbab8abc661b872331d9483545d7241e006346`): AMD Ryzen 5 5600X, 6 cores / 12 threads; 31 GiB RAM, 23 GiB swap; Linux 7.2.6-arch2-1; uv 0.12.17; system Python 3.14.7. Pins ran on uv-managed Python 3.11.16. Podman 6.1.2 is rootless (`rootless=true`), and the `docker` command is Podman's Docker emulation.
- **Pins on the host** (`a4/host/make-measure.txt`, `a4/host/pins.jsonl`): clean 8/8 passed; mutants 10/10 KILLED, 0/10 survived, 0/10 inconclusive, 0/10 stale, 0/10 non-causal; 0 leaked; twins 10/10 passed; exit 0. That includes P0h with `fixture.escapee` and all three of its mutants. The `registry` row carries the `proposer`, and its `invocation_root` is the runner's work tree.
- **Per-child transcripts:** `a4/host/host-pins-runs.tar.xz`, SHA-256 `e483b1925e024470518b4f91c7577f3959d43c1722f97520389b14c092e4c55c`, 19,988 bytes compressed, 706,560 bytes as an uncompressed tar, 259 files (also in `a4/MANIFEST.txt`).
- **Same machine.** `steel-legend` is the machine on which the development-box witnesses of Addenda A2–A4 were produced: the same hostname and kernel. Those runs used Guy's user account and the session's tree, not the runner's account and checkout. Only this run is the host witness.
- These are pass/fail results. No timing in them is evidence for any verdict.
