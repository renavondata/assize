# Claude Code brief 1 of 2 — Generic interface, sealed judge, Crafter

**REPO:** `<Guy to fill>`
**HARDWARE:** `<Guy to fill: CPU, cores, RAM, OS>`

This brief supersedes `cc-brief-worlds-and-sealed-judge.md`. Brief 2 (NetHack) runs only after this one reports SEALED.

## Context: why this exists
A Bayesian agent kernel will later improve itself autonomously. Coding agents will propose new candidate agents, and this judge will decide adoption with no human in the loop. The judge will be called thousands of times by unattended scripts. It is frozen and signed by Guy. Nothing a candidate does may read, influence or bypass it.

The judge scores two things:
- **Decisions**, by per-episode utility on fresh, never-issued seeds.
- **Predictions**, by log-loss on predictions the candidate commits before the next observation exists.

It also measures each candidate's compute, because compute is priced in utility. This session builds the judge, the interface and one World. It writes no agent.

## Tooling
- Linux host; Python ≥ 3.11 managed with `uv`; rootless Podman for candidate isolation.
- No cloud services, no LLM calls, no neural networks.
- If rootless Podman is unavailable, stop and report.

## 1. Interface (`worlds/spec/`)
Use JSON-RPC 2.0 over stdio between the judge and the candidate container. Write JSON Schema files carrying a `schema_version`.

**The schema is generic and typed.** All World vocabulary lives in a per-World manifest as data, never in the schema. The manifest declares:
- observation fields (name, type, shape, finite vocabulary where categorical);
- the action set;
- prediction targets (name, finite categorical support).

**Per step,** the judge sends `{t, observation, legal_actions}`. The candidate replies `{action, prediction?}` in a single message, where `prediction` maps declared targets to distributions over their declared support. Only then does the World advance. The candidate never receives seeds.

**Episode boundaries** use `begin_episode` and `end_episode`. `end_episode` carries the termination code and the final utility. No seed is sent at either boundary.

## 2. Sealed judge (`judge/`)
- **Process separation.** The judge runs as its own process and owns the World instances.
- **Isolation.** Candidates run as Podman images with:
  - `--network=none`
  - a read-only root
  - no mounts of judge paths
  - CPU and memory cgroup limits from committed config
  - per-step and per-episode wall-clock timeouts from committed config
- **Seeds.** Evaluation seeds come from a CSPRNG, are logged only in judge-private storage, and are checked against all previously issued seeds before use. A public training-seed stream is domain-separated, and its disjointness is checked.
- **Terminations.** Every episode is recorded, including crashes, timeouts and invalid actions, each with a termination code. None is ever dropped.
- **Measured compute.** For each episode, the judge records the candidate container's CPU seconds, wall-clock time and peak memory, taken from cgroup accounting. Self-reported figures are never used.
- **Prediction scoring.** Log-loss is scored per declared target per step. Zero probability on the realised outcome is recorded as +∞ and counted, never clipped. A missing prediction is recorded as missing, never imputed.
- **API.** `evaluate(candidate_image_digest, world, n_episodes, request_id)` is non-interactive and idempotent per `request_id`. It writes append-only JSONL. Each record carries `schema_version`, a hash of the judge's code and config, and the candidate image digest.

## 3. Crafter binding (`worlds/crafter/`)
- **Observations.** Use the `crafter` package's semantic map and inventory. Image observations are out of scope. If symbolic observation is unavailable, stop and report.
- **Episode length.** Use Crafter's default.
- **Utility.** The per-episode scalar is the count of distinct achievements unlocked; also record the achievement set. Report Hafner's (2022) aggregate score separately; do not use it as the per-episode utility.
- **Prediction targets.** Declare a small set of next-step categorical targets, with rationale, committed before any run. An example is each inventory count at t+1, with its declared range.
- **Determinism.** Running the same seed with the same action sequence twice must produce an identical trajectory hash.

## 4. Incumbent and predictive floor
Package a random agent (uniform over legal actions) as a candidate image, so the whole path is exercised. Its predictions are unigram frequencies of each target from its own past observations. This is the predictive floor.

## 5. Pilot, noise and time-to-learn
**Run limits.** Commit the pilot size and a total wall-clock cap before running. The defaults are 200 episodes and 2 hours, whichever binds first.

