# Claude Code brief 2 of 2 — NetHack binding and AutoAscend, judge untouched

**REPO:** same as brief 1.

## Precondition
Brief 1's `REPORT.md` must record SEALED. Read that report, the schema and the judge README before starting.

## Context
This session tests whether the interface built in brief 1 is genuinely World-agnostic. The judge and spec are frozen. NetHack must plug in through a manifest and a binding alone. If it cannot, that is the finding.

## 1. Zero-diff constraint
Make no changes to `judge/` or `worlds/spec/`.
- The pin compares both directories against brief 1's commit; the diff must be empty.
- If NetHack needs a schema or judge change, stop and report the minimal change required and why. Do not make it.

## 2. NetHack binding (`worlds/nethack/`)
**Versions.** Record the NLE and NetHack versions installed.

**Tasks.**
- Full game: NetHackChallenge.
- MiniHack ladder: the MiniHack task set BALROG uses, cited and committed.

**Observations.** Glyphs, message and bottom-line stats, declared in the manifest.

**Utility.**
- The per-episode utility is BALROG's progression metric.
- Vendor BALROG's implementation and its data tables at a pinned commit, with a checksum.
- Do not reimplement it.

**Prediction targets.**
- Declare a small set of next-step categorical targets with finite declared support, for example dungeon level, experience level and hunger state at t+1.
- Give the rationale and commit them before any run.
- No binning thresholds invented for continuous quantities.

**Determinism.** Running the same seed with the same action sequence twice must produce an identical trajectory hash.

## 3. Incumbents
**Random agent.** Reuse brief 1's random-agent image unchanged.

**AutoAscend.**
- Build a separate pinned image.
- Do not modify its strategy code.
- A thin adapter presenting judge observations in AutoAscend's expected format is permitted. Report its full diff.

**Version mismatch.** If AutoAscend requires a NetHack version different from the binding's:
- register it as a separate World variant with its own manifest;
- never pool its scores with the other version's.

If no adapter can make it run, stop and report.

**External references.** Published BALROG and NetHack Challenge numbers go in a separate table marked non-comparable.

## 4. Pilot, noise and time-to-learn
**Run limits.** Commit the pilot sizes and wall-clock cap before running. Defaults: 200 random episodes, and as many AutoAscend episodes as fit, within 3 hours total.

**Time-to-learn.**
- Use the same method as brief 1, applied to AutoAscend's per-episode progression.
- Report random-agent variance as well, but do not use it: it dies early and its variance is near-degenerate.
- Use δ ∈ {1, 2, 5} progression points.

## Pre-stated criteria (bind agent and Guy)
- **FIT** if δ = 2 is detectable within one day of compute on this hardware.
- **MARGINAL** if only δ = 5 is detectable.
- **UNFIT** otherwise.
- **Interface ACCEPTED** only if P1 passes.

## Pins (each must demonstrate it can fail)
- **P1 Zero diff.** A seeded edit to any file under `judge/` or `worlds/spec/` fails the diff check.
- **P2 Version pooling.** A mutant that pools AutoAscend episodes from two NetHack versions into one table fails the population check.
- **P3 Long-episode survivorship.** Episodes ending at the wall-clock cap are recorded with their termination code. A mutant that drops them fails the episode-count check.
- **P4 Vendored metric.** A mutant with one altered progression table entry fails the checksum.

## Refusal list
- No kernel, DSL, language-mixture, or wald/proplang/credence code.
- No LLM calls. No neural networks.
- No hand-written strategy beyond unmodified AutoAscend.
- No config changes after the first scored run.
- No edits to the judge or spec.

## Stop-and-report boundaries
Stop and report if:
- NLE, MiniHack or AutoAscend fail to install;
- the game is non-deterministic given a seed;
- the zero-diff constraint cannot be met;
- the cap is reached before the random pilot completes.

