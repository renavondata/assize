VERDICT: ACCEPT WITH OBLIGATIONS
F1: The head reproduces `make pins` and CI `pins` is green on it. Run on steel-legend from a fresh `git worktree add --detach` scratch copy of `7c4e937`, started at once after checkout (2026-10-06T09:51:10Z): PINS PASSED; clean 8/8, mutants 10/10 KILLED, twins 10/10, 0 leaked, 0 stale, 0 inconclusive, 0 non-causal, exit 0, 1m53s. The `registry` row carries proposer `{builder, claude-opus-5-5, d1c31c5a-40d9-4dec-8bff-6ae707a2785c}`, matching harness/proposer.toml at head. The PR #5 review's fresh-copy race (F1 there) did not fire this time; it is still open and is now A5's first item. The Builder's transcript is from `401f616`, and `401f616..7c4e937` touches only reports/L1/STATUS.md and reports/L1/make-pins.txt. CI: `pins` run 37445779806 on `7c4e937`, attempt 1, pull_request, `success`. It is the only `pins` run on any constitution-3 head. — severity: none — witness: reports/L1/review/7c4e9376d5b4a5812cfaec4a660cfd12fede72aa/{make-pins-run1-fresh.txt, ci-runs.txt, pr-facts.txt}
F2: The PR touches entrenched paths: `CLAUDE.md` (A1.3, A1.7 and A1.8 text) and `.claude/settings.json`. So, per A1.1/A1.2, this session opened it as assize-reviewer (PR #6) and labelled it `constitution`. CODEOWNERS routes it to @gfrmin.
- Commit trailers already follow amended A1.7, one `Proposer:` line per party. 37712ae carries `Proposer: guy` and `Proposer: builder claude-opus-5-5 d1c31c5a-…` on separate lines. The four other commits carry the builder line alone.
- The texts are said to be Guy's "as supplied". His source text is not in the repository, so this review cannot witness that beyond the trailer. Guy's merge disposes of it.
— severity: none — witness: pr-facts.txt
F3: `.claude/settings.json` adds `permissions.allow` = `Bash(gh:*)`, `Bash(make:*)`, `Bash(podman:*)`.
- `Bash(gh:*)` lets a session run, with no prompt, commands that CLAUDE.md "Git" forbids to sessions ("Never merge, never push to `master`, never tag, never delete branches."): `gh pr merge`, `gh api -X PUT repos/…/pulls/N/merge`, `gh release create`, `gh api -X DELETE repos/…/git/refs/heads/…`.
- The file grants these permissions but performs none of the actions, so no rule is breached by this PR.
- The remaining guard is token scope and branch protection. This reviewer token cannot read branch protection (HTTP 403), so this review cannot witness that guard.
- `podman:*` is allowed but `docker` is not, although CLAUDE.md names Docker as the cloud runtime. A cloud session's container commands will still prompt.

Pin for the next brief: a checker parses `.claude/settings.json` and fails if any `allow` pattern admits a command from a fixed forbidden list without a `deny` entry covering it. The list: `gh pr merge`, `gh api -X PUT …/merge`, `gh release create`, `git tag`, `git push origin master`, `git push origin --delete`, `gh api -X DELETE …/git/refs/…`. Seeded mutant: a settings fixture with `Bash(gh:*)` and no deny list; the pin KILLS it. The settings file itself stays Guy's to edit.
— severity: OBLIGATION on L2 — witness: .claude/settings.json at 7c4e937; `gh api repos/renavondata/assize/branches/master/protection` → 403 (this session)
F4: The STATUS ledger figures reproduce:
- L0+L1 hold 14 claims; every id recomputes as sha256(claim+ts)[:12].
- 9 are resolved, none twice, and 5 are open.
- Cumulative log-loss is 2.088 against 6.238 = 9 ln 2, over 9.

The base rate is the constant 0.5. A1.6 defines it as "the empirical frequency of that claim type to date; 0.5 before any resolution". Claim types "pins green" and "Reviewer ACCEPT" already had resolutions before 6 of the 9 were resolved, so the stated base is not the defined one. The size of the gap is measured in forecasts-check.txt: a prequential Laplace base per type scores 5.298, not 6.238. The forecaster's 2.088 still beats it, but the margin shown in STATUS is inflated by 0.94 nats.
- A1.6 does not say whether "to date" means prequential or retrospective, and a raw frequency of 1.0 gives infinite loss on the first miss. The rule cannot be applied mechanically as written.
- This is the convention the PR #3, #4 and #5 reviews accepted.
- A1.6 sits among the amendments, not under "Standing rules", so this review does not treat it as a standing rule for A1.4's blocking test.

Pin for the next brief: a script computes the base rate per claim type, prequentially, as Laplace (k+1)/(n+2) over resolutions strictly before each one, and STATUS quotes the script's output. Seeded mutant: a constant 0.5 once a type has a resolution; it is KILLED on a fixture ledger with two same-type true resolutions.
— severity: OBLIGATION on L2 — witness: forecasts-check.txt; reports/L1/STATUS.md
F5: STATUS is 17 lines in the A1.8 shape. It reads "PR #none" because no PR existed when it was written; the PR is #6.

`LAYER BOUNDARY: no` is correct under the amended A1.3 definition: the PR touches no root `REPORT.md`, amends the current layer's brief and opens no new layer. It is also correct under master's text. The merge is Guy's anyway, by entrenchment.

Brief 1 A5 pulls F1, F2 and F4 of the PR #5 review into L1.
- A1.10 makes briefs amendable by PR with Reviewer approval, and that review offered F1 "within A4 item 5's harness work, at the Builder's choice".
- No scored run exists yet, so "Configs, seeds, caps and targets are committed before the first scored run" is not touched.
- A5's F2 fixture (one line per party) agrees with amended A1.7.
- A5's F4 fixes `prev_sha256` = SHA-256(request_id, UTF-8), closing the open definition.
- F3 is discharged in definition only. Its pin that derives the STATUS line from the diff is the Builder's L2 obligation in STATUS.

— severity: none — witness: reports/L1/STATUS.md; docs/briefs/brief-1-judge-and-crafter.md §A5; pr-facts.txt
F6: Guard and context. Own session id 19f2f6c7-b4a3-4b93-a3eb-fd2cc07a1fb3. It differs from the head's Builder, d1c31c5a-40d9-4dec-8bff-6ae707a2785c, so the guard ran.

The /review context commands were run before any PR existed. `gh pr view constitution-3` returned nothing, so they fetched and described `master` at 715e0d2. This review re-fetched `constitution-3` (7c4e937) and evaluated that. The head reads "Current layer: L1", the brief is docs/briefs/brief-1-judge-and-crafter.md, and 5 forecasts are open at the head.

The branch is checked out in the Builder's worktree, so this review worked on a local branch `review-constitution-3` and pushed to `constitution-3` by refspec. — severity: none — witness: this session's transcript; pr-facts.txt

forecasts resolved:
- bac95e050e0d → true. `pins` run 37445779806 is the first CI run of the constitution-3 PR head 7c4e937, `success`.
- f01921f37bce → true. This file: ACCEPT WITH OBLIGATIONS, 0 BLOCK findings; "ACCEPT" is read to include ACCEPT WITH OBLIGATIONS, as in the PR #3–#5 reviews.
- 11503575a841, 1608ce8c1b56 and d2c4349bd09f stay open. They resolve only on the host `measure` run.
- Denominator: L0+L1 ledger 14 claims; 11 resolved after this review; 3 open. The Builder resolved none itself.

Criteria evaluated. The PR implements no item of brief 1 or of A4/A5. It amends CLAUDE.md, a Guy-reserved action, and appends brief text, which A1.10 allows. Against the Standing rules:
- "Every pin must demonstrate that it can fail by killing a named, seeded mutant.": MET. 10/10 KILLED with passing twins, locally and in CI (F1).
- "No unwitnessed claims.": MET for the STATUS pins and ledger figures (F1, F4). Guy's authorship of the amendment text rests on the 37712ae trailer (F2).
- "Denominators are explicit.": MET.
- "No LLM calls and no neural networks in this repository.": MET (no code change).
- "Edit `judge/` or `worlds/spec/` only under a brief that names them.": MET (neither is touched).
- Git, "Never modify this file, runner labels, or repository settings.": read with A1.1 as amended ("they may propose an amendment by a pull request labelled `constitution`, which only Guy merges"). MET: the change is a proposal in PR #6, labelled `constitution`, and is merged only by Guy.

Hygiene: the probe ran in one scratch worktree under this session's scratchpad. It was removed and pruned, and the scratchpad is empty. No `/tmp/assize-*`, no harness or `make pins` process and no assize container remain (cleanup.txt).

proposer: {kind: reviewer, model: claude-opus-5-5, session: 19f2f6c7-b4a3-4b93-a3eb-fd2cc07a1fb3}

NEEDS GUY: approve and merge (entrenched: CLAUDE.md, .claude/settings.json; PR #6 authored by assize-reviewer, so this review does not approve)
