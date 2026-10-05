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
