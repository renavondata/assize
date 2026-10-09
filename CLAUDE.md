# assize — constitution

This repository is the court: the World bindings, the interface, the sealed judge and the reference incumbents. No agent under evaluation may live in, import from, or write to this repository. Agents live elsewhere and are judged by a released judge image pinned by digest.

Guy Freeman holds all signatures. This file, branch protection, repository settings and runner registration are his alone to change. Files under `.github/` may be created or edited only under a brief that names them.

## Layer ladder
Each layer is built on the one below. A layer starts only after the previous layer's exit verdict is recorded in `REPORT.md` and Guy has merged it. Lower layers freeze when the next layer begins; upper layers never relitigate them.

| Layer | Where | Content | Exit gate |
|---|---|---|---|
| L0 | here | Scaffold, pin harness, CI split | Harness kills its own mutant; CI red on every seeded mutant |
| L1 | here | Interface, sealed judge, Crafter (`docs/briefs/brief-1-judge-and-crafter.md`) | SEALED; Crafter FIT/MARGINAL/UNFIT measured on the host |
| L2 | here | NetHack, AutoAscend (`docs/briefs/brief-2-nethack.md`) | Interface ACCEPTED by zero diff; NetHack verdict on the host; judge released as a digest-pinned image; repo frozen |
| L3 | agent repo | Crude seed agent: within-episode conditioning, program mixture over a tiny seed language | Beats random on held-out seeds in both Worlds; beats the predictive floor |
| L4 | agent repo | Language as action: library learning with the dominance pin | At least one agent-adopted language change with post-entry gain |
| L5 | agent repo | Adoption by sequential EU; provenance ledger | Adoption decisions made without Guy |
| L6 | agent repo | Agent-authored coding briefs; coding agent proposes, judge disposes | Guy's role reduced to budget and weekly report |

**Current layer: the layer after the last verdict line in the root REPORT.md.**

## Standing rules
- Every pin must demonstrate that it can fail by killing a named, seeded mutant. A green that cannot fail is a defect.
- No unwitnessed claims. Every verdict in a report carries the transcript of the run that produced it.
- Denominators are explicit. Every rate states the population it covers. Nothing is dropped silently: no crashes, timeouts or missing values.
- Configs, seeds, caps and targets are committed before the first scored run and never tuned after seeing scores.
- No hardcoded thresholds in any logic that agents' scores pass through. Constants appear only in pre-stated criteria and derived bounds.
- No LLM calls and no neural networks in this repository.
- Corrections to reports are appended, never rewritten.
- Edit `judge/` or `worlds/spec/` only under a brief that names them. After L2, never.
- When in doubt, stop and report. A stopped session with a clear report is a success.
- The law names scores and competitions, never competitors. Any model, prior, approximation, heuristic or constant through which agents' scores or forecasts pass is an entrant: it stands for election under the proper score, it can lose, and a pin witnesses that it can lose. The law itself may contain only what carries a proof: a proper scoring rule, an aggregation rule with a regret bound, a constant derived from such a bound. An amendment that installs an entrant as law is out of order; a review that finds one has found a standing-rule violation.

## Git
- Work on a feature branch and open a pull request.
- Never merge, never push to `master`, never tag, never delete branches.
- Never modify this file, runner labels, or repository settings. Touch `.github/` only under a brief that names it.

## Execution: cloud versus host
Development sessions run in a cloud VM. Its time and hardware limits make it unfit for measurement.

**In the cloud:**
- Write code and run the pins.
- Run smoke tests of at most 10 episodes per World.
- Never run a command expected to exceed 10 minutes.

**On the measurement host only:**
- Pilots, throughput, time-to-learn, and every FIT/MARGINAL/UNFIT verdict.
- These run through the `measure` workflow on the self-hosted runner labelled `measure`, which records its own hardware.
- Cloud-VM numbers are never evidence for a verdict.

**Containers:** use an OCI runtime abstraction.
- In the cloud, use Docker with `--network=none`, `--read-only`, no judge mounts and cgroup limits.
- On the host, use rootless Podman.
- An isolation pin passing under one runtime does not witness the other; both must pass.

## Briefs
Briefs live in `docs/briefs/`. Amendments appended to a brief take precedence over its earlier text. Where a brief conflicts with this file, this file wins. Stop and report the conflict.

