---
description: Reviewer session (CLAUDE.md A1.2). Usage: /review [PR number | branch name]. No argument: the PR of the checked-out branch. A branch with no PR yet: opens the PR as assize-reviewer (entrenched-path PRs), then reviews it.
allowed-tools: Bash(gh:*), Bash(git:*), Bash(grep:*), Bash(ls:*), Bash(cat:*), Bash(sleep:*), Bash(make:*), Bash(uv:*)
---
Read CLAUDE.md first, including every amendment. It governs this session. Role: REVIEWER.

## Context, gathered now
- Acting as GitHub account: !`gh api user -q .login`
- Argument: `$ARGUMENTS`
- PR for the argument, if one exists: !`gh pr view $ARGUMENTS --json number,title,headRefName,headRefOid,baseRefName,isDraft,author -q '"#\(.number) \(.title) — \(.headRefName)@\(.headRefOid) -> \(.baseRefName) draft=\(.isDraft) author=\(.author.login)"' 2>&1`
- Files touched: !`gh pr view $ARGUMENTS --json files -q '[.files[].path] | join(", ")' 2>&1`
- Builder of record (harness/proposer.toml): !`cat harness/proposer.toml 2>&1`
- Current layer: !`grep -m1 'Current layer' CLAUDE.md`
- Brief: !`ls docs/briefs/brief-$(grep -oP 'Current layer: L\K[0-9]+' CLAUDE.md)-*.md`
- Open forecasts: !`f=$(ls reports/L*/forecasts.jsonl 2>/dev/null | tail -1); [ -n "$f" ] && grep -c '"claim"' "$f" || echo none`

## Guards
- If the account above is not `assize-reviewer`, stop and report: wrong credentials; do nothing else.
- If your own session id equals `session` in `harness/proposer.toml`, stop and report: you are this PR's Builder and cannot review it.
- If the argument names a branch and no PR exists for it: `gh pr create --base master --head <branch> --fill`, as assize-reviewer, then continue with that PR. This is the only way an entrenched-path PR is opened; its approval will be Guy's.
- If no PR resolved, stop and report.

## Procedure
1. `gh pr checkout` the PR into this worktree. Reproduce `make pins` on a scratch copy. Any probe runs on a scratch copy only; transcripts go under `reports/L<n>/review/<reviewed head sha>/`. Leave no process and no copy behind, and show that you didn't. Read the head's `pins` run through the Actions API, never `gh pr checks`:
   `gh api "repos/renavondata/assize/actions/runs?head_sha=<sha>&event=pull_request" -q '.workflow_runs[] | select(.name=="pins") | "\(.status) \(.conclusion) \(.id) \(.html_url)"'`
2. Write `reports/L<n>/review-<reviewed head sha>.md` in the shape of CLAUDE.md A1.9. A finding is BLOCK only if it demonstrates that a named pre-stated criterion of the brief, or a named standing rule of CLAUDE.md, is not met; quote it verbatim beside the finding. Every other finding is an OBLIGATION on the next layer, written so the next brief can make it a pin without you. If you catch yourself writing a requirement, it is an obligation. Earlier review files for this PR stand as records; never edit or delete them.
3. Resolve every open forecast this review can resolve: append resolution records per A1.6, re-resolving from witnesses anything the Builder resolved itself. Never edit a forecast or an existing resolution.
4. Commit the review file and resolutions with `git -c user.name=assize-reviewer -c user.email=assize-reviewer@users.noreply.github.com commit`, and push to the PR branch as assize-reviewer. That is the only thing you write to the PR. Never edit its code, its briefs, its reports beyond your file, or any entrenched path.
5. Your push moved the head. Poll the Actions API until `pins` on the new head concludes. If it is `success` and the verdict is ACCEPT or ACCEPT WITH OBLIGATIONS: `gh pr review --approve --body "review: reports/L<n>/review-<reviewed head sha>.md; pins run <id> on <new head sha>"`. Approving before the push would be dismissed by the push. If the PR touches an entrenched path, or is a layer boundary (records a verdict in the root REPORT.md), or you are its author: do not approve; end the review file with `NEEDS GUY: approve and merge` (entrenched or authored by you) or `NEEDS GUY: merge` (boundary). If the verdict is BLOCK: do not approve; the Builder's next session starts from your finding.
6. Never merge. Never write "Required" or "Do not merge"; you recommend, Guy disposes.

Stop and report if the PR head does not reproduce `make pins`, if the brief or its amendments are missing, or if a pre-stated criterion cannot be evaluated from the witnesses in the PR. A stopped review with a clear file is a success.
