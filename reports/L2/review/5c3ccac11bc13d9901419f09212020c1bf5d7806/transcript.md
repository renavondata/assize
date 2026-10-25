# Review of PR #352 at 5c3ccac11bc13d9901419f09212020c1bf5d7806 — transcript

Reviewer session 60bb5112-9558-4011-947e-e8cd8784feb8 (claude-fable-5-1), review run 40213876342, 2026-10-25.
Declaration: comment 6400461133 on #352 at 16:55:21Z (expected 120 minutes); forecast row f413a403290b (session_minutes, bound 120, p 0.7) as comment 6400467760.
Scratch copies: `/tmp/rv352.qSwH` (GitHub clone, `make pins`), `/tmp/rv352p.*` (local probe clone), `/tmp/rv352-scripts/` (probe driver); all removed at the end of the session.

## 1. Reproduction (`make pins` on a fresh GitHub clone at 5c3ccac)

```
$ D=$(mktemp -d /tmp/rv352.XXXX) && gh repo clone renavondata/assize "$D" -- -q && git -C "$D" checkout -q 5c3ccac… && make pins   (origin https://github.com/renavondata/assize.git; started 16:59:43Z)
host: thinkpad-agent runner, 8 cores, load average 13–14 throughout (uptime at 18:12Z: 13.18, 13.79, 14.00)
clean phase 16:59Z–17:14Z: 103 run dirs; mutant phase from 17:16Z: 22 at 17:22Z, 55 at 17:27Z, 122 at 17:40Z, 143 at 17:50Z, 220 at 18:01Z, 230 at 18:11Z, 231 at 18:13Z (P14's container mutants, then P15–P38 with 112 mutants, remained)
review.yml: timeout-minutes 120 from the job's 16:53:56Z start → the run was stopped at 18:14Z and the scratch copy removed; make-pins-partial.txt is its buffered log at that moment (103 `[clean ]` lines, 220 `[mutant]` lines).
tally over out/pins/runs/*/{clean,<mutant>/{mutant,twin}}/transcript.log `result:` lines at 18:13:20Z:
  clean results: {'PASS': 103}
  mutant results: {'FAIL': 230, 'incomplete': 1 (P14/floor_unsmoothed, running)}
  twin results: {'PASS': 225, 'FAIL': 5}
  P0bu: clean PASS; compare_skipped, pulled_unchecked, failure_allowed, digests_unpreserved, permissions_widened: mutant FAIL, twin PASS
  unexpected: P0ac — all 5 mutants FAIL with twin FAIL (NON-CAUSAL):
    twin [FAIL] real drafts: findings ['draft #356: draft_price_line: 0 `Price:` lines, want 1 (…)']   (repro-P0ac-price_unwired-twin.log, 17:48:59Z)
    clean [ok] real drafts: findings []                                                                   (17:03:44Z)
    draft #356 "Draft: Wish #341 — measure.yml can run the seal pilot (unblocks #342 3b/3d)" created 2026-10-25T17:28:34Z (author assize-reviewer, the Vizier), no Price: line
```

## 2. Instruction #342: signature and text

```
$ gh issue view 342 → "Draft: Wish #341 — freeze at the seal" | OPEN | author assize-reviewer | labels instruction,draft
$ gh api repos/renavondata/assize/issues/342/timeline (label events)
2026-10-24T19:03:30Z labeled   assize-reviewer draft
2026-10-24T19:03:30Z labeled   assize-reviewer needs-draft-check
2026-10-24T19:05:50Z unlabeled assize-reviewer needs-draft-check
2026-10-24T19:33:43Z labeled   gfrmin instruction
2026-10-25T12:27:04Z unlabeled gfrmin instruction
2026-10-25T12:27:07Z labeled   gfrmin instruction        <- last label event, by gfrmin
$ gh api graphql … issue(number:342){ lastEditedAt editor userContentEdits(last:20){ totalCount nodes } }
{"lastEditedAt":null,"editor":null,"userContentEdits":{"totalCount":0,"nodes":[]}}   <- body never edited
```
Signed (Amendment 4 rule 5). Body ends `Price: guy-items; down; 3`.

Item 3's last pre-stated criterion, verbatim: "The seal pull request touches only `.github/workflows/release.yml`, `CLAUDE.md`, the root `REPORT.md`, `reports/L2/REPORT.md`, `docs/briefs/brief-2-nethack.md` (if item 2 was not merged separately), any pin and mutant that item 3a's criterion needs under `harness/`, and the session's own STATUS, proposer and forecast files."
Item 2 was merged separately: PR #350 (merge a87da71, the base of this PR).

Issue #351 (filed 12:32:32Z by the first Builder session on item 3, run 40193158292, after a probe of P0bm on master 3698abc) names exactly the paths item 3a needs outside that list: `harness/trusted_base.toml`, a brief admission heading, `failed.yml` (or `FAILED_EXEMPT`), and release.yml's own path in `paths:`. Vizier run 40193569863 recommended `closed` at p 0.6 "after Guy amends and re-signs #342 item 3" (comment 6397700178). gfrmin closed #351 at 12:37:54Z with no comment; #342 was not edited (above). A new Builder session (`build run local`, declared on #342 at 14:52:47Z, session 5903f3c7, claude-sonnet-5-5) then built this PR.