**Time-to-learn.**
- Use a Bayesian bootstrap over the incumbent's per-episode utilities.
- Assume a candidate distributed as the incumbent shifted by δ ∈ {0.25, 0.5, 1} achievements per episode, and state this assumption in the report.
- Report the episodes per arm needed for 90% posterior mass on the correct sign of the difference.
- Convert that to wall-clock time using measured throughput.
- Note that a random agent's variance is a weak proxy for that of a competent agent.

## Pre-stated criteria (bind agent and Guy)
- **FIT** if δ = 0.5 is detectable within one day of compute on this hardware. **MARGINAL** if only δ = 1 is. **UNFIT** otherwise.
- **SEALED** only if all pins below pass.
- **Interface PROVISIONAL.** Full acceptance is decided by brief 2's zero-diff test.

## Pins (each must demonstrate it can fail)
- **P1 Seed reuse.** An evaluator mutant reissues a used seed. The issuance check fails.
- **P2 Peek.** A candidate attempts to read judge paths and to open a network socket. Both are denied by the OS or container, not by convention.
- **P3 Survivorship.** A crashing candidate's episodes are recorded with termination codes. A mutant that drops them fails the episode-count check.
- **P4 Measured compute.** A candidate busy-loops for a known CPU duration and self-reports zero. The judge's measured CPU must be at least the known duration. A mutant that uses self-reports fails.
- **P5 Commitment order.** A clairvoyant candidate predicts the next observation using any leaked information. On the clean judge it gains nothing over the floor. On a mutant judge that sends the next observation early, it scores near zero log-loss. The suite must distinguish the two.
- **P6 Schema purity.** A mutant adds a Crafter field name to the schema. A static check fails it: no manifest vocabulary token may appear in the schema files.
- **P7 Infinite loss.** A candidate puts zero mass on a realised outcome. The judge records +∞. A clipping mutant fails.

## Refusal list
- No kernel, DSL, language-mixture, or wald/proplang/credence code.
- No hand-written game strategy.
- No changes to the pilot config, caps or prediction targets after the first scored run.
- No rootful containers.

## Stop-and-report boundaries
Stop and report if:
- Podman isolation cannot be demonstrated;
- Crafter is non-deterministic given a seed;
- any pin cannot be made to fail;
- the cap is reached before the pilot completes.

On completion, report:
- the schema and manifest;
- committed configs;
- the judge hash;
- random-agent utilities with episode counts, the predictive-floor log-loss, and compute per episode;
- the time-to-learn table and throughput;
- pin transcripts showing each kill;
- verdicts: FIT, MARGINAL or UNFIT, and SEALED or NOT SEALED.

## Deliverables
- `worlds/spec/`, `worlds/crafter/`, `judge/` and `incumbents/random/`
- a README with exact run commands, and `REPORT.md`

Commit locally; do not push.

---

## Amendment A1: cloud execution (appended; overrides earlier text where they conflict)
1. **HARDWARE.** The measurement host is the self-hosted runner labelled `measure`, which records its own hardware. Delete the placeholder.
2. **Isolation.** Replace "rootless Podman" throughout with an OCI runtime abstraction:
   - Docker in the cloud session, with `--network=none`, `--read-only`, no judge mounts and cgroup limits;
   - rootless Podman on the host.
   P2 must pass under both. A cloud pass does not witness the host. Replace "If rootless Podman is unavailable, stop and report" with: "If P2 cannot be demonstrated under Docker in the cloud, stop and report; the host run happens via `measure.yml`."
3. **Measurement.** §5 (pilot, noise, time-to-learn) runs only via `make measure` in `measure.yml` on the host. In the cloud, run `make smoke` with at most 10 episodes. Never report cloud-VM numbers as evidence for FIT, MARGINAL or UNFIT. The session's report states the verdict as PENDING HOST, and Guy triggers `measure.yml`.
4. **Long commands.** Never run a command expected to exceed 10 minutes in the session.
5. **Git.** Replace "Commit locally; do not push" with: "Push to a feature branch and open a pull request; never merge."
6. **Pins.** Register all pins with the L0 harness so that `make pins` runs them with their mutants.

---

## Amendment A2: mutation hygiene (appended; overrides earlier text where they conflict)
1. **Patch mutants only.** Every mutant targeting code under `judge/`, `worlds/` or `incumbents/` uses the harness's patch selector. No mutant switch, environment flag or test hook may exist in that code.
2. **New pin P8, no switches shipped.** The judge entrypoint refuses to start, with a non-zero exit, if `ASSIZE_MUTANT` or any variable prefixed `ASSIZE_TEST` is set.
   - The check starts the judge with each variable set and must observe refusal.
   - A patch mutant that removes the refusal must make P8 fail.
