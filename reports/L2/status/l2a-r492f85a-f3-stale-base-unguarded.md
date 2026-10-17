# reports/L2/status/l2a-r492f85a-f3-stale-base-unguarded.md
# STATUS — L2 — 2026-10-17 — eb3c674 — PR #235
VERDICT: SESSION DONE: review 492f85a F3 (P0bg lacks a mutant dropping the `base is not None` guard on `stale_exemptions`) is built and discharged by P0bg's mutant `stale_base_unguarded`, KILLED with a passing clean twin
LAYER BOUNDARY: no (per A1.3's definition: records no layer verdict; adds or opens no brief)
pins CI run 39053553255 on eb3c674: success (reports/L2/ci/39053553255.json)
pins: clean (CI run above green; local P0bg only: clean passes, mutant fails with CalledProcessError on `git rev-list None..HEAD`); full-suite counts are in the CI artefact
changed: harness/{pins.py,edits/P0bg_stale_base_unguarded.toml,proposer.d/l2a-r492f85a-f3-stale-base-unguarded.toml}, reports/L2/{forecasts/101af9f7-….jsonl,ci/39053553255.json,status/l2a-r492f85a-f3-stale-base-unguarded.md}
did: skipped L2a obligation 33 (held by open PR #234); `claims next 33 34 35` printed 33 as free, since #234's STATUS is not yet on master
did: P0bg registers a second mutant, `stale_base_unguarded` (removes the guard at `_p0m_real_branch`'s `stale` line); the P0bg probe already used a non-empty exemption table, so the unguarded call is reached
did: local witness, copy of the tree in /tmp (not retained): clean P0bg True; with the edit applied P0bg False, "does not raise" fails with CalledProcessError
did: no tool call was denied; the first push was refused by pre-push (trailer block not contiguous) and answered by amending the unpushed commit
decided (not asked): took F3 rather than obligation 34, because 34 edits P14 beside #234 and needs its exact p value — p(stands on review)=0.8
decided (not asked): no `make pins` locally (15–20 min exceeds the cloud limit); CI run 39053553255 is the whole-suite witness — p(stands on review)=0.85
forecasts: made 4 (pins_green #235 p=0.7, review_accept #235 p=0.7, host_verdict L2 FIT p=0.35, session_minutes local bound 30 p=0.5); resolved none this session; cumulative log-loss not recomputed here
price: guy-items 0; guy-latency median 0.0h max 0.0h; sessions 0; runner-min 0
obligations added: L2a: review 492f85a F4 remains open (the review procedure's open-forecast counter crashes on legacy `resolves` rows)
NEEDS YOU (at most 1): none
next: L2a obligation 33 (PR #234, pending review), then 34 (P14 low power), 35 (pilot cap checked only between requests); review 492f85a F4
