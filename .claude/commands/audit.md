---
description: Auditor procedure of the reviewer account (CLAUDE.md Amendments 2 and 4). Usage: /audit. Audits the whole repository at master.
allowed-tools: Bash(gh:*), Bash(git:*), Bash(grep:*), Bash(ls:*), Bash(cat:*), Bash(sleep:*), Bash(make:*), Bash(uv:*), Bash(python3:*)
---
CLAUDE.md, already in your context, governs this session, including every amendment. Role: AUDITOR.

## Context, gathered now (from master, not a pull request)
- Acting as GitHub account: !`gh api user -q .login`
- Own session id: !`cat .claude/.session_id 2>/dev/null || echo unknown`
- Audited: !`git branch --show-current || true` at !`git rev-parse HEAD || true`; origin/master at !`git rev-parse origin/master || true`
- Current layer: !`L=$(( $(grep -oP '^- L\K[0-9]+' REPORT.md | sort -n | tail -1) + 1 )); echo "L$L" || true`
- Brief: !`L=$(( $(grep -oP '^- L\K[0-9]+' REPORT.md | sort -n | tail -1) + 1 )); ls docs/briefs/brief-$L-*.md 2>/dev/null || true`
- Last audit file: !`f=$(git log --diff-filter=A --name-only --format= -- 'reports/*/audit-*.md' | head -1); echo "${f:-none}"`
- Highest-surprise merged pull requests since it (since the root commit if none; header, then the top three): !`f=$(git log --diff-filter=A --name-only --format= -- 'reports/*/audit-*.md' | head -1); s=$(basename "${f:-none}" .md | sed -n 's/^audit-//p'); [ -n "$s" ] || s=$(git rev-list --max-parents=0 HEAD | tail -1); uv run --frozen python -m harness.ledger surprise --since "$s" 2>&1 | head -4 || true`
- The Vizier's record since it: !`f=$(git log --diff-filter=A --name-only --format= -- 'reports/*/audit-*.md' | head -1); t=$([ -n "$f" ] && git log -1 --format=%cI --diff-filter=A -- "$f" || echo ""); uv run --frozen python -m harness.ledger proposer vizier --since "$t" 2>&1 || true`
- The Vizier's three resolved forecasts with the largest log-loss since it (Amendment 3: surprise sampling includes the Vizier's recommendations): !`cat reports/L*/forecasts.jsonl | python3 -c 'import sys, json, math; r = [json.loads(l) for l in sys.stdin if l.strip()]; o = {x.get("id"): x["outcome"] for x in r if "claim" not in x and isinstance(x.get("outcome"), bool)}; v = [x for x in r if "claim" in x and x.get("proposer", {}).get("kind") == "vizier" and x["id"] in o]; [print(x["id"], x.get("class"), x.get("mode"), round(-math.log(x["p"] if o[x["id"]] else 1 - x["p"]), 4), x["claim"]) for x in sorted(v, key=lambda x: math.log(x["p"] if o[x["id"]] else 1 - x["p"]))[:3]] or print("none")' || true`

## Guards
- If the account above is not `assize-reviewer`, stop and report: wrong credentials; do nothing else. The Auditor is a procedure of the reviewer account, under rule 4 of the ground (CLAUDE.md Amendment 4); it holds no account, model or scope of its own.
- If the audited sha is not origin/master, stop and report.
- If your own session id appears in the `builders=` field of any pull request listed above, stop and report: you were a Builder of record in a pull request you would re-review. If it is `unknown`, say so in the audit file and continue.

## Procedure
1. Forecast first, before reading any file beyond this context. `git checkout -b audit-<sha, 12 hex>`. Append to `reports/L<n>/forecasts.jsonl` four forecast records in the shape of A1.6, one per bin of your own finding count {0, 1–3, 4–8, 9+}, with `proposer` `{"kind": "auditor", "model": <your model id>, "session": <your session id>}`, `sha_before` the audited sha, claim `Audit at <sha12>: the Auditor's finding count is in <bin>`, `ts` the current UTC time (`python3 -c 'import datetime; print(datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))'`), `p` each in (0, 1) and summing to 1, `resolves_by` `the resolver, from the count of F lines in reports/L<n>/audit-<sha>.md`, `type` `finding_count` and `args` `{"sha": <the audited sha>, "bin": <the bin: "0", "1-3", "4-8" or "9+">}` (CLAUDE.md Amendment 4, rule 3). Commit with the trailer `Proposer: auditor <model> <session>` (no blank line before any other trailer) and push the branch. That commit and the records' `ts` precede your first file read; the session log is their witness.
2. Transcribe the Vizier's records (CLAUDE.md Amendment 3; the Vizier procedure does not push): every comment by `assize-reviewer` whose body begins `vizier-ledger: ` (`gh api --paginate "repos/renavondata/assize/issues/comments?per_page=100" -q '.[] | select(.user.login == "assize-reviewer") | .body | select(startswith("vizier-ledger: ")) | ltrimstr("vizier-ledger: ")'`) whose `id` is in no ledger yet is appended verbatim to `reports/L<n>/forecasts.jsonl`, in comment order; and the body of any open issue `Sovereign brief at L<m>` authored by `assize-reviewer` with no `reports/L<m>/sovereign-brief.md` is committed as that file. Commit both with the trailer as in 1. Change nothing else of theirs.
3. Read the repository at the audited sha, the whole tree, against the seven audit criteria of CLAUDE.md Amendment 2. Then re-review, cold, the three pull requests listed above: read each diff (`gh pr diff <n>`) and form your findings before reading its review files under `reports/`; then read them to see whether the Reviewer passed each finding. Re-review the Vizier's three forecasts listed above the same way, against the item's timeline. Probes run on scratch copies only (`mktemp -d`), never in this checkout. Leave no process and no copy behind, and show that you didn't.
4. Write `reports/L<n>/audit-<audited sha>.md`:
   ```
   AUDIT: <sha> — L<n> — <date> — auditor <model> <session>
   FINDINGS: <count>
   F<i>: <finding> — criterion: <number and text, verbatim> — at: <file>:<line> — pin: <proposed pin> — mutant: <seeded mutant> — witness: <transcript path or command>[ — passed by: reviewer <model> <session> in <review file> of PR #<k>]
   re-reviewed: PR #<k> (loss <x>, resolved <r>/<m>) for each of the three, or none
   forecasts: <the four ids>
   ```
   The `passed by` field is the record against the Reviewer: it is set on a finding from a re-reviewed pull request whose review file did not raise it.
