---
description: Reviewer session (CLAUDE.md A1.2). Usage: /review <PR number>.
allowed-tools: Bash(gh:*), Bash(git:*), Bash(grep:*), Bash(ls:*), Bash(cat:*), Bash(sleep:*), Bash(make:*), Bash(uv:*), Bash(python3:*)
---
Read CLAUDE.md first, including every amendment. It governs this session. Role: REVIEWER.

## Context, gathered now (from the PR head, not the working tree)
- Acting as GitHub account: !`gh api user -q .login`
- Own session id: !`cat .claude/.session_id 2>/dev/null || echo unknown`
- PR: !`gh pr view $ARGUMENTS --json number,title,headRefName,headRefOid,baseRefName,isDraft,author,labels -q '"#\(.number) \(.title) — \(.headRefName)@\(.headRefOid) -> \(.baseRefName) draft=\(.isDraft) author=\(.author.login) labels=\([.labels[].name]|join(","))"' 2>&1 || true`
- Fetched head: !`git fetch -q origin "$(gh pr view $ARGUMENTS --json headRefName -q .headRefName 2>/dev/null)" 2>&1 && git rev-parse --short FETCH_HEAD || true`
- Files touched: !`gh pr view $ARGUMENTS --json files -q '[.files[].path] | join(", ")' 2>&1 || true`
- Builder of record at head: !`for f in $(git ls-tree -r --name-only FETCH_HEAD harness/proposer.toml harness/proposer.d); do echo "# $f"; git show "FETCH_HEAD:$f"; done 2>&1 || true`
- Current layer at head: !`L=$(( $(git show FETCH_HEAD:REPORT.md | grep -oP '^- L\K[0-9]+' | sort -n | tail -1) + 1 )); echo "L$L" || true`
- Brief at head: !`L=$(( $(git show FETCH_HEAD:REPORT.md | grep -oP '^- L\K[0-9]+' | sort -n | tail -1) + 1 )); git ls-tree --name-only FETCH_HEAD docs/briefs/ | grep "brief-$L-" || true`
- Open forecasts at head: !`f=$(git ls-tree -r --name-only FETCH_HEAD | grep 'reports/L[0-9]*/forecasts\(\.jsonl\|/[^/]*\.jsonl\)$' | sort); [ -n "$f" ] && for p in $f; do git show "FETCH_HEAD:$p"; done | python3 -c 'import sys,json; r=[json.loads(l) for l in sys.stdin if l.strip()]; c={x["id"] for x in r if "claim" in x}; o={x["id"] for x in r if "outcome" in x}; print(len(c-o))' || echo none`

## Guards
- If the account above is not `assize-reviewer`, stop and report: wrong credentials; do nothing else.
- If `$ARGUMENTS` begins with `draft`, this is a draft check: the PR context above does not apply; follow "Draft-check mode" below and nothing else.
- If your own session id equals `session` in the Builder-of-record line, stop and report: you are this PR's Builder. If it is `unknown`, say so in the review file and continue.
- If no PR resolved, stop and report.

## Declaration and stop (instruction #112 Parts A and D)
- The first act of every session, before any other, is one comment on the item it has taken (the PR under review, or the draft) reading `review run <run id> started <ISO time> on #<n>: expected <m> minutes; model <your model id>`, with `<run id>` `$GITHUB_RUN_ID` (`local` outside Actions) and the time from `date -u +%Y-%m-%dT%H:%M:%SZ`. Nothing else is done before this comment exists. At the session's end, edit that comment (`gh api -X PATCH repos/renavondata/assize/issues/comments/<id> -f body=...`) to add `; tokens <n>`, from `uv run --frozen python -m harness.sessions tokens review.log` (`unknown` when there is no log).
- The declaration is a forecast: `type` `session_minutes`, `args` `{"run": <run id>, "bound": <m>}`, claim `review run <run id> ends within <m> minutes of its start`, proposer kind `reviewer`. Post it as a comment on the item whose whole body is `vizier-ledger: <the row as one line of JSON>`, right after the declaration; the Auditor transcribes it.
- A session that stops before writing its review file (or, in draft-check mode, its `Draft check:` comment) posts its stop report as a comment on the item it holds, beginning `review run <run id> stopped <ISO time>:`, before it ends. A session ending with neither is an unrouted exit (`harness.sessions.declared_findings`). The declaration and the stop comment are the two comments a session makes about itself.

