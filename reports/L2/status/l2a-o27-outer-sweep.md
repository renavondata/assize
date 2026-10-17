# STATUS — L2 — 2026-10-17 — 083c4c5 — PR #227
VERDICT: SESSION DONE: L2a obligation 27 (`run_under_edits` neither sets the subreaper nor sweeps) discharged by P0bc
LAYER BOUNDARY: no (per A1.3's definition: records no layer verdict; adds or opens no brief)
pins: clean 79/79; mutants 224/224 KILLED; twins 224/224; leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0 (pins CI run 38988622010 on 083c4c5: success (reports/L2/ci/38988622010.json); local make pins transcript reports/L2/builder/083c4c5d2d7b7f20c663c3d8d9715f150c39a27a/make-pins.txt)
changed: harness/runner.py, harness/pins.py, harness/registries.py, harness/fixtures/orphaner.py, harness/edits/P0bc_{outer_sweep_removed,outer_subreaper_not_set}.toml, harness/proposer.d/l2a-o27-outer-sweep.toml, reports/L2/{forecasts/b9b95b17-….jsonl,ci/38988622010.json,builder/083c4c5…/,status/l2a-o27-outer-sweep.md}
did: no open instruction issue; `claims next 26 27 28 29 30` gave 27; skipped 26, held by PR #226
did: `run --under-edits` now starts runtime infrastructure, arms PR_SET_CHILD_SUBREAPER and sweeps after the inner run, before the copy is removed; records {edits, inner_exit, leaked_processes} in out/under-edits.json; exits non-zero on a leak
did: P0bc (fixture.orphaner: a clean check leaves fixture.daemon's daemon, then SIGKILLs its orchestrator); mutants outer_sweep_removed and outer_subreaper_not_set KILLED, each failing on "daemon dead" and "leaked_processes >= 1"
did: the make-pins transcript was copied into reports/ with `cp` (39 kB, not retyped through Write); no other file was written by shell; no tool call was denied
decided (not asked): item is obligation 27, the first open brief item no PR holds; the chooser seed is absent, so the first candidate — p(stands on review)=0.9
decided (not asked): the leak is reported in a separate under-edits.json, not as a row in pins.jsonl, so readers of pins.jsonl see no new row kind — p=0.75
decided (not asked): new pin P0bc rather than a P0h case, and its code placed away from PR #226's hunks in pins.py, runner.py and registries.py, so the two merge without conflict — p=0.8
chose: reports/switchback-seed.txt absent; first candidate taken (L2a obligation 27)
forecasts: made 4 (pins_green #227 p=0.7, review_accept #227 p=0.75, host_verdict L2 FIT p=0.35, session_minutes run 38986068042 bound 90 p=0.55); resolved 0
price: guy-items 0; guy-latency median 0.0h max 0.0h; sessions 2; runner-min 31
obligations added: L3: none
NEEDS YOU (at most 1): none
next: L2a obligation 26 if PR #226 does not merge, else obligation 28 (the `Overlap` assertion has no pin)
