# STATUS — L2 — 2026-10-18 — c07d4c0 — PR #248
VERDICT: SESSION DONE: L2a obligation 34 (P14 has low power against small departures, R d3c24bf7133f F2); P14 now also refuses an incumbent that never plays a legal action; mutant `P14/one_action_dropped` KILLED with a passing twin
LAYER BOUNDARY: no (per A1.3's definition: records no layer verdict; adds or opens no brief)
pins CI run 39141025004 on c07d4c0: success (reports/L2/ci/39141025004.json)
pins: clean 84/84; mutants 240/240 KILLED; twins 240/240; leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0 (summary row of the run's pins-report artefact, skipped 0)
changed: harness/{pins.py,README.md,edits/P14_one_action_dropped.toml,proposer.d/l2a-o34-p14-coverage.toml}, reports/L2/{forecasts/c689ca4e-….jsonl,ci/39141025004.json,status/l2a-o34-p14-coverage.md}
did: no open `instruction` issue; `claims next` took obligation 34 (PR #247 holds 36); `reports/switchback-seed.txt` absent, so the first candidate of master STATUS's `next` was taken
did: coverage test over 500 draws (5 episodes): every action played, false-failure probability of a uniform agent exact by inclusion–exclusion (`_some_cell_empty_sf`), asserted below UNIFORM_ALPHA=1e-6 at the draws actually played (275 is the least); Pearson stays exact over the first 200 (exact p at 300 draws did not finish in 2 minutes)
did: first head c95bddb (3 episodes) failed pins run 39136961259: the third episode died at step 60 (also 64 in a local run), 260 draws left miss probability 2.43e-6, `floor_unsmoothed` twin failed, NON-CAUSAL; fixed with five episodes in c07d4c0. Local P14 (transcript: this session's tool output): clean True; with `one_action_dropped` applied, only the coverage assertion fails (Pearson passes), 500 draws, action 16 unplayed
did: no tool call was denied; one push was refused by the pre-push hook (blank line split the trailer block) and answered by recommitting
decided (not asked): coverage test plus extra episodes rather than a longer host run — it kills the named mutant in the cloud, with exact false-failure probability — p(stands on review)=0.75
decided (not asked): five episodes, not three or four, because a random agent dies early in a seed-3 episode in roughly 2 of 10 runs — p(stands on review)=0.8
forecasts: made 4 (pins_green #248 p=0.65, review_accept #248 p=0.7, host_verdict L2 FIT p=0.35, session_minutes run 39136337928 bound 90 p=0.6); pins_green is false as made on the first head (run 39136961259 failed); cumulative log-loss not recomputed here
price: guy-items 0; guy-latency median 0.0h max 0.0h; sessions 1; runner-min 120
obligations added: none
NEEDS YOU (at most 1): none
next: review ef1e03c F4; review 492f85a F4; L2a obligation 36 if PR #247 is not merged