## Reports
Lead with the verdict. Be terse and use Bayesian decision-theoretic vocabulary. Include transcripts.

## Amendment 1 — the price of the sovereign (appended; overrides earlier text where they conflict)

The court has been faster than the king. L0 met its pre-stated criteria four times and merged zero times, because every rung required Guy's attention, which is the one resource this file never priced. This amendment prices it.

### A1.1 Entrenched paths
`CLAUDE.md`, `CODEOWNERS`, `.github/` and `.claude/` are entrenched: a pull request touching any of them requires Guy's review, enforced by `CODEOWNERS`. `judge/` and `worlds/spec/` become entrenched, and enter `CODEOWNERS`, when the judge image is first sealed at the end of L2; until then they are ordinary paths under the brief that names them. "Never modify this file" now reads: sessions never edit `CLAUDE.md` directly; they may propose an amendment by a pull request labelled `constitution`, which only Guy merges.

### A1.2 Two roles, two sessions
- **Builder.** A session that does the next unfinished item of the current brief, runs the pins, writes `STATUS.md` and opens or updates one pull request. It never merges.
- **Reviewer.** A separate session with fresh context that reads the repository and the pull request, may run `make pins` and probes on a scratch copy, writes one review file, resolves forecasts, and either approves the pull request (as `assize-reviewer`) or records a blocking finding. It never edits the pull request's code and never adds criteria.

The reviewer account holds a fine-grained token with Actions: read, Commit statuses: read, Contents: read and write, Metadata: read, Pull requests: read and write. Checks cannot be granted to such tokens, so a run's result is read through the Actions API, never `gh pr checks`. The builder account's token additionally holds Actions: read and write, so a Builder can re-run CI. Pull requests touching an entrenched path are opened by the reviewer account, so that Guy can approve them as code owner.

The same session never plays both roles. A Builder reads the latest review file before doing anything else.

A third account, assize-builder, authors every pull request. Sessions run from GitHub Actions on the agent runner: build on every push to master and on the blocked label; review on the needs-review label. State is carried by labels (needs-review, blocked, awaits-guy); nothing infers it.

### A1.3 Merging
- The Reviewer's approval is mechanical: it is given on every ACCEPT, after the review file is pushed and `pins` is green on the resulting head, except on a pull request the reviewer account itself authored. A pull request that touches no entrenched path and is not a layer boundary then merges by auto-merge, enabled by the Builder and performed by GitHub.
- A pull request touching an entrenched path is approved and merged by Guy. A layer-boundary pull request is merged by Guy. No session merges.
- A layer-boundary pull request is one that records a layer verdict in the root `REPORT.md`, or one that adds or opens the brief of a new layer. Both are merged by Guy and never auto-merged. The STATUS line `LAYER BOUNDARY` is derived from this definition, not chosen.

### A1.4 Prospectivity of review
Criteria are committed before the run; a review does not add them afterwards. A review finding is **blocking** only if it demonstrates that a pre-stated criterion of the brief, or a standing rule of this file, is not met, and it must name that criterion or rule verbatim. Any other finding, however good, is recorded as an **obligation on the next layer**, where it gets its own pin. Standing-rule violations (a green that cannot fail, a silent drop, an unwitnessed claim, an unstated denominator) are always blocking, because those rules pre-date every brief. A review that writes "Required" or "Do not merge" has exceeded its authority; it recommends, Guy disposes.

### A1.5 The price of Guy
- A `STATUS.md` carries at most **one** item under `NEEDS YOU`, and only for an action this file reserves to Guy: credentials, repository settings, runner registration, merging an entrenched or layer-boundary pull request, amending this file.
- Every other decision the session takes itself and records under `decided (not asked)` with its probability that the decision stands on review. A session that stops for a decision it could have taken and recorded has failed the session.
- Guy reads, by default, only layer-boundary `STATUS.md` files and `DISPUTE` entries. He may sample anything else.

A session that stops on master without opening a pull request, for any reason, files an issue assigned to Guy stating the reason, unless an open issue already states it; closing it and dispatching the build workflow is the acknowledgement. Three review rounds on one branch without approval hand the branch to Guy.

