# STATUS — L2 — 2026-10-17 — 86a0edb — PR #236
VERDICT: SESSION DONE: L2a obligation 35 (the pilot can return a verdict with wall_s > cap_s, because the cap is checked only between requests; R 571ee563f91d F2) is built: `pilot/run.py` `report` stops a pilot whose wall-clock passed its cap, and P18's mutant `cap_overrun_admitted` is KILLED with a passing twin
LAYER BOUNDARY: no (per A1.3's definition: records no layer verdict; adds or opens no brief)
pins CI run 39060153984 on 86a0edb: success (reports/L2/ci/39060153984.json)
pins: clean 83/83; mutants 234/234 KILLED; twins 234/234; leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0 (summary row of the run's pins-report artefact, skipped 0)
changed: pilot/run.py, harness/{pins.py,edits/P18_cap_overrun_admitted.toml,proposer.d/l2a-o35-cap-overrun.toml}, reports/L2/{forecasts/bbdce2cc-….jsonl,ci/39060153984.json,status/l2a-o35-cap-overrun.md}
did: skipped L2a obligation 33 (held by open PR #234; `claims next 33 34 35` printed 33, since #234's STATUS is not on master); no switchback seed, so no `chooser choose`
did: `report` adds `cap: <cap> s passed during the last request, at <wall_s> s` as a stop reason when `played.wall_s > cap_s`; every record is kept, no time-to-learn row, verdict STOPPED (the obligation's "the report refuses a verdict when wall_s > cap_s")
did: P18's overrun pilot: fake clock at cap/8 per reading, three requests, last pre-request check at 7/8 cap, end at 1250 s of 1000 s; local scratch-copy witness (not retained): clean P18 True; `cap_overrun_admitted` P18 False at that expectation only (verdict FIT); `cap_ignored` still False
did: no tool call was denied; no push was refused
decided (not asked): skipped obligation 34 (P14 low power) because it edits P14 beside #234's change to P14's p value, as the previous session did — p(stands on review)=0.8
decided (not asked): the check sits in `report`, not `play`, so any `Played` past its cap is refused whoever built it; message starts `cap:` like the pre-request stop — p(stands on review)=0.8
decided (not asked): no local `make pins` (a harness/ change runs the full suite, about 45 min in CI, over the cloud limit); CI run 39060153984 is the whole-suite witness — p(stands on review)=0.85
forecasts: made 4 (pins_green #236 p=0.75, review_accept #236 p=0.75, host_verdict L2 FIT p=0.35, session_minutes run 39059848278 bound 45 p=0.6); resolved none this session; cumulative log-loss not recomputed here
price: guy-items 1; guy-latency median 0.7h max 0.7h; sessions 0; runner-min 0
obligations added: L2a: review ef1e03c F4 (P0bg mutant `commits_base_unguarded`) and F7 (review workflow's git identity) remain open
NEEDS YOU (at most 1): none
next: L2a obligation 33 (PR #234, pending review), then 34 (P14 low power), 36 (`pilot/__main__.py` paths unpinned); review ef1e03c F4; review 492f85a F4