On completion, report:
- versions, manifests and configs;
- incumbent utilities with episode counts and compute per episode;
- predictive-floor log-loss;
- the time-to-learn table and throughput;
- the adapter diff;
- pin transcripts showing each kill;
- verdicts: FIT, MARGINAL or UNFIT, and ACCEPTED or REJECTED.

## Deliverables
- `worlds/nethack/` and `incumbents/autoascend/`
- additions to the README and `REPORT.md`

Commit locally; do not push.

---

## Amendment A1: cloud execution (appended; overrides earlier text where they conflict)
1. **Inherited amendments.** Brief 1's Amendment A1 items 2–6 apply here unchanged.
2. **AutoAscend source.** Vendor AutoAscend as a git submodule pinned to a named commit. If the cloud session cannot fetch it, stop and report.
3. **Measurement.** All pilots, including AutoAscend episodes, run only on the host via `measure.yml`. In the cloud, each incumbent runs at most 3 smoke episodes per World, with a step cap committed in config.
4. **Zero diff.** P1 (zero diff on `judge/` and `worlds/spec/`) compares against the merged L1 commit on `master`, not a local commit.

---

## Amendment A2: L1 exit carry-over (DRAFT, appended; overrides earlier text where they conflict)
Drafted by the Builder (session afb193a1-6114-4d73-87de-0b24f8570087) as the last deliverable of L1 (CLAUDE.md A1.10). It stands only on Reviewer approval under A1.4, and opens L2 only when Guy merges it.

### Precondition
`reports/L1/REPORT.md` records **SEALED** and **FIT** (host measure run 37831165785, judge_sha256 `28710725463f36b93123771ddcda4390e3b02f4ee15488b42834809929eda7ff`), and the root `REPORT.md` carries its L1 verdict line. Read that report, `reports/L1/review-*.md` and this amendment before starting.

### Purpose
L1 left 55 obligations on L2 (`reports/L1/REPORT.md`, *Obligations on L2*). Brief 2 §1 forbids any change to `judge/` or `worlds/spec/`, and CLAUDE.md freezes them after L2. Every obligation that needs a judge change therefore has to land before NetHack work starts, or never. Two facts make this binding:
- `judge/evaluate.py:33` hard-codes `WORLDS = {"crafter": ...}`, so adding NetHack as written edits the judge.
- Prices are per World in `judge/config.toml` (`[price.crafter]` only), so pricing NetHack edits it too.

As things stand, brief 2's zero-diff test would fail on its first NetHack commit, for reasons that are about the judge, not about NetHack.

### Scope and order
1. **L2a, judge carry-over.** Judge, harness and pilot obligations only, with no NetHack code and no NetHack name in `judge/` or `worlds/spec/`:
   - World discovery becomes data: the judge binds every `worlds/<name>/binding.py` that has a manifest, and prices each World from its manifest's committed `price` block, with the derivation in its rationale. Crafter's price moves there unchanged.
   - A1 item 4's zero-diff baseline becomes the merged L2a commit on `master`, not the merged L1 commit. The L2a merge is a layer-internal milestone that Guy merges, because it changes the court.
