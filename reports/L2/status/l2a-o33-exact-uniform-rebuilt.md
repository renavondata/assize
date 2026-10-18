# STATUS — L2 — 2026-10-18 — 2fc893a — PR #246
VERDICT: SESSION DONE: L2a obligation 33 (P14 uses an asymptotic χ² p-value, R d3c24bf7133f F1) rebuilt from master by cherry-picking 98bea19 of closed PR #234, as Guy directed; P14's uniformity p value is the exact multinomial tail; mutant `P14/asymptotic_p` KILLED with a passing twin
LAYER BOUNDARY: no (per A1.3's definition: records no layer verdict; adds or opens no brief)
pins CI run 39127942072 on 2fc893a: success (reports/L2/ci/39127942072.json)
pins: clean 84/84; mutants 239/239 KILLED; twins 239/239; leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0 (summary row of the run's pins-report artefact, skipped 0)
changed: harness/{pins.py,README.md,edits/P14_asymptotic_p.toml,proposer.d/l2a-o33-exact-uniform-rebuilt.toml}, reports/L2/{forecasts/e5c2325f-….jsonl,ci/39127942072.json,status/l2a-o33-exact-uniform-rebuilt.md}
did: no open `instruction` issue; #239 and #240 already closed (PRs #241, #242 merged); no open PR held any candidate (`claims next 'L2a obligation 33'` printed it); `reports/switchback-seed.txt` absent, so the first candidate of master STATUS's `next` was taken
did: Guy closed #234 ("obligation 33 to be rebuilt from master by cherry-picking 98bea19 once the PARTY fix merges"); PR #241 (the PARTY fix) has merged; 98bea19 cherry-picked onto 0d02d34 without conflict
did: `git patch-id --stable` of 98bea19's code paths and of 2fc893a's: both d215d77b8ab50d011826219b9d9e0341d1d68886; the old proposer row and forecasts file of PR #234 are not carried; both builders are trailers on the code commit
did: no tool call was denied; no push was refused
decided (not asked): new branch `l2a-o33-exact-uniform-rebuilt` and new PR, after the obligation 19 precedent (PR #223 rebuilt from closed #217) — p(stands on review)=0.9
decided (not asked): no local `make pins` (harness/pins.py change, whole suite over the cloud limit); CI run 39127942072 is the whole-suite witness — p(stands on review)=0.85
forecasts: made 4 (pins_green #246 p=0.75, review_accept #246 p=0.8, host_verdict L2 FIT p=0.35, session_minutes run 39124337896 bound 90 p=0.55); resolved none this session; cumulative log-loss not recomputed here
price: guy-items 1; guy-latency median 0.0h max 0.0h; sessions 3; runner-min 145
obligations added: none
NEEDS YOU (at most 1): none
next: L2a obligation 34 (P14 low power, R d3c24bf7133f F2); 36 (`pilot/__main__.py` paths unpinned); review ef1e03c F4; review 492f85a F4