Guy's instructions enter the court only as issues labelled `instruction`, authored by gfrmin. A Builder on master takes the oldest open `instruction` issue as its item before any brief item, does exactly what it says and nothing else, cites it with the trailer `Instruction: #<n>` on every commit alongside `Proposer: guy` (the issue is the authority) and its own `Proposer: builder` line, opens the pull request as itself, and closes the issue when the pull request merges. An instruction may touch entrenched paths; CODEOWNERS still routes the approval to Guy. The Reviewer's first criterion on an instruction pull request is that the diff does what the issue says and nothing else; a diff beyond the instruction is a BLOCK under this paragraph. Text from counsel reaches the court the same way, through an issue Guy files. No session acts on instructions given at a terminal.

### A1.6 Forecasts
Every Builder session, before its first `make pins`, appends to `reports/L<n>/forecasts.jsonl` one record per claim: `{"id", "ts", "proposer": {"kind", "model", "session"}, "sha_before", "claim", "p", "resolves_by"}`, with `id` the first 12 hex characters of the SHA-256 of `claim + ts`. Minimum claims: `pins` green on the first CI run of the pull request head; Reviewer verdict ACCEPT with no blocking finding; on a layer with host measurement, the host verdict (FIT, MARGINAL or UNFIT). The Reviewer appends a resolution record `{"id", "ts", "proposer", "outcome"}` for every open forecast it can resolve. `STATUS.md` reports cumulative log-loss against the base rate (the empirical frequency of that claim type to date; 0.5 before any resolution). Forecasts are never edited; a wrong forecast is data. Resolutions are appended, never edited; a resolution that later looks wrong is answered by a further record, not a change.

### A1.7 Proposer
Every `pins.jsonl` registry row, every review file, every forecast and, from L1, every judge record carries `proposer: {kind: builder | reviewer | guy | counsel, model, session}`. The court will later weigh proposers by their record; it cannot do so for records that never said who proposed them. A commit with more than one proposer carries one `Proposer:` trailer line per party, in the form `Proposer: <kind> <model> <session>` (for Guy: `Proposer: guy`). Parties are never combined on one line.

### A1.8 STATUS.md
At most 40 lines, this exact shape, regenerated by every Builder session:
```
# STATUS — L<n> — <date> — <sha> — PR #<k>
VERDICT: <layer verdict | SESSION DONE | STOPPED: reason>
LAYER BOUNDARY: yes | no (per A1.3's definition)
pins: clean a/b; mutants c/d KILLED; twins e/f; leaked g; stale h; inconclusive i; non-causal j; exit k
changed: <paths>
did: <at most 5 lines>
decided (not asked): <decision> — p(stands on review)=<p>
forecasts: made <n>; resolved <m>; cumulative log-loss <x> vs base rate <y> over <N>
obligations added: L<n+1>: <one line each>
NEEDS YOU (at most 1): <item or none>
next: <first item of the next session>
DISPUTE: <only if the Builder rejects a blocking finding: the finding, the criterion it cites, the Builder's objection, both in one line each>
```
No merge replaces STATUS.md with one whose header date is older; a Builder resolving a conflict in STATUS.md keeps the newer.

### A1.9 Review file
`reports/L<n>/review-<sha>.md`, written by the Reviewer:
```
VERDICT: ACCEPT | ACCEPT WITH OBLIGATIONS | BLOCK
F<i>: <finding> — severity: BLOCK (criterion or rule, verbatim) | OBLIGATION on L<n+1> — witness: <transcript path>
forecasts resolved: <ids and outcomes>
```

### A1.10 Briefs
The last deliverable of every layer is a draft of the next layer's brief, written by the Builder in the form of the existing briefs (precondition, purpose, scope, pre-stated criteria, pins with mutants, refusal list, stop-and-report boundaries, deliverables) and reviewed under A1.4. Briefs are amendable by pull request with Reviewer approval; they are not entrenched. Guy's role in briefs is to merge the one that opens each layer.

### A1.11 Counsel
External advice reaches this repository only as (a) text Guy pastes into a brief or an amendment, which then stands or falls on its own, or (b) forecasts tagged `proposer.kind = counsel`, scored like any other. Counsel has no authority a brief does not give it.