2. **L2b, NetHack.** Brief 2 §§2–4 as written, under the zero-diff pin against the L2a baseline.
3. **L2c, seal.** The judge is built as an image, released and pinned by digest:
   - the image carries `verify`;
   - P0b's scan (brief 1 A2 item 3) runs over the built image, not only the tree;
   - `judge/` and `worlds/spec/` enter `CODEOWNERS` (CLAUDE.md A1.1, entrenched, so Guy's).

### Pre-stated criteria added by A2
These join brief 2's criteria; none replaces one.
- Every OPEN obligation listed in `reports/L1/REPORT.md` is either discharged by a pin whose named mutant is KILLED with a passing twin, or is entrenched and listed as Guy's, with its fixture and mutant written out.
- P1 (zero diff) holds from the L2a baseline to the L2b head.
- The pilot runner and its config are hashed into every pilot report, beside `judge_sha256`.
- Brief 2's time-to-learn verdict is rechecked against the first non-random candidate's variance once one exists. Until then the random incumbent's variance is reported as a weak proxy and is not used, as brief 2 §4 already says.

### Pins added by A2 (each with its named mutant, KILLED with a passing twin)
- **P19 World discovery.** A fixture World directory with a manifest and a binding is bound with no judge edit; a directory without a manifest is refused. Mutant: `world_table_hardcoded`.
- **P20 Per-World price.** `evaluate()` refuses a World whose manifest commits no price. Mutant: `crafter_price_fallback`.
- **P21 Seal.** The released image's digest equals the one recorded in `REPORT.md`; its `verify` subcommand verifies a fixture ledger; P0b's scan of the image finds nothing. Mutants: `verify_omitted`, `image_imports_mutants`.
- Each pinnable obligation of L1 carries the pin and mutant `reports/L1/REPORT.md` names for it.

### Refusal list (added)
- No NetHack code, manifest or name under `judge/` or `worlds/spec/`, ever.
- No change to `judge/` or `worlds/spec/` after the L2a baseline.
- No edit to entrenched paths (`.github/`, `.claude/`, `CODEOWNERS`, `CLAUDE.md`). Obligations on them are drafted as text for Guy.

### Stop-and-report boundaries (added)
Stop and report if:
- any judge-touching obligation turns out to need NetHack-specific knowledge to discharge;
- the Crafter judge hash changes in a way the L2a diff does not explain;
- re-running the L1 pins after L2a gives anything other than all clean and all KILLED.

### Deliverables (added)
- L2a's pull request, with its pins.
- `reports/L2/REPORT.md` recording the baseline sha.
- The seal's image digest.
- A draft of brief 3 (A1.10).

---

## Amendment A3: the suite's own cost is measured, priced and tuned under the same law (appended)

### 1. Invariants (unchanged, restated so nothing below erodes them)
Every mutant KILLED with a passing twin. No STALE, INCONCLUSIVE, NON-CAUSAL or LEAKED in a clean run. A verdict that differs between two runs of the same tree and config is a flake, and a flake is a defect of the harness, recorded as such.

### 2. Measurement
- Every `pins.jsonl` run row records `wall_s` (wall-clock of the run) and, for pins with timed fixtures, `observed_s` for each timed event: how long the child actually took to die after the kill, how long the escapee actually held the scratch root, how long the non-cooperating grandchild survived the sweep, and so on. The summary row records the suite's total `wall_s` and the per-pin totals.
- The Reviewer's reproduction of `make pins` and the Builder's run are two samples of the same suite; any disagreement in verdicts is recorded as a flake in the review file.
- `STATUS.md` gains a line: `suite: wall <s> on CI (run <id>); slowest pins <name:s, name:s, name:s>; flakes <n>`.

### 3. Price
One second of suite wall-clock on CI is priced at the cycle latency it imposes: the Builder states the price in `harness/config.toml` as `ci_second_price`, in the same utility units as the compute price of A4 item 4, with the rationale (the number of PRs per day the suite bounds, given the tick interval and the review's reproduction). The price is committed before any tuning run and not revised after seeing results.

### 4. Waits are derived, not typed
Each timed wait in the fixture configs (`child_timeout_s`, `reap_grace_s`, the hold and hang durations) is set from the recorded `observed_s` distribution for that event: a stated upper quantile times a stated margin, both committed in config with rationale. The Builder may not lower a wait below what the recorded distribution supports. A wait with no recorded distribution keeps its current value until one exists.

### 5. Adoption of a faster configuration (the switch rule applied to the harness)
A candidate fixture config or job layout (including splitting `pins` into parallel CI jobs by pin family, each with its own orchestrator and sweep) is adopted only after it has run in shadow beside the incumbent for a stated number of PRs with zero flakes and all invariants held, and its priced wall-clock is lower. The first flake under the candidate reverts it and records why. The Builder forecasts, before the shadow period, the probability that the candidate survives it.

### 6. Pins
- P11 Timing recorded: a mutant that drops `wall_s` or `observed_s` from a run row is KILLED.
- P12 Wait floor: a mutant that sets a wait below the recorded distribution's floor is KILLED by a check that reads the distribution.
- The parallel-job layout, if adopted, carries a pin that a leaked process in one job is attributed to that job and fails it; seeded mutant: sweep disabled in one job only.

### 7. Host lock
`make pins` takes a host-wide lock (`flock` on a file under `$XDG_RUNTIME_DIR` or `/tmp`, keyed by host); a second invocation blocks until the first finishes and records `lock_wait_s` in its summary row. Pin: two invocations started together produce two clean runs with no spurious failure and one non-zero `lock_wait_s`; seeded mutant: lock removed, which must reproduce the P10 twin failure on the fixture.

### 8. No target
This amendment sets no duration target. The ledger decides what is fast enough: the priced wall-clock falls until the invariants or the recorded distributions stop it.

---

## Amendment A4: obligations carried from L1 into L2 (appended)
These are L2 items. Each becomes a pin with a seeded mutant unless marked otherwise.
1. Judge signing key: an encrypted copy of the judge's private storage is taken off the measurement host weekly by a scheduled job; a restore onto a scratch host is witnessed once, with the chain re-verified from the restored key. Mutant: backup job that writes an empty archive, KILLED.
2. Code-scanning alerts: at every layer boundary the Builder lists open alerts (`gh api repos/renavondata/assize/code-scanning/alerts?state=open`) and either disposes of each in the boundary STATUS or records it as an obligation. No pin; a boundary STATUS without this line is a defect of the STATUS.
3. Role credential separation: Builder and Reviewer jobs run under distinct runner users (or ephemeral runners), so a Builder cannot read a Reviewer's work directory or credential. Witness: a Builder job attempting to read the Reviewer user's home is denied by the OS. (see L1 obligation 55)
4. Instrument identity: `host_facts.sh` records a stable host id; the Reviewer never compares throughput or time-to-learn across hosts; a second measurement host, if added, carries its own verdicts.
5. P0m on CI: the real-branch check runs on CI with a full-depth clone (`fetch-depth: 0` in pins.yml, an entrenched change); the shallow-clone skip is removed. Mutant: shallow clone restored, KILLED by a pin that fails when the branch walk is skipped. (see L1 obligation 44)
6. Exemption entries: every exemption's sha is verified to be on the branch being checked; a stale entry fails the check. Mutant: verification skipped, KILLED. (see L1 obligation 32)
7. One-child-at-a-time: the orchestrator's single-child invariant has its own pin; seeded mutant runs two children concurrently, KILLED. P0i gains a variant that exercises the harness's verdict path rather than the fixture alone. (see L1 obligation 28)
8. Seal: when the judge image is first sealed, `judge/` and `worlds/spec/` enter CODEOWNERS (entrenched change) in the same pull request as the seal.
9. Housekeeping, in the first entrenched PR of L2: `actions/checkout@v5`, `actions/upload-artifact@v5`.
10. For brief 3, not L2: Thompson sampling over the program mixture as the seed policy.
11. Evil merges: a merge commit may be attributed by its author account (A9), but may not change an entrenched path relative to both of its parents. P0m gains that check; seeded mutant: evil merge accepted, KILLED.
12. Signatures: a commit attributed to guy must verify (`git verify-commit`) against a key listed in an entrenched `allowed_signers` file; GitHub's own merges verify against its web-flow key. Seeded mutant: an unsigned guy-attributed commit accepted, KILLED.
13. STATUS monotonic: no merge replaces `reports/L*/STATUS.md` with one whose header date is older. A pin checks master's STATUS is the newest-dated in history; seeded mutant: an older STATUS carried over, KILLED.
15. Everything the L2c image build needs (Containerfile, entrypoint, the `verify` subcommand) is in place by the L2a baseline or lives outside `judge/` and `worlds/spec/`, so the seal changes nothing under them.

---

## Amendment A5: forecasts are aggregated by the switch rule (appended)
1. Forecasters are entrants: the Builder's own probability; a pooled base-rate forecaster over all resolved claims; a per-claim-type base-rate forecaster; any entrant a later Builder adds under this amendment. Each is a function from the ledger's history to a probability, computed only from resolutions that preceded the claim.
2. The scored forecast for a claim is the Hedge aggregate over entrants, weights proportional to exp(−η × cumulative log-loss on prior resolutions), η = sqrt(8 ln N / T) with N entrants and T prior resolutions (η = 1 before the first resolution). The Builder's p is recorded beside it; nothing else about it is required.
3. STATUS reports each entrant's weight and cumulative log-loss.
4. Pin P16: on a fixture ledger where one entrant is consistently worse, its weight must fall below the others'; seeded mutant: fixed equal weights, KILLED. A second mutant that lets an entrant see the resolution of the claim it is forecasting must be KILLED by a fixture where that leak would make it perfect.
5. Only the aggregator produces a scored forecast; a static scan (as P0b) finds no other writer of the scored field. Seeded mutant: an entrant writing it directly, caught.
14. A NEEDS YOU in a STATUS whose header names the PR that carried it to master is satisfied by that merge; a Builder on master treats it as `none`. Before filing an issue, a Builder fetches master again and re-reads STATUS; an issue is filed only against the current head.

## Audit findings at 8aae43c8c792

1. Elected Auditor model not constrained to differ from Builder's and Reviewer's. Criterion: Amendment 2, "a fresh session on a model different from both the Builder's and the Reviewer's". At harness/ledger.py:585, harness/entrants.toml:5-7. Pin: elect audit excludes the audited history's build and review models and refuses when none remains (needs at least three audit entrants). Mutant: `elect_ignores_exclusions`.
2. Concurrency drops queued build/review runs and failed.yml ignores zero-step cancels. Criterion: 3. "Every exit routes somewhere: every way a session or job can end produces a pull request, an issue assigned to Guy, or a labelled PR state". At .github/workflows/build.yml:11, review.yml:17, failed.yml:21-23. Pin: a cancelled zero-job run whose trigger has no later successful run is reported. Mutant: `cancel_zero_step_ignored_for_unserved_trigger`.
3. failed.yml does not watch measure, stale, or pins on master. Criterion: 3 (as above). At .github/workflows/failed.yml:4. Pin: every workflow is listed in failed.yml or in a stated exemption list. Mutant: `measure_unlisted`.
4. No list of the trusted base. Criterion: 7. "Monotone trusted base: the set of things outside every loop is listed and has not grown since the last audit". At CLAUDE.md:146. Pin: committed list compared with the live set of secrets, runner labels, tokens, workflows and CODEOWNERS paths. Mutant: `unlisted_secret_added`.
5. judge/scoring.invalid never checks 0<=p_i<=1; negative loss and a judge crash are reachable. Criterion: 2. "The law names scores and competitions, never competitors". At judge/scoring.py:44. Pin: fixture replies [1.5,-0.5] and [-0.5,1.5] end the episode invalid_reply with no negative loss and no exception. Mutant: `range_check_removed`.
6. P20's schema half has no mutant. Criterion: 1. "Every check kills a mutant". At harness/pins.py:2106. Pin: P20 mutant on the schema. Mutant: `schema_price_optional`.

## Wish #80 — Amendment: the chooser is validated by switchback (appended; instruction #111 Part C)

### Pre-stated criterion
A switchback across three regimes: (i) fixed order; or (ii) the chooser of Draft "The next item is the forecast of Guy's pick, acted on and overturnable". The schedule is fixed by a seeded hash of the ledger head at this amendment's merge, alternating per choice and committed before the first scored choice. All four outcomes are reported per regime, with denominators: guy-items per merged item; overturn rate stratified by exposure (`seen` vs unexposed, void counted); wish-to-merge latency; and the log-likelihood ratio of the mixture against `fixed-order` on resolved `guy_picks`, with its evidence bound stated from the α of the chooser's draft.

### Constants, pre-stated here
k (probes per boundary brief) = 2. Switchback length = the remainder of the layer.

### Pin
The switchback schedule recomputed from the committed seed equals the regimes recorded in STATUS `chose:` lines. Mutant: the regime chosen after the seed is seen. KILLED.

A regime with no resolved outcome is reported as such and never dropped. Nothing is tuned after scores are seen.

## Wish #134 — Amendment: a full pins run takes minutes, on our own hardware (appended; instruction #136)

### Purpose
A full `pins` run (every harness change forces one, since #108) took 29 of its 30 minutes on `ubuntu-latest` (run 38225369452). It is run serially on one hosted core. Run it in parallel on a self-hosted runner so it finishes in minutes, and so several Builders' pull requests can be checked at once.

### Scope
1. `harness/runner.py` runs pins in parallel across N worker processes, one pin per worker at a time, each in its own scratch copy as now. Results are written in registry order whatever order the workers finish in, so a run's record is byte-identical for every N. N is read from `harness/config.toml`, a constant committed before the first parallel run. Following A3 §5 it is adopted only if the parallel configuration beats the serial one on the switch rule; it is not tuned by sight.
2. `.github/workflows/pins.yml` runs on `[self-hosted, pins]` instead of `ubuntu-latest`. It keeps the isolation of CLAUDE.md's container rules (rootless Podman, `--network=none`, read-only, no judge mounts). The runner is a fresh checkout per job and is never the `measure` host's runner, so pins never contend with a measurement.
3. `ledger price` reports pins wall-clock per run alongside pins CI minutes.

### Pre-stated criteria
- Record identity: the full registry run with N=1 and N=8 on the same head gives byte-identical records, verdicts included.
- Speed: on the self-hosted runner, the median wall-clock of the full run over the first ten full runs after adoption is at most one fifth of the median of the last ten full runs on `ubuntu-latest`, read from `ledger price`. Failing that, the amendment is recorded UNFIT and `pins.yml` returns to `ubuntu-latest`.

### Pins (each must demonstrate it can fail)
- P-par: the runner on the synthetic registry with N=1 and N=4 must give identical records. Mutants, each KILLED: records in completion order; two workers sharing one scratch copy; a worker's crash dropped instead of recorded `inconclusive`.

### Refusal list
- No pin is skipped, sampled or reordered in the record to gain speed; #108's witness-based skipping is the only skipping.
- No runner shared with `measure`.

### Stop-and-report boundaries
- The self-hosted `pins` runner is not registered: stop and record it under `NEEDS YOU` (runner registration is Guy's alone).
- A pin that passes serially and fails in parallel: stop and report it as a hidden shared state, do not serialise it quietly.

### Deliverables
Runner change, workflow change, P-par, a `ledger price` transcript for each criterion. The third part of the wish, several Builders at once, is draft #67 (wish #61) and depends on this amendment and on the split of shared files drafted beside it.

## Wish #138 — Amendment: claude-fable-5-1 enters the build election (appended)

### Precondition
The pull requests closing #135 (each pull request writes its own STATUS, forecasts and proposer rows) and #136 (parallel pins on our own hardware) have both merged. Until then this item is not a candidate: `claims next` skips it and names the precondition it is waiting on.

### Purpose
Guy asked for Fable in the build election once shared-file conflicts and slow pins no longer make a Builder session expensive to lose. The Haiku and Fable entries for review, audit and vizier, and the per-model price line, are the instruction drafted beside this amendment.

### Scope
1. `harness/entrants.toml`: `build` becomes `["claude-opus-5-5", "claude-sonnet-5-5", "claude-fable-5-1"]`. Nothing else in the file changes.
2. `claims next` reads this amendment's precondition from the merge state of the two named pull requests, not from a guess.

### Pre-stated criteria
- After the change, `python -m harness.ledger elect build` on a synthetic ledger with no Fable draws gives Fable EXP3's uniform starting probability.
- From the first Builder session that draws Fable, the per-model price line (the beside instruction's item 3) reports its sessions, minutes and cost.

### Pins (each must demonstrate it can fail)
- P0aa gains a case: this item, with either named pull request unmerged, is skipped and the skip names the precondition. Mutant, KILLED: the precondition ignored (the item taken while #136 is open).

### Refusal list
- No model is named in a workflow; the election draws it.
- No weight, prior or head start for Fable: it enters as every entrant does.

### Stop-and-report boundaries
- If the per-model price line has not merged when the precondition is met, stop and report: the wish asks that the cost be readable.

### Deliverables
The entrants change, the P0aa case, and an `elect build` transcript.

## Wish #173 (appended; instruction #174)

1. When the elected model for a procedure is unavailable (a usage limit, or a refusal to start, as in review run 38374009672), the session re-runs at once with a fresh draw from `python -m harness.ledger elect <procedure> --seed <new run id>`. The unavailable model is excluded from that draw for the rest of the run. At most one re-run per run id.
2. The unavailable round is itself a forecast of the elected model that resolves 0 (did not run), with proposer kind `mechanism`, under the same proper log score as every other typed forecast of that model. No new constant: the loss is the one the election already uses.
3. Witnesses: a pin in `harness/pins.py` fails a mutant that drops an unavailable round unscored, and a pin fails a mutant that re-runs with the same draw. Both must be KILLED before the amendment is in force.
4. Price quantity: re-runs per week and runner-minutes spent on unavailable rounds, reported on the STATUS price line (P0t). Expected direction: both fall to zero once the election has learned to avoid the unavailable model.

## Wish #179 (appended; instruction #181)

### Purpose
L2 reaches the seal sooner. A2's criterion "Every OPEN obligation listed in `reports/L1/REPORT.md` is either discharged by a pin whose named mutant is KILLED with a passing twin, or is entrenched and listed as Guy's" is narrowed for obligations 44–55 (*Process, git and CI*) only. Obligations 1–43 stay under A2 as written.

### Scope
1. For each of L1 obligations 44–55, the Builder records one row in `reports/L2/obligations-44-55.md`: the obligation number, and exactly one disposition:
   - `discharged by <pin> (<instruction or amendment that added it>)`, citing a mutant of that pin that is KILLED with a passing twin in a cited `pins` CI run on master, and one sentence saying why that mutant is the obligation's failure; or
   - `carried to the agent repository as a design input`, with one sentence stating the input.
2. A2's criterion counts an obligation of 44–55 as met by either disposition. Nothing in 1–43 changes, and no obligation of 44–55 needs a new pin under A2.
3. Candidates the Builder checks first, not dispositions (the Builder decides each against item 1): 44 → P0m (real branch in CI, full clone); 45 → P0w and Wish #134's amendment; 49 → P0s (base rates per type); 50 → P0k and P0r; 52 → P0m (merge authors) and P0y; 53 → P0ab; 54 → P0v, P0aj, P0aw; 55 → A4 item 3. Where the cited pin covers only part of the obligation, the remainder is carried, not discharged.

### Pre-stated criteria
- Each of 44–55 has exactly one row; none is missing, none has both dispositions.
- Every `discharged` row names a pin present in `harness/pins.py` at master, a mutant of it, and a `pins` CI run on master in which that mutant is KILLED with a passing twin.

### Pins (each must demonstrate it can fail)
- A check in `harness/claims.py`, run by an existing P0 pin's clean case, reads `reports/L2/obligations-44-55.md` and fails on a missing number, a row with both or neither disposition, or a `discharged` row naming a pin or mutant absent from the registry. Mutant, KILLED: the registry lookup skipped (a row citing a nonexistent pin passes).

### Refusal list
- No change to the disposition or criterion of obligations 1–43.
- No edit to entrenched paths for this item.
- No obligation is dropped: carrying it is a row, not an omission.

### Stop-and-report boundaries
- An obligation of 44–55 whose cited pin's mutant is not KILLED on master: carry it, and say so in STATUS.

### Deliverables
`reports/L2/obligations-44-55.md`, the check and its mutant, and the CI run cited.

## Wish #74 (appended; instruction #284)

The next item a Builder takes is chosen by forecast value: gate progress and price quantities moved per session, against Guy's stated budget and priorities. That choice is itself a scored forecast.
A1.5's fixed order (instructions, then STATUS next, then brief file order) remains the default until a scored choice exists.
Pre-stated criterion: a chooser that loses to the fixed order on resolved choices is not elected.
Constitution note: replacing A1.5's order is a CLAUDE.md change and needs a `constitution` pull request; this draft asks only for the scored default and the pin that witnesses it.
Pin that can fail: a chooser that departs from the fixed order with no recorded forecast fails the pin.

## Wish #69 (appended; instruction #286)

A draft that changes how work is done states, in its body, the price quantity it expects to move and a forecast of the size of the move, as a pre-stated criterion. A draft that names no price quantity says so and is labelled recording-only.

Pre-stated criterion: `claims.draft_findings` refuses a process-changing draft with no `price` line, and accepts a recording-only draft that says so.

Pin that can fail: a process-changing draft with no `price` line is accepted by a mutant; the pin must fail on that mutant.

## Amendment A3: the seal precedes NetHack (appended; instruction #303)

1. The zero-diff pin (brief 2 A1 item 4, as A2 amends it: zero diff on `judge/` and `worlds/spec/` against the L2a baseline) is built first, before anything else. It is the first item. Its registry id is whatever the registry assigns (PR #301 proposes P35, since registry P1 is the CSPRNG pin); the name "P1" in A1 and A2 means this pin.
2. L2c follows immediately: the judge image is built from the baseline's `judge/`, released, and pinned by digest; `judge/` and `worlds/spec/` enter CODEOWNERS; `reports/L2/REPORT.md` records the digest and the Crafter host verdict under the sealed image (a host `measure` run, as in L1). This is a layer-internal milestone that Guy merges, like the L2a baseline.
3. L2b then proceeds under the sealed image. NetHack is a World binding and manifest only (`worlds/<name>/binding.py` plus manifest, per A2). The zero-diff pin and the released digest stay as they are. A NetHack change that would need an edit to `judge/` or `worlds/spec/` is a stop-and-report boundary, not a reason to re-seal.
4. The L2 verdict line in the root `REPORT.md` is written when item 3 is done, as the ladder requires. The agent repository may use the sealed image from item 2 on.

CLAUDE.md's ladder does not change. L2's exit gate still requires the zero diff, a NetHack verdict on the host, the released image and the freeze. Only the order inside L2 moves, from L2a → L2b → L2c to L2a → L2c → L2b.

## Admitted by instruction #315

- CODEOWNERS `/judge/ @gfrmin`
- CODEOWNERS `/worlds/spec/ @gfrmin`

## Wish #341: L2 ends at L2c (appended; instruction #342)

Brief 2 §§2–4, A2's L2b scope and A3 item 3 are carried, not done.

A3 item 4 now reads: "the L2 verdict line in the root `REPORT.md` is written when L2c is done".

Carried items, listed in tracking issue #344: wishes #302, #300, #209, #208, #179, #173, #138, #134, #125, #103, #97, #86, #62, #61, #59, #58; drafts #304, #282, #280; NetHack issue #329 and pull requests #333 and #325.

## Admitted by instruction #342

- workflow `release.yml`
- token `release.yml github.token`

## Admitted by instruction #356

- token `measure.yml github.token`
