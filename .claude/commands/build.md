---
description: Builder session (CLAUDE.md A1.2). Usage: /build. Works the next item of the current layer's brief.
allowed-tools: Bash(gh:*), Bash(git:*), Bash(grep:*), Bash(ls:*), Bash(cat:*), Bash(make:*), Bash(uv:*)
---
Read CLAUDE.md first, including every amendment. It governs this session. Role: BUILDER.

## Context, gathered now
- Acting as GitHub account: !`gh api user -q .login`
- GH_TOKEN set: !`[ -n "$GH_TOKEN" ] && echo YES || echo no`
- Own session id: !`cat .claude/.session_id 2>/dev/null || echo unknown`
- Branch: !`git branch --show-current` at !`git rev-parse --short HEAD`; changed files: !`git status --porcelain | wc -l`
- Current layer: !`grep -m1 'Current layer' CLAUDE.md`
- Brief: !`ls docs/briefs/brief-$(grep -oP 'Current layer: L\K[0-9]+' CLAUDE.md)-*.md`
- Last STATUS: !`s=$(ls reports/L*/STATUS.md 2>/dev/null | tail -1); [ -n "$s" ] && cat "$s" || echo none`
- Newest review: !`r=$(ls -t reports/L*/review-*.md 2>/dev/null | head -1); [ -n "$r" ] && head -5 "$r" || echo none`

## Guards
- If the account above is `assize-reviewer`, or GH_TOKEN is set, stop and report: a Builder must never hold the reviewer's credentials. Do nothing else.
- If the newest review's VERDICT is BLOCK, your first and only item is that finding.

## Procedure
1. Start from STATUS's `next` line, else from the brief's first unfinished item.
2. Before your first commit, write `harness/proposer.toml` with `kind = "builder"`, your model, and your own session id; the Reviewer's guard reads it. The `session` is the own-session-id line above, never a value inferred from a path. Before your first `make pins`, append your forecasts to `reports/L<n>/forecasts.jsonl` per A1.6: at minimum, pins green on the first CI run of this PR head, and reviewer ACCEPT with no blocking finding, and, on a layer whose exit gate names a host verdict, the host verdict (FIT, MARGINAL or UNFIT).
3. Do one item of the brief, or the smallest group the brief states together. Never start the next layer. Never edit an entrenched path (A1.1) unless the brief names it.
4. Run `make pins`. Witness under the A3 hygiene rule. Every pin proves it can fail.
5. Decide what you can decide; record each decision in STATUS under `decided (not asked)` with p(stands on review). NEEDS YOU carries at most one item, and only an action CLAUDE.md reserves to Guy.
6. Write `reports/L<n>/STATUS.md` in the shape of A1.8 and push to a feature branch. If the branch touches no entrenched path: open or update one pull request with your own credentials, and if it is not a layer boundary, `gh pr merge --auto --squash`. If the branch touches an entrenched path: do not open a PR; set STATUS's `next` line to `assize-review <branch>`, which opens and reviews it as the reviewer account so that Guy can approve it as code owner. Never merge yourself; never hold or read the reviewer's token. STATUS names the sha at which `make pins` ran; the commit that adds STATUS is that sha's child and touches only `reports/`. Any other difference is a defect.
7. If this item completes the layer: append the verdict line to the root REPORT.md, set `LAYER BOUNDARY: yes`, do not enable auto-merge, and include a draft of the next layer's brief in the form of the existing briefs (A1.10).

Stop and report under the brief's boundaries. A stopped session with a clear STATUS is a success. A session that asks Guy something it could have decided and recorded has failed.
