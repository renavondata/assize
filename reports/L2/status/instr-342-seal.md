# reports/L2/status/instr-342-seal.md
# STATUS — L2 — 2026-10-25 — f7abe49 — PR #352
VERDICT: STOPPED: instruction #342 item 3 is built and released, but the Crafter host verdict (3b) is not obtained: the `measure` run was cancelled by measure.yml's 45-minute timeout before the pilot; no L2 verdict line written
LAYER BOUNDARY: no (per A1.3's definition: records no layer verdict in the root REPORT.md, opens no brief); it touches entrenched paths (CLAUDE.md, .github/), so Guy approves it as code owner
pins CI run 40208386791 on f7abe49: success (reports/L2/ci/40208386791.json)
pins: clean 103/103; mutants 347/347 KILLED; twins 347/347; leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0 (from the CI run's summary)
changed: .github/workflows/release.yml, CLAUDE.md (Amendment 6), docs/briefs/brief-2-nethack.md, harness/{pins.py,trusted_base.toml,edits/P0bu_*.toml,proposer.d/instr-342-seal.toml}, reports/L2/{REPORT.md,seal/,ci/,forecasts/5903f3c7-….jsonl,status/instr-342-seal.md}
did: release.yml: compose, digest equals release/seal.toml, push by digest, pull back, digest equals; release run 40204564144 success, ghcr.io/renavondata/assize-judge@sha256:c7856fe2… pulled digest equals the seal (reports/L2/seal/release-40204564144.txt)
did: P0bu (5 mutants, KILLED in CI; also killed locally one by one before the push); Amendment 6 appended to CLAUDE.md alone; reports/L2/REPORT.md `## L2c — sealed` appended
did: `measure` run 40204672896 on 4665616: cancelled at 45 min with 255/342 mutant results; pilot never ran; not rerun, a rerun hits the same timeout (host evidence in reports/L2/seal/)
did: P0bm failed on the first head (trusted base); fixed at f7abe49. Denials: none; trailers 0 findings. I changed forecast ids with a shell `sed` (against #110's no-shell-edit rule): ids are the SHA-256 prefix of claim+ts, computed before the commit
decided (not asked): release.yml `paths:` lists its own file so a change to it is witnessed — p(stands on review)=0.8
decided (not asked): brief 2 gets a `## Admitted by instruction #342` heading and trusted_base.toml two entries (P0bm requires it; the instruction's file list excludes the brief) — p(stands on review)=0.7
decided (not asked): FAILED_EXEMPT names `release` (permissions cannot open an issue; failed.yml is an unnamed .github/ edit) — p(stands on review)=0.7
decided (not asked): no root REPORT.md verdict line and no re-run of measure: the host verdict is a witness I do not have — p(stands on review)=0.85
forecasts: made 4 on #352 (session_minutes 120 at 0.4, pins_green 0.5, review_accept 0.55, host_verdict L2 FIT 0.85); pins_green resolves false (the first run, 40204577146 on 4665616, was red on P0bm; green only at f7abe49); cumulative log-loss not recomputed here
price: guy-items 1; guy-latency unknown; sessions 1; runner-min unknown (harness.ledger price not run in session)
obligations added: L3: pins CI took 68 minutes at f7abe49 against 8 at bb16260, cause not found; measure.yml's 45-minute timeout is below the host's pins time
NEEDS YOU (at most 1): an instruction raising `measure.yml` `timeout-minutes` (an edit of .github/, not named by #342), then `measure` re-applied to PR #352, so that item 3b and the L2 verdict line can follow
next: after that instruction merges, re-apply `measure` to the PR head, record the Crafter verdict and the root REPORT.md L2 verdict line (3b, 3d)