## 3. Diff of a87da71..5c3ccac (18 files, +395 −1)

```
 .github/workflows/release.yml                      |  56 ++++++++
 CLAUDE.md                                          |   7 +      (Amendment 6 appended; 0 deletions)
 docs/briefs/brief-2-nethack.md                     |   5 +      (## Admitted by instruction #342; two entries)  <- outside the list
 harness/edits/P0bu_*.toml (5 files)                |  28 +
 harness/pins.py                                    |  80 ++++++++++-   (P0bu, FAILED_EXEMPT["release"])
 harness/proposer.d/instr-342-seal.toml             |   4 +
 harness/trusted_base.toml                          |   2 +      (release.yml; release.yml github.token)        <- outside the list
 reports/L2/REPORT.md                               |  22 +      (## L2c — sealed … NOT obtained)
 reports/L2/ci/40208386791.json                     |   1 +
 reports/L2/forecasts/5903f3c7-….jsonl              |   4 +
 reports/L2/seal/{measure-…-excerpt,measure-…-facts,release-40204564144}.txt | 167 +
 reports/L2/status/instr-342-seal.md                |  20 +
```
Root `REPORT.md`: not touched (no L2 verdict line). `release.yml` `on.push.paths`: `release/**`, `judge/**`, `.github/workflows/release.yml` (the third is not in item 3a's text).
Commits (all author assize-builder; trailers `Instruction: #342`, `Proposer: guy`, `Proposer: builder claude-sonnet-5-5 5903f3c7-…` on each): 21a6b7d (forecasts, proposer row), 0d02f19 (release.yml, P0bu), 4665616 (Amendment 6), f7abe49 (trusted base), 5c3ccac (STATUS, report, witnesses).

## 4. CI runs on the branch (Actions API)

```
pins        40204577146 pull_request 4665616 failure  created 14:56:29Z updated 15:42:51Z   first run; summary: clean_total 103, killed 341, non_causal 6
  P0bm clean: [FAIL] harness/trusted_base.toml equals the tree's declared trusted base, every entry admitted (['unlisted workflow release.yml', 'unlisted token release.yml github.token'])
pins        40208386791 pull_request f7abe49 success  created 15:44:42Z updated 16:52:30Z   summary: clean_total 103, killed 347, leaked 0, stale 0, inconclusive 0, non_causal 0, since a0a4c8b (run 40193268575)
  P0bu: clean ok; mutants compare_skipped, pulled_unchecked, failure_allowed, digests_unpreserved, permissions_widened all KILLED, twins pass (ci-40208386791-P0bu-clean.log)
pins        40213876611 pull_request 5c3ccac success  created 16:53:57Z updated 17:01:41Z   summary: clean_total 13, killed 61, skipped 90, since f7abe49 (run 40208386791)
pins-master 40208385232 pull_request_target f7abe49 failure  (step `make pins` exit 2)
  log: `git checkout origin/master -- harness`; CLEAN FAILED P0bm, P0bs; 8 mutants NON-CAUSAL (P0bm ×6, P0bs ×2)
  P0bm clean: unlisted workflow release.yml, unlisted token release.yml github.token   (pins-master-40208385232-P0bm-clean.log)
  P0bs clean: release.yml (release) is watched by failed.yml or exempt → fails under master's FAILED_EXEMPT (pins-master-40208385232-P0bs-clean.log)
pins-master 40213876509 pull_request_target 5c3ccac failure (completed 17:40:59Z; two earlier attempts on the same head cancelled at creation)
  summary under master's harness: clean_total 102 (no P0bu), killed 334, non_causal 8; P0bm and P0bs clean fail exactly as on f7abe49
release     40204564144 push 4665616 success  created 14:56:18Z; steps 5–8 (Compose, Composed digest equals the seal, Push by digest, Pulled digest equals the seal) success
  log: manifest sha256:c7856fe2cc22222a9c1af4bde31272acd4e4ae4f60bae605c975e75ed918259c
       sealed  sha256:c7856fe2… composed sha256:c7856fe2…
       pulled  sha256:c7856fe2… sealed   sha256:c7856fe2…
  equal to release/seal.toml at master and to reports/L2/seal/release-40204564144.txt
measure     40204672896 pull_request (label `measure`, applied 14:57:43Z by assize-builder) cancelled; runner steel-legend; step 5 `make measure` 14:57:55Z..15:43:12Z (45 min 17 s) "The operation was canceled."
  clean phase 14:57:55Z..15:11:08Z; mutant lines 15:11:08Z..15:41:54Z: 255 `[mutant]` lines (artefact pins.jsonl: 103 clean rows, 265 mutant rows, no summary row); no `pilot` line
  CLEAN FAILED: P0m, P0r, P0x, P0ac, P0bm   (measure-40204672896-*-clean.log)
    P0r:  gh: To use GitHub CLI in a GitHub Actions workflow, set the GH_TOKEN environment variable
    P0x:  real issues not read (gh api … exit status 4);  P0ac: real drafts not read (same)
    P0m:  real branch a87da71..HEAD: commits 21a6b7d, 0d02f19, 4665616 "unsigned_guy: attributed to guy … but git reports ssh 'N', openpgp 'N'" (the signed instruction could not be read; in CI run 40208386791 the same check reads `[ok] real branch a87da71feedc..HEAD: 5 commits; findings []`)
    P0bm: as in run 40204577146 (fixed at f7abe49)
  facts.txt `### head`: c9b0d7d0c6394d4820aa4a9f8edf372a283a881e = GitHub's merge commit "Merge 4665616… into a87da71…" (parents a87da71, 4665616), not a branch commit
  `claims.measure_head_findings(facts, "5c3ccac…")` → [head_differs: artefact measured c9b0d7d0…, reviewed head is 5c3ccac…]; the same against 4665616.
measure.yml at master: `timeout-minutes: 45`, no GH_TOKEN anywhere (pins.yml: `timeout-minutes: 120`, `GH_TOKEN: ${{ github.token }}` on three steps); Makefile `measure`: host facts, `$(MAKE) pins`, then `pilot run` ("The pilot runs only after the pins … pass").
Last successful measure run: 37831165785 (2026-10-08, L1): `PINS PASSED` then `pilot run` then `VERDICT: FIT`.
```

## 5. Probes on the head (local probe clone, PYTHONDONTWRITEBYTECODE=1, python -B)

```
harness.trusted.check(Path(".")) → []
claims.status_check(Path("."), [reports/L2/status/instr-342-seal.md]) → []
claims.PARTY.match: 'reviewer claude-fable-5-1 60bb5112-…' True; 'mechanism harness.ledger 40213876342' True
P0bu in-memory probe (probe-p0bu.py → probe-p0bu.out): control pass; 13 extra mutants all FAIL the pin:
  push_by_tag, steps_reordered, paths_release_dropped, paths_judge_dropped, job_permissions_added, compare_exit_zero,
  pulled_exit_zero, digest_from_elsewhere, if_on_push, output_written_on_failure, pulled_compares_to_itself,
  composed_read_from_image_line.  Probe clone left clean (git status empty).
```

## 6. Forecasts (reports/L2/forecasts/5903f3c7-9d6c-48b2-bac4-d129c02e32f6.jsonl)

```
id            sha256(claim+ts)[:12]  type             args                               ts            p
dca36efd9e1a  ok                     session_minutes  {run: "local", bound: 120}         14:52:46Z     0.4
f63bc964c204  ok                     pins_green       {pr: 352}                          14:58:00Z     0.5
9557f28ae567  ok                     review_accept    {pr: 352}                          14:58:00Z     0.55
cb303c326845  ok                     host_verdict     {layer: 2, verdict: "FIT"}         14:58:00Z     0.85
File added once in 21a6b7d (author date 2026-10-25T16:54:19+02:00 = 14:54:19Z) and never changed on the branch (git log -p: one commit).
PR opened 14:56:26Z; first pins run 40204577146 created 14:56:29Z (failure). Three rows carry ts 14:58:00Z, later than the commit that holds them and than the first run.
harness/ledger.py::_pins_green: "The first `pins` run on the pull request created at or after the forecast concluded success at attempt 1."
```

Resolver (`uv run --frozen python -m harness.ledger resolve --session 40213876342`, exit 0; L2: 97 open, 91 typed; resolved 3, unreadable 0; empty L0/L1 files removed):
```
38e2281e34e9 true   review_accept #350 — reports/L2/review-bb16260… at fcd3889a804b: ACCEPT
dca36efd9e1a false  (void: unobservable) run local: not an Actions run
f63bc964c204 true   pins run 40208386791 attempt 1 on f7abe49dd13d: success     <- the red first run 40204577146 (14:56:29Z) precedes ts 14:58:00Z and is skipped
```
The Builder's STATUS line reads: "pins_green resolves false (the first run, 40204577146 on 4665616, was red on P0bm; green only at f7abe49)".

## 7. Registry reachability from this machine

```
$ skopeo … → command not found
$ podman manifest inspect ghcr.io/renavondata/assize-judge@sha256:c7856fe2…   (anonymous)
Error: … unable to retrieve auth token: invalid username/password: unauthorized
$ podman manifest inspect --authfile <reviewer fine-grained token> …           → denied (fine-grained tokens carry no packages scope)
$ gh api /orgs/renavondata/packages/container/assize-judge → HTTP 403 "Resource not accessible by personal access token"
```
The package is private; the release is witnessed by run 40204564144's log alone.

## 8. Labels and state

```
14:56:40Z labeled constitution (assize-builder); 14:57:43Z labeled measure; 16:53:54Z labeled needs-review, unlabeled measure, labeled awaits-guy (all assize-builder)
gh pr view: mergeable MERGEABLE, mergeStateStatus BLOCKED, autoMergeRequest null, reviewRequests [gfrmin], reviews []
No build run live on the branch at 16:55Z (build 40213876435 completed success, gate only). Merge-base a87da71 = origin/master.
```