## Draft-check mode: `/review draft <issue number>` (instruction #112 Part C)
1. Read the draft (`gh issue view <n> --json title,body,labels,comments`) and the `vizier-ledger:` row that recorded it (on the draft, or on the wish its first line cites). Your session id must differ from that row's `session`; if it does not, stop and report: you wrote this draft.
2. Read CLAUDE.md and every open issue labelled `instruction`. Check the draft for: conflict with the law or an open instruction; retroactivity (does it change the rules for a pull request already open); held items (an item an open PR already holds); degenerate criteria (a pin that cannot fail, a criterion with no seeded mutant, a threshold with no stated source).
3. First record your forecast as a comment on the draft whose whole body is `vizier-ledger: <the row as one line of JSON>`: a row in the shape of A1.6 with proposer kind `reviewer`, `class` `draft-check`, `mode` `recommend`, `type` `guy_answers`, `args` `{"item": <the draft>, "answer": <"labeled:instruction" for sign, "signed-after-edit" for edit, "closed" for decline>}`.
4. Then post one comment `Draft check: sign | edit | decline — p=<p> that Guy agrees — <reason>`; for edit, the exact replacement text in full; for decline, the reason.
5. Then remove the label: `gh api -X DELETE repos/renavondata/assize/issues/<n>/labels/needs-draft-check`. Never edit the draft, sign it, close it, or push anything.

## Procedure
1. `gh pr checkout` the PR. Reproduce `make pins` on a scratch copy; probes run on scratch copies only; transcripts go under `reports/L<n>/review/<reviewed head sha>/`. Leave no process and no copy behind, and show that you didn't. Read the head's `pins` run through the Actions API, never `gh pr checks`:
   `gh api "repos/renavondata/assize/actions/runs?head_sha=<sha>&event=pull_request" -q '.workflow_runs[] | select(.name=="pins") | "\(.status) \(.conclusion) \(.id) \(.html_url)"'`
   If the PR carries the `measure` label, read the `measure-host` run and its artefact the same way; they are the host witness.
2. If the PR cites `Instruction: #<n>`, read the issue; the first criterion is that the diff does what the issue says and nothing else (CLAUDE.md A1.5). Beyond-instruction changes are BLOCK. Write `reports/L<n>/review-<reviewed head sha>.md` in the shape of A1.9. A finding is BLOCK only if it demonstrates that a named pre-stated criterion of the brief, or a named standing rule of CLAUDE.md, is not met; quote it verbatim beside the finding. Every other finding is an OBLIGATION on the next layer. Earlier review files for this PR stand as records; never edit or delete them. Record any verdict that differs between your reproduction and the Builder's as a flake.
3. Run the resolver: `uv run --frozen python -m harness.ledger resolve --session "${GITHUB_RUN_ID:-local}"` (CLAUDE.md Amendment 4, rule 3); it appends the resolution of every open typed forecast whose outcome is observable. Resolve by hand only `free` claims, each with its witness path, appending resolution records per A1.6, never one whose forecast your own session made (rule 4). Never edit a forecast or an existing resolution.
4. Commit the review file and resolutions as yourself and push to the PR branch. The resolver's resolutions are committed in their own commit, whose only `Proposer:` lines are yours and `Proposer: mechanism harness.ledger <run id>`, so a defect in either trailer never dismisses the review file (instruction #239 item 4). That is the only thing you write to the PR. Never edit its code, its briefs, its reports beyond your file, or any entrenched path.
5. Your push moved the head. Poll the Actions API until `pins` on the new head concludes. Then, exactly one of:
   - ACCEPT or ACCEPT WITH OBLIGATIONS, `pins` success, no entrenched path, not a layer boundary: `gh pr review <n> --approve --body "review: <path>; pins run <id> on <new head>"`, then `gh pr edit <n> --remove-label needs-review`, then `gh pr merge <n> --auto --merge` so that a Builder that forgot to arm auto-merge cannot strand an approved PR. Auto-merge takes it.
   - ACCEPT or ACCEPT WITH OBLIGATIONS on an entrenched-path or layer-boundary PR: end the review file with `NEEDS GUY: approve and merge` (entrenched) or `NEEDS GUY: merge` (boundary); `gh pr edit <n> --remove-label needs-review --add-label awaits-guy --add-reviewer gfrmin`. Approve as well when the PR is not a layer boundary and you are not its author, so that only Guy's code-owner review remains.
   - BLOCK: do not approve; `gh pr edit <n> --remove-label needs-review --add-label blocked`. The Builder is sent to the branch by that label.
6. Never merge. Never write "Required" or "Do not merge"; you recommend, Guy disposes.

## Files, pushes and denials (instruction #110)
- Change files with the Edit and Write tools, never by shell redirection, heredocs or inline scripts; shell is for commands that are not edits. A tool call the harness denies is quoted (tool, reason) in the review file or in the session's stop report.
- Every push passes `harness/hooks/pre-push` (`python -m harness.claims trailers @{u}..HEAD`, installed by the workflow): a refused push is answered by amending your own unpushed commit, never by an exemption entry in `claims.PROPOSER_EXEMPTIONS`. A session that cannot make its commit parse stops and reports.

Stop and report if the PR head does not reproduce `make pins`, if the brief or its amendments are missing, or if a pre-stated criterion cannot be evaluated from the witnesses in the PR. A stopped review with a clear file is a success.