5. If there is at least one finding, append to the current brief a section `## Audit findings at <sha12>`, one numbered item per finding: the finding, its criterion verbatim, file and line, the proposed pin and its seeded mutant. Append only; change nothing else in the brief.
6. Open the pull request under the Builder's procedure, two-phase per P0l: commit the audit file and the brief amendment (trailer as in 1), push, and open the pull request as yourself, titled `Audit at <sha12>: <count> findings`. Poll the Actions API until `pins` on that head concludes: `gh api "repos/renavondata/assize/actions/runs?head_sha=<sha>&event=pull_request" -q '.workflow_runs[] | select(.name=="pins") | "\(.status) \(.conclusion) \(.id)"'`. Record the run as `reports/L<n>/ci/<id>.json` (`gh api repos/renavondata/assize/actions/runs/<id> --jq '{conclusion,created_at,event,head_branch,head_sha,html_url,id,name,path,run_attempt,status}'`), write `reports/L<n>/STATUS.md` in the shape of A1.8 naming that sha and citing `pins CI run <id> on <sha7>`, commit both in a commit touching only `reports/`, push, then `gh pr edit <n> --add-label needs-review`.
7. Never edit code, never edit an entrenched path, never resolve a forecast, never approve, never enable auto-merge, never merge.
8. Change files with the Edit and Write tools, never by shell redirection, heredocs or inline scripts; shell is for commands that are not edits. A tool call the harness denies is quoted (tool, reason) in STATUS `did:` or in the session's stop report; a session whose procedure called for a pull request and that stops on master without one files an issue assigned to gfrmin, as build.md requires, with the denial quoted (instruction #110).

Stop and report if the guards fail or the ledger command errors. A stopped audit with a clear file is a success.
