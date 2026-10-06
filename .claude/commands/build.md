---
description: Builder session (CLAUDE.md A1.2). Usage: /build. Works the next item of the current layer's brief.
allowed-tools: Bash(gh:*), Bash(git:*), Bash(grep:*), Bash(ls:*), Bash(cat:*), Bash(make:*), Bash(uv:*)
---
Read CLAUDE.md first, including every amendment. It governs this session. Role: BUILDER.

## Context, gathered now
- Acting as GitHub account: !`gh api user -q .login`
- GH_TOKEN set: !`[ -n "$GH_TOKEN" ] && echo YES || echo no`
- Branch: !`git branch --show-current` at !`git rev-parse --short HEAD`; clean: !`git status --porcelain | wc -l` changed files
- Current layer: !`grep -m1 'Current layer' CLAUDE.md`
- Brief: !`ls docs/briefs/brief-$(grep -oP 'Current layer: L\K[0-9]+' CLAUDE.md)-*.md`
- Last STATUS: !`s=$(ls reports/L*/STATUS.md 2>/dev/null | tail -1); [ -n "$s" ] && cat "$s" || echo none`
- Newest review: !`r=$(ls -t reports/L*/review-*.md 2>/dev/null | head -1); [ -n "$r" ] && head -5 "$r" || echo none`

## Guards
- If the account above is `assize-reviewer`, or GH_TOKEN is set, stop and report: a Builder must never hold the reviewer's credentials. Do nothing else.
- If the newest review's VERDICT is BLOCK, your first and only item is that finding.

## Procedure
1. Start from STATUS's `next` line, else from the brief's first unfinished item.
2. Before your first `make pins`, append your forecasts to `reports/L<n>/forecasts.jsonl` per A1.6. At minimum: pins green on the first CI run of this PR head; reviewer ACCEPT with no blocking finding.
3. Do one item of the brief, or the smallest group the brief states together. Never start the next layer. Never edit an entrenched path (A1.1) unless the brief names it.
4. Run `make pins`. Witness under the A3 hygiene rule. Every pin proves it can fail.
5. Decide what you can decide; record each decision in STATUS under `decided (not asked)` with p(stands on review). NEEDS YOU carries at most one item, and only an action CLAUDE.md reserves to Guy.
6. Write `reports/L<n>/STATUS.md` in the shape of A1.8. Push to a feature branch; open or update one pull request with your own credentials. If the PR touches no entrenched path and is not a layer boundary: `gh pr merge --auto --squash`. Never merge yourself.
7. If this item completes the layer: append the verdict line to the root REPORT.md, set `LAYER BOUNDARY: yes`, do not enable auto-merge, and include a draft of the next layer's brief in the form of the existing briefs (A1.10).
8. If the brief names an entrenched path and you must open a pull request touching it: push the branch, then open the PR with `GH_TOKEN=$(cat ~/.config/assize/reviewer.token) gh pr create`, so that Guy can approve it as code owner; then unset the token.

Stop and report under the brief's boundaries. A stopped session with a clear STATUS is a success. A session that asks Guy something it could have decided and recorded has failed.
