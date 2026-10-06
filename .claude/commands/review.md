---
description: Reviewer session (CLAUDE.md A1.2). Usage: /review [PR number]; with no number, the PR of the checked-out branch.
allowed-tools: Bash(gh:*), Bash(git:*), Bash(GH_TOKEN=* gh *), Bash(GH_TOKEN=* git *), Bash(grep:*), Bash(ls:*), Bash(cat:*)
---
Read CLAUDE.md first, including every amendment. It governs this session. Role: REVIEWER.

## Credentials
Every `gh` call in this session, and every `git` call that talks to the remote, runs as `assize-reviewer` via the token in the keyring, inlined per command (never exported, never printed):
- `gh`: `GH_TOKEN=$(secret-tool lookup service env key ASSIZE_REVIEW_TOKEN) gh ...`
- `git push`/`fetch`: `GH_TOKEN=$(secret-tool lookup service env key ASSIZE_REVIEW_TOKEN) git -c credential.helper= -c 'credential.helper=!gh auth git-credential' push ...`

A bare `gh` acts as Guy's account and must not be used.

## Context, gathered now
- Acting as GitHub account: !`GH_TOKEN=$(secret-tool lookup service env key ASSIZE_REVIEW_TOKEN) gh api user -q .login`
- PR: !`GH_TOKEN=$(secret-tool lookup service env key ASSIZE_REVIEW_TOKEN) gh pr view $ARGUMENTS --json number,title,headRefName,headRefOid,baseRefName,isDraft -q '"#\(.number) \(.title) — \(.headRefName)@\(.headRefOid) -> \(.baseRefName) draft=\(.isDraft)"'`
- Files touched: !`GH_TOKEN=$(secret-tool lookup service env key ASSIZE_REVIEW_TOKEN) gh pr view $ARGUMENTS --json files -q '[.files[].path] | join(", ")'`
- Current layer: !`grep -m1 'Current layer' CLAUDE.md`
- Brief: !`ls docs/briefs/brief-$(grep -oP 'Current layer: L\K[0-9]+' CLAUDE.md)-*.md`
- Open forecasts: !`f=$(ls reports/L*/forecasts.jsonl 2>/dev/null | tail -1); [ -n "$f" ] && grep -c '"claim"' "$f" || echo none`

## Guards
- If the account above is not `assize-reviewer`, stop and report: this session has the wrong credentials and must not review. Do nothing else.
- If no PR resolved above, stop and report.
- This session is `${CLAUDE_SESSION_ID}`. After checkout (step 1), run `git grep -l '${CLAUDE_SESSION_ID}' HEAD` and `git log origin/<base>..HEAD --format=%B | grep -c '${CLAUDE_SESSION_ID}'`. If either finds this session in any `proposer.session` (forecasts, STATUS, pins.jsonl, review files) or commit message on the PR, this session proposed the work under review: stop and report. The same session never plays both roles (A1.2).

## Procedure
1. `gh pr checkout` (with the token prefix above) the PR into this worktree. Reproduce `make pins` on a scratch copy. Any probe runs on a scratch copy only; transcripts go under `reports/L<n>/review/<head sha>/`. Leave no process and no copy behind, and show that you didn't.
2. Write `reports/L<n>/review-<head sha>.md` in the shape of CLAUDE.md A1.9. A finding is BLOCK only if it demonstrates that a named pre-stated criterion of the brief, or a named standing rule of CLAUDE.md, is not met; quote it verbatim beside the finding. Every other finding is an OBLIGATION on the next layer, written so the next brief can make it a pin without you. If you catch yourself writing a requirement, it is an obligation.
3. Resolve every open forecast this review can resolve: append resolution records per A1.6, including any the Builder resolved itself, which you re-resolve from the witnesses rather than trust. Never edit a forecast.
4. If the verdict is ACCEPT or ACCEPT WITH OBLIGATIONS and the PR touches an entrenched path or is a layer boundary (records a verdict in the root REPORT.md), end the review file with `NEEDS GUY: merge` now, before committing; otherwise auto-merge will take it. Commit the review file and resolutions to the PR branch with `git -c user.name=assize-reviewer -c user.email=assize-reviewer@users.noreply.github.com commit`, then push it with the token-authenticated `git push` above. That is the only thing you write to the PR. Never edit its code, its briefs, its reports beyond your file, or any entrenched path.
5. After your push, poll the Actions API until pins on the new head concludes; if success and the verdict is ACCEPT or ACCEPT WITH OBLIGATIONS, approve, citing both the reviewed head and the run id: `GH_TOKEN=$(secret-tool lookup service env key ASSIZE_REVIEW_TOKEN) gh pr review --approve --body "review: reports/L<n>/review-<head sha>.md; reviewed head <head sha>; pins run <run id> on <new head sha>"`. Approval is mechanical and always given on ACCEPT with green pins. Push nothing after approving: "dismiss stale approvals on new commits" is on, so any later push dismisses the approval. If pins on the new head does not conclude success, do not approve; stop and report with the run id. If the verdict is BLOCK: do not approve; the Builder's next session starts from your finding.
6. Never merge. Never write "Required" or "Do not merge"; you recommend, Guy disposes.

Stop and report if the PR head does not reproduce `make pins`, if the brief or its amendments are missing, or if a pre-stated criterion cannot be evaluated from the witnesses in the PR. A stopped review with a clear file is a success.
