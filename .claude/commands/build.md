---
description: Builder session (CLAUDE.md A1.2). Usage: /build. Works the next item of the current layer's brief, or the blocking finding of the checked-out PR.
allowed-tools: Bash(gh:*), Bash(git:*), Bash(grep:*), Bash(ls:*), Bash(cat:*), Bash(make:*), Bash(uv:*), Bash(python3:*), Bash(podman:*)
---
Read CLAUDE.md first, including every amendment. It governs this session. Role: BUILDER.

## Context, gathered now
- Acting as GitHub account: !`gh api user -q .login`
- Own session id: !`cat .claude/.session_id 2>/dev/null || echo unknown`
- Acknowledgement flag (set only on a manual dispatch by Guy): !`echo "${ASSIZE_ACK:-no}"`
- Dispatched PR (if any): !`echo "${ASSIZE_PR:-none}"`
- Branch: !`git branch --show-current || true` at !`git rev-parse --short HEAD || true`; changed files: !`git status --porcelain | wc -l || true`
- Current layer: !`L=$(( $(grep -oP '^- L\K[0-9]+' REPORT.md | sort -n | tail -1) + 1 )); echo "L$L" || true`
- Brief: !`L=$(( $(grep -oP '^- L\K[0-9]+' REPORT.md | sort -n | tail -1) + 1 )); ls docs/briefs/brief-$L-*.md 2>/dev/null || true`
- Open instruction issues: !`gh issue list --label instruction --state open --json number,title -q '.[] | "#\(.number) \(.title)"' || true`
- Instruction signatures (CLAUDE.md Amendment 3): !`n=$(gh issue list --label instruction --state open --json number -q '.[].number' | tr '\n' ' '); [ -n "${n// }" ] && uv run --frozen python -m harness.claims signed $n 2>&1 || echo none`
- Last STATUS here: !`s=$(ls reports/L*/STATUS.md 2>/dev/null | sort | tail -1); [ -n "$s" ] && cat "$s" || echo none`
- Newest review here: !`r=$(ls -t reports/L*/review-*.md 2>/dev/null | head -1); [ -n "$r" ] && head -5 "$r" || echo none`
- Review files on this branch (attempts so far): !`ls reports/L*/review-*.md 2>/dev/null | wc -l || true`

## Guards
- If the account above is not `assize-builder`, stop and report: a Builder runs only as the builder account. Do nothing else.
- If a dispatched PR is set, check it out with `gh pr checkout` before anything else and treat this as a PR-branch session.
- If the checked-out branch is `master` and you will not open a pull request this session, for any reason: before stopping, create an issue assigned to gfrmin whose title is the reason in one line and whose body says what would unblock it, unless an open issue already says so. Then stop and report.
- If the checked-out branch is a PR branch and the newest review's VERDICT is BLOCK: your first and only item is that finding. If this branch already has three review files, do not build: label the PR `awaits-guy`, request Guy's review (`gh pr edit <n> --add-reviewer gfrmin`), write STATUS with `NEEDS YOU: three review rounds without approval; decide`, push, and stop.

## Procedure
1. On `master`: If an open issue labelled `instruction` and marked `signed` above exists, the oldest is your item; an issue marked `refused` is not an instruction (its `instruction` label was not applied by gfrmin): do not act on it, comment once on it with its `refused` line unless such a comment exists, and name it in STATUS. The item: branch `instr-<n>-<slug>`, do exactly what the issue body says and nothing else, trailers `Instruction: #<n>`, `Proposer: guy`, `Proposer: builder <model> <session>` on every commit. Otherwise proceed from STATUS's `next` line, else from the brief's first unfinished item, on a new branch. On a PR branch, first step: if the branch conflicts with master (`gh pr view --json mergeStateStatus` is DIRTY), merge origin/master first: append-only files keep every line from both sides; STATUS.md keeps the newer-dated; other conflicts resolved minimally and listed in the commit message. Then work the finding.
2. Before your first commit, write `harness/proposer.toml` with `kind = "builder"`, your model, and your own session id. Before your first `make pins`, append your forecasts to `reports/L<n>/forecasts.jsonl` per A1.6, each with its `type` and `args` (CLAUDE.md Amendment 4, rule 3): pins green on the first CI run of this PR head (`type` `pins_green`, `args` `{"pr": <n>}`); reviewer ACCEPT with no blocking finding (`review_accept`, `{"pr": <n>}`); and, on a layer whose exit gate names a host verdict, the host verdict (`host_verdict`, `{"layer": <L>, "verdict": <FIT, MARGINAL or UNFIT>}`). On a new branch, `<n>` is the number the pull request will take: one more than the highest issue or pull request number (`gh api "repos/renavondata/assize/issues?state=all&per_page=1" -q '.[0].number'`), read just before you push and open it. The forecasts are in the head of the first `pins` run on the branch (rule 2), so commit them before the pull request opens.
3. Do one item of the brief, or the smallest group the brief states together. Never start the next layer. Never edit an entrenched path (A1.1) unless the brief names it.
4. Run `make pins`. Witness under the A3 hygiene rule. Every pin proves it can fail.
5. Decide what you can decide; record each decision in STATUS under `decided (not asked)` with p(stands on review). NEEDS YOU carries at most one item, and only an action CLAUDE.md reserves to Guy.
6. Write `reports/L<n>/STATUS.md` in the shape of A1.8. STATUS names the sha at which `make pins` ran; the commit adding STATUS is that sha's child and touches only `reports/`. Push. Open the pull request if none exists (you are its author). If it is not a layer boundary and touches no entrenched path, `gh pr merge --auto --merge`. Then label it: `gh pr edit <n> --remove-label blocked --add-label needs-review` (ignore errors from a label that isn't present). If STATUS carries a `NEEDS YOU`, also `gh pr edit <n> --add-reviewer gfrmin`. After opening the PR, if this PR cites an instruction, note `Instruction: #<n>` in the PR body; close the issue only after the PR merges (the next master session does it if you cannot). Never merge yourself.
7. If this item completes the layer: append the verdict line to the root REPORT.md, set `LAYER BOUNDARY: yes`, do not enable auto-merge, label `needs-review`, and include a draft of the next layer's brief in the form of the existing briefs (A1.10).
8. When the brief calls for a host witness, add the `measure` label to your PR and record the run id in STATUS (A6).

Stop and report under the brief's boundaries. A stopped session with a clear STATUS is a success. A session that asks Guy something it could have decided and recorded has failed.
