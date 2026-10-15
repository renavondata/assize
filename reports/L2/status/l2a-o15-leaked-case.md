# STATUS — L2 — 2026-10-15 — 28ef714 — PR #202
VERDICT: SESSION DONE: L2a obligation 15 delivered (review 2402ed7d56a5 F3); pins green locally on 28ef714 (CI run to follow on the PR head)
LAYER BOUNDARY: no (per A1.3's definition: records no layer verdict; adds or opens no brief)
pins: clean 71/71; mutants 203/203 KILLED; twins 203/203; leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0 (local `make pins` on 28ef714ac517, reports/L2/builder/28ef714ac5178fe8b5294f734a62f946f3d107a3/make-pins.txt; P10/leaked_not_recorded KILLED, twin passes)
changed: harness/pins.py, harness/edits/P10_leaked_not_recorded.toml, harness/proposer.d/l2a-o15-leaked-case.toml, reports/L2/{forecasts/d59a5e40-….jsonl,builder/28ef714…/,status/l2a-o15-leaked-case.md}
did: `claims next '#113' 'L2a obligation 15'`: #113 held by PR #185; took obligation 15 (obligation 13 held by PR #200, by title). No switchback seed, so the first open candidate
did: P10 makes the runtime's remove command a no-op in its own thread (thread-local, so the other runtime's thread is untouched) and plays a stubborn candidate (failed-episode site) and two polite Worlds (final-container site); asserts `leaked` only on the episode whose container stayed listed, every World a record, the container still listed as control; each case removes what it leaked
did: mutant `leaked_not_recorded` removes both `leaked` assignments in judge/episodes.py. Witness copied by `cp` (a transcript, not an edit). No tool denial
decided (not asked): patch `runtime.remove_argv` in the pin rather than add a test seam to the judge, so judge/ is unchanged — p(stands on review)=0.85
decided (not asked): cover both teardown sites in P10 with one mutant removing both assignments, as the finding names — p=0.8
forecasts: made 4 (pins_green #202 p=0.7, review_accept #202 p=0.7, host_verdict L2 FIT p=0.35, session_minutes bound 90 p=0.6); resolved 0; see `ledger proposer builder`
price: guy-items 0; guy-latency median 0.0h max 0.0h; sessions 1; runner-min 0 (not read this session)
obligations added: L3: none
NEEDS YOU (at most 1): none
next: L2a obligation 16 of reports/L1/REPORT.md (an exception escaping `episodes.run()` skips teardown); #113 (PR #185) and obligation 13 (PR #200) are held
