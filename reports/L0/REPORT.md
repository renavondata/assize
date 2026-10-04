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
