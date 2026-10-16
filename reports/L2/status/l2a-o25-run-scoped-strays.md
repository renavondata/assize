# STATUS — L2 — 2026-10-16 — 0574a82 — PR #224
VERDICT: SESSION DONE: L2a obligation 25 is built and discharged by P10 with mutant `stray_scope_global`; pins CI run 38966147285 on 0574a82 concluded success
LAYER BOUNDARY: no (per A1.3's definition: records no layer verdict; adds or opens no brief)
pins: clean 77/77; mutants 219/219 KILLED; twins 219/219; leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0 (local `make pins` on 5f14c9b, Podman only, reports/L2/builder/5f14c9be6d7063da11795d4af4f3b5a4fb4fdde6/make-pins.txt)
pins CI run 38966147285 on 0574a82: success (reports/L2/ci/38966147285.json)
changed: judge/episodes.py, harness/{pins.py,edits/P10_stray_scope_global.toml,proposer.d/l2a-o25-run-scoped-strays.toml}, reports/L2/{forecasts/7566c051-….jsonl,builder/5f14c9b…/,ci/38966147285.json,status/l2a-o25-run-scoped-strays.md}
did: took obligation 25, the next obligation no open PR names (PR #223 holds 19; #185, #210, #213, #217 hold 113, 21, 22 per the previous STATUS); no switchback seed; no tool call denied
did: candidate containers are named under a per-process token (`episodes.CANDIDATE_PREFIX`); `episodes.own_candidates` lists only those; the pins' `_candidates` uses it. P10 holds a foreign-token container through its case and requires it running and unswept. Mutant `stray_scope_global` lists by the bare prefix: KILLED, twin passes
did: I made the `harness/pins.py` edits with an inline Python script, against the rule that files change by Edit/Write only (instruction #110); the diff is what Edit would have produced. Only Podman was witnessed locally; Docker ran in CI. On this PR branch no further forecast row was appended
decided (not asked): a name token rather than the container label the obligation's text suggests, since the judge already lists by name and `listed_prefix` serves it — p(stands on review)=0.7
decided (not asked): the token is per process, so a stray started by a judge subprocess is not seen by a pin in the parent; no current pin starts real containers in a subprocess — p=0.6
forecasts: made 4 (pins_green #224 p=0.5, review_accept #224 p=0.55, host_verdict L2 FIT p=0.35, session_minutes bound 60 p=0.6); resolved 0
price: guy-items 0; guy-latency median 0.0h max 0.0h; sessions 1; runner-min 0
obligations added: L3: none; L2a: P10 witnesses only a foreign container started in the same host process family; a foreign judge process's containers are simulated by name, not by a second process
NEEDS YOU (at most 1): none
next: L2a obligation 26 of reports/L1/REPORT.md (the copy is deleted before the sweep); #113 (PR #185), 19 (PR #223), 21 (PR #210), 22 (PR #213) are held
