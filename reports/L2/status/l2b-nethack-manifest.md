# STATUS — L2 — 2026-10-22 — 465dd42 — PR #318
VERDICT: SESSION DONE: NetHack's manifest (observations, three prediction targets with derived supports, price) committed; the judge binds and prices NetHack; P38 holds it
LAYER BOUNDARY: no (per A1.3's definition: records no layer verdict in the root REPORT.md; adds or opens no brief)
pins CI run 39827843820 on 465dd42: success (reports/L2/ci/39827843820.json)
pins: clean 99/99; mutants 329/329 KILLED; twins 329/329; leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0 (CI artifact pins.jsonl summary row; skipped 0 pins, 0 mutants)
changed: worlds/nethack/{manifest.json,binding.py,README.md}, harness/pins.py (P38; P19's bound set; P36 child reads `time`), harness/edits/P38_*.toml, harness/proposer.d/l2b-nethack-manifest.toml, reports/L2/{forecasts/dcc9778c-….jsonl,ci/39827843820.json,witness/l2b-nethack-manifest/,status/l2b-nethack-manifest.md}
did: candidates in order: #315 skipped (held by PR #316, awaits-guy); STATUS next #303 closed; L2c's outstanding parts are Guy's (#316 CODEOWNERS; #317 measure.yml shallow checkout, which fails 7 git-history pins on the host and blocks the Crafter host verdict); took L2b brief 2 §2's next unbuilt item. No `chooser` (reports/switchback-seed.txt absent)
did: manifest: glyphs, `toplines` (the message line; `message`, `action`, `version`, `s`, `t` and bare digits are interface-schema tokens, P6), NLE's 27 blstats as named fields; 121 actions; targets depth −5..53, experience_level 0..30, hunger 0..6, each derived from NetHack 3.6.7's source/dungeon.def (read at heiner/nle v1.3.0) plus 0 for NLE's zeroed post-death observation; delta 0.02
did: P38 (5 mutants) re-derives the depth bounds from the shipped dungeon.def; local witness (scratch copies, clean and each mutant) for P38, P19, P36, P37 and P6: reports/L2/witness/l2b-nethack-manifest/witness-*.txt; local `make pins --since` was killed by the 10-min background limit after 99/99 clean (P19 then failing, fixed in 465dd42) and 57 mutants killed: make-pins-partial.txt
did: departures from "Edit/Write only": `cp`/`mv` staged witness transcripts into reports/; a `sed` fixed a field name in my own /tmp witness script; a `pkill` ended my own wait loop (exit 144); no denials
decided (not asked): take an L2b item while L2c's remaining parts wait only on Guy (A3 orders L2c before L2b; the digest is pinned by P21 and nothing here touches judge/ or worlds/spec/, P35) — p(stands on review)=0.6
decided (not asked): the trajectory hash keeps hashing NLE's raw observation, so P36's goldens stand; the emitted observation is its `view` — p=0.8
decided (not asked): non-target blstats take NLE's declared observation-space bounds [−2³¹, 2³¹−1] rather than narrower invented ones — p=0.8
decided (not asked): delta 0.02 reads brief 2's "δ = 2 progression points" in BALROG's ×100 reporting units — p=0.85
forecasts: made 4 (pins_green, review_accept on #318; host_verdict L2 FIT; session_minutes 150); resolved 0; cumulative log-loss not recomputed here
price: guy-items 0; guy-latency median 0.0h max 0.0h; sessions 0; runner-min 0 (ledger price --since 227f2b6)
obligations added: L2b: the judge never closes a World; NLE episodes free their temp dirs only on garbage collection — the pilot item should close them
NEEDS YOU (at most 1): none
next: L2b brief 2 §2 MiniHack ladder (BALROG's task set, cited and committed), then §3 AutoAscend
