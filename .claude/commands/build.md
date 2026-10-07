---
description: Builder session (CLAUDE.md A1.2). Usage: /build. Works the next item of the current layer's brief, or the blocking finding of the checked-out PR.
allowed-tools: Bash(gh:*), Bash(git:*), Bash(grep:*), Bash(ls:*), Bash(cat:*), Bash(make:*), Bash(uv:*), Bash(python3:*), Bash(podman:*)
---
Read CLAUDE.md first, including every amendment. It governs this session. Role: BUILDER.

## Context, gathered now
- Acting as GitHub account: !`gh api user -q .login`
- Own session id: !`cat .claude/.session_id 2>/dev/null || echo unknown`
- Acknowledgement flag (set only on a manual dispatch by Guy): !`echo "${ASSIZE_ACK:-no}"`
- Branch: !`git branch --show-current || true` at !`git rev-parse --short HEAD || true`; changed files: !`git status --porcelain | wc -l || true`
- Current layer: !`grep -m1 'Current layer' CLAUDE.md || true`
- Brief: !`ls docs/briefs/brief-$(grep -oP 'Current layer: L\K[0-9]+' CLAUDE.md)-*.md 2>/dev/null || true`
- Last STATUS here: !`s=$(ls reports/L*/STATUS.md 2>/dev/null | sort | tail -1); [ -n "$s" ] && cat "$s" || echo none`
- Newest review here: !`r=$(ls -t reports/L*/review-*.md 2>/dev/null | head -1); [ -n "$r" ] && head -5 "$r" || echo none`
- Review files on this branch (attempts so far): !`ls reports/L*/review-*.md 2>/dev/null | wc -l || true`

## Guards
- If the account above is not `assize-builder`, stop and report: a Builder runs only as the builder account. Do nothing else.
- If the checked-out branch is `master` and the last STATUS has a `NEEDS YOU` that is not `none`, and the acknowledgement flag is `no`: do not build. If no open issue has that line as its title, create one: `gh issue create --title "<the NEEDS YOU line>" --assignee gfrmin --body "From $(git rev-parse --short HEAD) STATUS. Close this issue and run the build workflow (gh workflow run build.yml) to acknowledge."` Then stop and report.
- If the checked-out branch is a PR branch and the newest review's VERDICT is BLOCK: your first and only item is that finding. If this branch already has three review files, do not build: label the PR `awaits-guy`, request Guy's review (`gh pr edit <n> --add-reviewer gfrmin`), write STATUS with `NEEDS YOU: three review rounds without approval; decide`, push, and stop.

## Procedure
1. On `master`: start from STATUS's `next` line, else from the brief's first unfinished item, on a new branch. On a PR branch: work the finding.
2. Before your first commit, write `harness/proposer.toml` with `kind = "builder"`, your model, and your own session id. Before your first `make pins`, append your forecasts to `reports/L<n>/forecasts.jsonl` per A1.6: pins green on the first CI run of this PR head; reviewer ACCEPT with no blocking finding; and, on a layer whose exit gate names a host verdict, the host verdict.
3. Do one item of the brief, or the smallest group the brief states together. Never start the next layer. Never edit an entrenched path (A1.1) unless the brief names it.
4. Run `make pins`. Witness under the A3 hygiene rule. Every pin proves it can fail.
5. Decide what you can decide; record each decision in STATUS under `decided (not asked)` with p(stands on review). NEEDS YOU carries at most one item, and only an action CLAUDE.md reserves to Guy.
6. Write `reports/L<n>/STATUS.md` in the shape of A1.8. STATUS names the sha at which `make pins` ran; the commit adding STATUS is that sha's child and touches only `reports/`. Push. Open the pull request if none exists (you are its author). If it is not a layer boundary and touches no entrenched path, `gh pr merge --auto --merge`. Then label it: `gh pr edit <n> --remove-label blocked --add-label needs-review` (ignore errors from a label that isn't present). If STATUS carries a `NEEDS YOU`, also `gh pr edit <n> --add-reviewer gfrmin`. Never merge yourself.
7. If this item completes the layer: append the verdict line to the root REPORT.md, set `LAYER BOUNDARY: yes`, do not enable auto-merge, label `needs-review`, and include a draft of the next layer's brief in the form of the existing briefs (A1.10).
8. When the brief calls for a host witness, add the `measure` label to your PR and record the run id in STATUS (A6).

Stop and report under the brief's boundaries. A stopped session with a clear STATUS is a success. A session that asks Guy something it could have decided and recorded has failed.
