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
