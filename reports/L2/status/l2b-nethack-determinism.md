# STATUS — L2 — 2026-10-21 — 1cd7c62 — PR #305
VERDICT: SESSION DONE: brief 2 §2's Versions and Determinism are built: nle 1.3.0 / NetHack 3.6.7 recorded, NetHackChallenge seeded deterministically whatever the date; P36 kills six mutants
LAYER BOUNDARY: no (per A1.3's definition: records no layer verdict; adds or opens no brief)
pins CI run 39646656800 on 1cd7c62: success (reports/L2/ci/39646656800.json)
pins: clean 95/95; mutants 310/310 KILLED; twins 310/310; leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0 (reports/L2/build/l2b-nethack-determinism/ci-39646656800-summary.txt)
changed: pyproject.toml, uv.lock, worlds/nethack/{binding.py,README.md}, harness/pins.py, harness/edits/P36_*.toml (6), harness/proposer.d/l2b-nethack-determinism.toml, reports/L2/{forecasts/ff8d2cc9-99b9-4cab-a423-1bc227394ea9.jsonl,ci/39646656800.json,build/l2b-nethack-determinism/,status/l2b-nethack-determinism.md}
did: no signed instruction open; master STATUS `next` (#296 reviewed) is done; brief item zero-diff pin skipped, held by PR #301; audit 8aae43c findings 2–3 need `.github/` (entrenched); so took brief 2 §2; no awaits-guy PR open; reports/switchback-seed.txt absent, no chooser run
did: NetHackChallenge refuses every seed; the binding lifts the lock on its instance, seeds core/disp/lgen from the issued seed with reseeding off, and sets NLE's `fix_moon_phase` (the game otherwise reads moon phase and Friday 13th from the date)
did: P36: one hash per seed twice per process and across two processes, equal to goldens for seeds 1/7/12 (ordinary day, new moon, full moon, so `moon_from_clock` fails on any date); each 2000-action stream plays to the game's end; versions checked against the install and uv.lock
did: local: clean phase 95/95 and each mutant failing the check (reports/L2/build/l2b-nethack-determinism/local-p36.txt); first `seed_lock_kept` form crashed the child (would be INCONCLUSIVE), reshaped to record the error
decided (not asked): took §2 by fixed order although wish #300 asks the seal first: its draft #303 is unsigned; a NetHack binding touches no `judge/` or `worlds/spec/` path, so it is valid under either order — p(stands on review)=0.7
decided (not asked): split §2: versions + determinism now, no manifest.json, so the judge does not bind NetHack until utility/targets/price exist — p=0.8
decided (not asked): the World is NetHackChallenge with its seed lock lifted and `fix_moon_phase` on (the brief's own Determinism requires both); recorded in binding docstring and README — p=0.75
decided (not asked): new registry id P36 (P35 is PR #301's); witnesses JUDGE_SIDE — p=0.85
decided (not asked): REPORT.md not touched (PR #301 appends its L2b section; the NetHack report lands with the verdict) — p=0.8
forecasts: made 4 (pins_green #305, review_accept #305, host_verdict L2 FIT, session_minutes); resolved 0 this session; cumulative log-loss not recomputed here
price: guy-items 0; guy-latency median 0.0h max 0.0h; sessions 0; runner-min 0 (`ledger price --since 342af43`, which counts nothing yet for this session)
obligations added: L3: none
NEEDS YOU (at most 1): none
next: brief 2 §2 Utility: vendor BALROG's progression and its tables at a pinned commit with a checksum (brief P4), then targets, price, manifest.json
