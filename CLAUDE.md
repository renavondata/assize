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

**Current layer: L0**

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
