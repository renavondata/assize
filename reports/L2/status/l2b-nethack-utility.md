# STATUS — L2 — 2026-10-21 — 673588d — PR #306
VERDICT: SESSION DONE: brief 2 §2 Utility is built: BALROG's progression vendored unmodified at b7afe79e3e42 with a SHA-256 per file; P37 (brief P4) kills five mutants
LAYER BOUNDARY: no (per A1.3's definition: records no layer verdict; adds or opens no brief)
pins CI run 39665687395 on 673588d: success (reports/L2/ci/39665687395.json)
pins: clean 96/96; mutants 315/315 KILLED; twins 315/315; leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0 (reports/L2/build/l2b-nethack-utility/ci-39665687395-summary.txt)
changed: worlds/nethack/{binding.py,README.md,balrog/{progress.py,achievements.json,LICENSE}}, harness/pins.py, harness/edits/P37_*.toml (5), harness/edits/P36_{moon_from_clock,character_fixed}.toml, harness/proposer.d/l2b-nethack-utility.toml, reports/L2/{forecasts/66463860-01ce-4c86-b7bb-4ca23bb857f6.jsonl,ci/39665687395.json,build/l2b-nethack-utility/,status/l2b-nethack-utility.md}
did: no instruction issue open; `claims next` gave master STATUS `next` (brief 2 §2 Utility), held by no PR; no awaits-guy PR open; reports/switchback-seed.txt absent, so no chooser run
did: vendored balrog/environments/nle/{progress.py,achievements.json} and LICENSE (MIT) byte for byte; `binding.balrog()` loads the module only when every file has its recorded SHA-256 and the loaded table is the checked one; each Episode holds BALROG's `Progress` and feeds it (obs, reward, done, info) every step, as BALROG's NLE wrapper does; the env also emits `tty_chars` for Progress's end reason, outside the hashed observation
did: P37: record and files equal the pin's committed commit and checksums; a copy with one table entry altered, and one with the code altered, are refused; seeds 1/3 (P36's streams) give utility 0.0 and the `Dlvl:2` entry. Local transcript reports/L2/build/l2b-nethack-utility/local-p37-clean.txt
did: first CI run 39661407109 on d772564 failed: P36 `moon_from_clock` and `character_fixed` STALE, since their anchor line in make_env changed (same in the local run, reports/L2/build/l2b-nethack-utility/local-pins-d772564.txt); re-anchored in 673588d, same mutations
did: forecasts appended before the first pins run; the session_minutes forecast (120 min) will probably resolve 0: two full CI runs were ~45–60 min each
decided (not asked): registry id P37 for brief P4 (P4 is L1's cgroup pin; P35 is PR #301's, P36 is the determinism pin) — p(stands on review)=0.85
decided (not asked): vendor under worlds/nethack/balrog/ with the checksums in binding.py and duplicated as goldens in the pin, so a mutant that moves table and record together is still KILLED — p=0.8
decided (not asked): load the vendored module by path after verification, rather than a git submodule (brief A1 item 2 names a submodule for AutoAscend only) — p=0.75
decided (not asked): utility kept in BALROG's own units [0, 1]; whether δ ∈ {1,2,5} reads as percentage points (BALROG reports ×100) is decided with the time-to-learn config, before any run — p=0.7
decided (not asked): P36's two edit files re-anchored rather than keeping make_env's line unchanged; the mutation is identical — p=0.85
forecasts: made 4 (pins_green #306 p=0.7, review_accept #306 p=0.65, host_verdict L2 FIT p=0.35, session_minutes 120 p=0.6); resolved 0 this session; cumulative log-loss not recomputed here
price: guy-items 0; guy-latency median 0.0h max 0.0h; sessions 0; runner-min 0 (`ledger price --since f5ad950`)
obligations added: L3: none
NEEDS YOU (at most 1): none
next: brief 2 §2 Prediction targets: declare next-step categorical targets with finite support (dungeon level, experience level, hunger state at t+1) and their rationale, then price and manifest.json