3. **Static check.** A static scan of the built judge image finds no reference to `harness.mutants`. A patch mutant that adds one must be caught.

---

## Amendment A3: follows from brief 0 A2 (appended)
1. **Mutants.** Mutants are anchored edits applied to a disposable copy (brief 0 A2). No environment switch exists anywhere in the repository.
2. **P8 replaced.** A2 item 2 (P8, the judge refusing to start if `ASSIZE_MUTANT` is set) is replaced by brief 0's P0b static scan, extended to the built judge image. A2 items 1 and 3 stand.

---

## Amendment A4: ledger integrity, proposers, calibration, process hygiene (appended; overrides earlier text and A1–A3 where they conflict)

### 1. Tamper-evident ledger
- Every judge record carries `prev_sha256`, the SHA-256 of the previous record's canonical serialisation (sorted keys, no whitespace), and `sha256`, its own. The first record of a request chains from the request's `request_id`.
- After every `evaluate()` call the judge writes the chain head to judge-private storage, signed with a key the judge generates on first start and never exports. Verification recomputes the chain and checks the signature; it is a judge subcommand and a pin.
- **P9 Ledger tamper.** Three mutants, each an anchored edit, each KILLED with a passing twin: one record dropped; one record's `utility` altered after writing; chain update skipped. Verification must fail each.
- Records are append-only at the file-system level as well: the judge opens the ledger `O_APPEND` and never seeks. A mutant that opens it for rewrite must be caught by P9's second case.

### 2. Proposer
Every judge record, every candidate registration and every pilot report carries `proposer: {kind, model, session}` for the party that submitted the candidate image. The judge takes `proposer` from the credential that registered the image, never from a file the candidate shipped; a candidate with no attributable proposer is refused at registration, witnessed by a pin.

### 3. Calibration beside log-loss
For each declared prediction target, report alongside log-loss a reliability table over the declared support (predicted probability bins against realised frequency, with counts) and the mean predicted entropy. Nothing is pooled across targets or Worlds. Overconfidence shows as +∞ and in the reliability table before it shows in utility; that is the point.

### 4. Compute priced before scoring
"Compute is priced in utility" needs an exchange rate. Commit, before the first scored run, the price of one CPU-second and of one gigabyte-second of peak memory in units of the World's per-episode utility, in config, with the rationale. The L5 adoption criterion (utility minus priced compute, on fresh seeds) is undefined without it, and must not be tuned after a score is seen.

### 5. Process hygiene (obligation from L0, brief 0 A3 item 5)
- Harness: every orchestrator sets `PR_SET_CHILD_SUBREAPER`; children run one at a time, asserted; after every child run and before its scratch root is deleted, every remaining descendant is killed, repeating until none remain, with the count recorded as `leaked_processes`; any run with `leaked_processes > 0`, or a scratch root still held after the sweep, has verdict LEAKED, counted, failing the suite. Fixtures: the cooperating grandchild; a non-cooperating grandchild (new session, no death signal, SIGTERM ignored, hanging past the timeout); a double-forked daemon from a clean check returning True. Mutants, each KILLED with a passing twin: subreaper not set; sweep skipped; LEAKED not counted; scratch kept. If `death_signal_reverted` then survives, either pin a case only the death signal covers or remove the death signal and retire the mutant, recording why.
- Judge, **P10 Container teardown.** A candidate container holding a process that ignores SIGTERM is killed and removed on timeout, witnessed by the container runtime listing nothing afterwards, under both runtimes. A candidate container alive after teardown is an episode with termination code LEAKED, counted, never dropped. A mutant that skips removal must fail P10.

### 6. Scope and order
Item 5 (harness) is built first in this layer, before any pilot, because leaked processes on the measurement host contaminate throughput and therefore every time-to-learn figure. Pilots run only after the harness half of item 5 is witnessed on the host via `measure.yml`.

### 7. Obligations from the L0 review (copy verbatim)
Copy, word for word, the three OBLIGATION findings F2, F3 and F4 from `reports/L0/review-5e81d054f56ccbc59f0c1799f9438368ab80d086.md`, each with its pin and mutant as the reviewer wrote them, as items 7a, 7b and 7c. Do not rephrase them.

