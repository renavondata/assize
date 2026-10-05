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
