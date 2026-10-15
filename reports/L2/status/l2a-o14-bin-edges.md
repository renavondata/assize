# STATUS — L2 — 2026-10-15 — 55a153a — PR #201
VERDICT: SESSION DONE: L2a obligation 14 delivered (review 7e18816c626e F2); pins green on 55a153a (pins CI run 38655748759 on 55a153a: success, reports/L2/ci/38655748759.json)
LAYER BOUNDARY: no (per A1.3's definition: records no layer verdict; adds or opens no brief)
pins: clean 71/71; mutants 202/202 KILLED; twins 202/202; leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0 (local `make pins` on 55a153a, reports/L2/builder/55a153adbcef65e941c1b5127d5ea26acbb0378b/make-pins.txt; CI 38655748759 the same counts; P13/bin_product_rounded and P13/bin_exact_rational KILLED, twins pass, in both)
changed: judge/scoring.py, judge/README.md, harness/pins.py, harness/README.md, harness/edits/P13_{bin_product_rounded,bin_exact_rational}.toml, harness/proposer.d/l2a-o14-bin-edges.toml, reports/L2/{forecasts/bb94375a-….jsonl,ci/38655748759.json,builder/55a153a…/,status/l2a-o14-bin-edges.md}
did: `claims next '#113' 'L2a obligation 10'`: #113 held by PR #185; obligation 10 not held but already discharged by PR #197 (P27, merged a8c6a7c); 11, 12 merged (#198, #199); 13 held by PR #200 (by title; `claims next` does not see it); took obligation 14. No switchback seed, so the first open candidate
did: `scoring.bin_of` now compares q with the double edges `b / bins` (bisect) instead of `int(q*bins)`, which put 0.3*3 = 0.8999999999999999 in bin 9; P13 feeds a two-valued target q and 1 − q at the doubles below, at and above every edge, and 0.3*3, against `_calibration_by_definition`, the one statement of the rule, which the forecaster derivation now also uses; non-vacuity checks that both rival rules bin some of these probabilities elsewhere
did: witness copied from /tmp by `cp` (a transcript, not an edit); pins-master run 38655748594 failed on this head as on every PR (master's entrenched workflow). No tool denial
decided (not asked): obligation 10 (master STATUS `next`) is done, so taken as discharged, not redone — p(stands on review)=0.9
decided (not asked): the one rule is the double edges `b / bins`, the docstring's and derivation's, not the exact rational q·bins (which bins a prediction of 0.3 at 2); both losers are mutants — p=0.75
decided (not asked): extend P13 as the obligation names, not a new pin, and call `scoring.calibration` directly (P7 already checks the loop's record against the same derivation) — p=0.85
forecasts: made 4 (pins_green #201 p=0.7, review_accept #201 p=0.7, host_verdict L2 FIT p=0.35, session_minutes bound 120 p=0.6); resolved 0; see `ledger proposer builder`
price: guy-items 0; guy-latency median 0.0h max 0.0h; sessions 1; runner-min 0 (`ledger price --since add902a`, read before the CI run's minutes were posted)
obligations added: L3: none
NEEDS YOU (at most 1): none
next: L2a obligation 15 of reports/L1/REPORT.md (P10 has no clean case that records and counts `leaked`); #113 (PR #185) and obligation 13 (PR #200) are held