7a. F2: Forecast resolution records do not have the A1.6 shape. The Builder's two resolutions use `{"resolves", "ts", "outcome", "evidence"}` with no `proposer` and no `id`, and the Builder resolved its own forecasts, which A1.6 assigns to the Reviewer. — severity: OBLIGATION on L1. Pin: a ledger validator in `make pins` rejects any `forecasts.jsonl` resolution row that lacks `id`, `ts`, `proposer` or `outcome`, or whose `id` matches no forecast. Mutant: an anchored edit that drops the `proposer` check must be KILLED by a fixture ledger carrying a proposer-less resolution. — witness: reports/L0/forecasts.jsonl (rows 4–5)

7b. F3: CI claims are not bound to the head they describe. STATUS.md (`7697a05`) reports "pins.yml green (f07330a)" and a PASSED verdict. Its own head and the PR head `5e81d05` both have red `pins` runs, and STATUS does not say so. — severity: OBLIGATION on L1. Pin: STATUS.md and every layer verdict line cite the `pins` run by run id and head sha; a checker rejects a verdict whose cited run's `head_sha` differs from the sha the STATUS names, or whose conclusion is not `success`. Mutant: an edit that skips the sha comparison must be KILLED by a fixture STATUS citing a run on an older sha. — witness: reports/L0/STATUS.md; reports/L0/review/5e81d054f56ccbc59f0c1799f9438368ab80d086/ci-runs.txt

7c. F4: The proposer of a commit cannot be recovered from git. Every commit on the branch is authored `Guy Freeman`, including session commits, so `5177756` (the only change to `CLAUDE.md` in this PR: `main` → `master`, "on Guy's instruction") cannot be attributed from git alone to Guy or to a session. The PR touches entrenched paths (`CLAUDE.md`, `.github/`), so Guy's merge disposes of it. This review does not find a violation. — severity: OBLIGATION on L1. Pin: every commit on a PR branch carries a `Proposer: <kind> <model> <session>` trailer (A1.7), and a check fails any commit touching an entrenched path whose trailer is not `guy`. Mutant: an edit that disables the trailer check must be KILLED by a fixture commit to `CLAUDE.md` with a `builder` trailer. — witness: `git log --format='%h %an | %s' master..5e81d05 -- CLAUDE.md`

### 8. Host facts
`scripts/host_facts.sh` additionally records `uptime` (load averages), the runner's pinned CPU set (`cat /sys/fs/cgroup/user.slice/user-$(id -u).slice/cpuset.cpus.effective`), the runner version from `~/actions-runner/.runner` or `./config.sh --version`, and the output of `podman info --format '{{.Host.OCIRuntime.Name}} {{.Host.CgroupsVersion}} {{.Host.CgroupManager}} rootless={{.Host.Security.Rootless}}'`. A measurement whose facts lack any of these is not a measurement.

### 9. Pre-stated criteria added by A4
P9 and P10 KILLED with passing twins; the harness half of item 5 witnessed on the host before the first pilot; the compute price committed before the first scored run; every judge record carrying `proposer` taken from the registering credential; the three item-7 pins present with their mutants KILLED. These join brief 1's existing criteria; none replaces one.

---

## Amendment A5: PR #5 review obligations brought into L1 (appended; overrides earlier text where they conflict)
- F1 (stale bytecode): done within A4 item 5's harness work, before any pilot. The harness copy excludes `__pycache__` at every depth, and every child Python process runs with bytecode reading and writing disabled (`-B` and `PYTHONDONTWRITEBYTECODE=1`). Pin: a mutant whose edit preserves byte length and lands in the same second as the source's recorded mtime is KILLED. Seeded mutant: restore the top-level-only exclude; the pin KILLS it with a fixture that compiles a module, then applies a same-length edit within the same second.
- F4 (§1 chaining): the first record of a request has `prev_sha256` equal to the SHA-256 of the request's `request_id` as UTF-8 bytes. P9's verifier rejects a first record chaining from the empty string; seeded mutant: a first record with `prev_sha256` of "" must fail verification.
- F2 (trailers): the item-7c checker reads every `Proposer:` line of a commit, one party per line, per CLAUDE.md A1.7 as amended; seeded mutant: a checker that reads only the first line, KILLED by a fixture commit with two parties whose second party must be reported.
- F3 is discharged by CLAUDE.md A1.3 as amended; no brief text.
