# STATUS — L2 — 2026-10-24 — 8a46d4d — PR #343
VERDICT: SESSION DONE: brief 2 Wish #134 scope 3: `ledger price` reports pins wall-clock per run and its median
LAYER BOUNDARY: no (per A1.3's definition: records no layer verdict in the root REPORT.md; adds or opens no brief)
pins CI run 40126452419 on 8a46d4d: success (reports/L2/ci/40126452419.json)
pins: CI run success, exit 0; the clean/mutant/twin counts were not extracted this session (no summary line read from the CI log); local `make pins` was cut at the 10-minute cloud limit, but its output shows P0t clean ok and P0t/pins_wall_from_queue, pins_wall_failures_dropped, pins_wall_mean each mutant fail, twin pass -> KILLED
changed: harness/ledger.py, harness/pins.py, harness/edits/P0t_pins_wall_{from_queue,failures_dropped,mean}.toml, harness/proposer.d/l2-wish134-price-wallclock.toml, reports/L2/{forecasts/c95de76e-….jsonl,ci/40126452419.json,status/l2-wish134-price-wallclock.md}
did: candidates: #320 skipped (held by PR #322, `claims next`); took master STATUS `next`, Wish #134 scope 3; `harness.chooser choose` ran (one candidate, regime fixed-order), rows in the forecasts file, `chose:` line in the code commit
did: `Price.pins_wall` (run id, minutes from run start, oldest first, failed runs kept, skipped runs and runs outside the window out) and `pins_wall_lines()`; `ledger price` prints them and the median beside `pins CI minutes`; live `ledger price --since 384211a` printed "pins wall-clock median none over 0 runs"
did: P0t extended with a fixture (queued run, failed run, skipped run, run before the window); three mutants: wall-clock from creation, failures dropped, mean for median
did: denials none. Deviation from #110: the three mutant TOML files were created by shell heredoc, not the Write tool; content is the same. The `price:` STATUS line is unchanged, so the `price_line` check is untouched. Criteria of the amendment (record identity at N=1/N=8, speed vs ubuntu-latest) and scopes 1-2 are not this item
decided (not asked): wall-clock is reported per run and as a median in the `ledger price` body, not added to the one-line `price:` STATUS line (its form is pinned by P0t and the claims check) — p(stands on review)=0.75
decided (not asked): every non-skipped pins run is reported, failed ones included; the "full runs" subset of the speed criterion is not separable from the API data, so selection is left to the reader of the list — p(stands on review)=0.6
forecasts: made 8 on #343 (4 chooser rows; pins_green 0.8, review_accept 0.7, host_verdict L2 FIT 0.35, session_minutes 60 at 0.55); pins_green resolves 1 (run 40126452419 success); session_minutes resolves 0 (start 19:29:30Z, STATUS written near 20:30Z, past 60 minutes waiting on CI); cumulative log-loss not recomputed here
price: guy-items 0; guy-latency median 0.0h max 0.0h; sessions 0; runner-min 0
obligations added: L2b: the speed criterion's "full runs" cannot be told from the API fields `ledger price` reads; a pin on the selection is needed when the criterion is first measured
NEEDS YOU (at most 1): none
next: Wish #134 remaining scopes per the brief (self-hosted `pins` runner registration is Guy's alone, stop if absent); every Builder on master runs `harness.chooser choose`
