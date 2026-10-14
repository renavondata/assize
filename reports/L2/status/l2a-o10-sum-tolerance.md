# STATUS — L2 — 2026-10-14 — e25a666 — PR #197
VERDICT: SESSION DONE: L2a obligation 10 delivered; pins green on e25a666 (pins CI run 38627704902 on e25a666: success, reports/L2/ci/38627704902.json)
LAYER BOUNDARY: no (per A1.3's definition: records no layer verdict; adds or opens no brief)
pins: clean 70/70; mutants 195/195 KILLED; twins 195/195; leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0 (full run in CI 38627704902; local make pins not run, over 10 minutes; P27 clean 0.73s, tolerance_loose and tolerance_zero KILLED with passing twins in that run)
changed: harness/pins.py, harness/edits/P27_{tolerance_loose,tolerance_zero}.toml, judge/README.md, harness/proposer.d/l2a-o10-sum-tolerance.toml, reports/L2/{forecasts/0170ff38-….jsonl,ci/38627704902.json,status/l2a-o10-sum-tolerance.md}
did: `claims next #113 'L2a obligation 9'`: #113 held by PR #185; obligation 9 held by PR #196 (opened during this session's queue, by title and STATUS; `claims next` did not see it); took L2a obligation 10 (review c2a87f6478ad F3); no switchback seed, so the first open candidate
did: new pin P27: for every support size of every bound World, sums 1 ± 2·n·ε invalid, 1 ± n·ε valid, and the worst of 200 seeded naive-summed softmaxes (2ε from one at n=10, both orders) valid; mutants tolerance_loose (0.5), tolerance_zero (0)
did: judge/scoring.py unchanged (the bound was already right; only its pin was missing); judge/README.md names P27
did: pins-master run 38627705029 failed on this head as on every PR (master's workflow, entrenched); not mine to change
decided (not asked): P27 calls `scoring.invalid` directly, not through a container episode; P7's `zeros`/`sum_unchecked` already witness that an invalid prediction ends `invalid_reply` — p(stands on review)=0.75
decided (not asked): "just inside" is both 1 ± n·ε (bound inclusive) and the adversarial softmax, the review naming only the latter — p=0.8
decided (not asked): new pin P27 rather than extending P7, so the check runs in under a second with no runtime and avoids P7's container cost — p=0.85
forecasts: made 4 (pins_green #197 p=0.7, review_accept #197 p=0.7, host_verdict L2 FIT p=0.35, session_minutes bound 60 p=0.5); resolved 0; see `ledger proposer builder`
price: guy-items 0; guy-latency median 0.0h max 0.0h; sessions 1; runner-min 27 (pins CI of the green run)
obligations added: L3: none. L2: obligations 11+ remain (L2a obligation 11 next, once not held)
NEEDS YOU (at most 1): none
next: L2a obligation 11 (missing predictions are unpriced in comparisons); #113 (PR #185) and obligation 9 (PR #196) are held
