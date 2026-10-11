# STATUS — L2 — 2026-10-12 — 13141ef — PR #117
VERDICT: SESSION DONE: instruction #111 Parts A, B (less the CLAUDE.md sentence) and C built; pins CI run 38182372179 on 13141ef (success, attempt 1; record reports/L2/ci/38182372179.json)
LAYER BOUNDARY: no (per A1.3's definition: records no layer verdict, adds or opens no brief)
pins: clean 50/50; mutants 132/132 KILLED; twins 132/132; leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0
price: guy-items 1; guy-latency median 0.4h max 0.4h; sessions 0; runner-min 0
changed: harness/chooser.py, harness/ledger.py, harness/claims.py, harness/pins.py, harness/entrants.toml, 15 mutants under harness/edits/, harness/README.md, .claude/commands/{build,vizier}.md, docs/briefs/brief-2-nethack.md, reports/
did: #110 closed (delivered by PR #116); took #111 (oldest signed instruction no open PR holds; #112, #113 follow)
did: P0ac draft form; P0ad sealed forecast and `chose:` line; P0ae labels, `seen` exposure, void counted; P0af Fixed Share, alpha = s/(T-1), fixed-order default; P0ag switchback schedule; brief amendment appended
did: first pins run (38180562904) failed, P0s/outcome_inverted STALE because my resolver edit moved its anchor; fixed in 13141ef (green above). Disclosure: one edit to harness/pins.py was made by an inline `python3 -` script in Bash, against #110 Part D; the result is the same text, no tool call was denied
decided (not asked): P0ac not P0x, since P0x is the price rule — p(stands on review)=0.9
decided (not asked): Part C says "three regimes" and lists two; built two (fixed-order, chooser) — p=0.6
decided (not asked): seed = merge commit sha, committed by the first Builder after merge to reports/switchback-seed.txt; chooser exits 2 until then — p=0.65
decided (not asked): `guy_picks` p may be 0 or 1 (fixed-order is certain); `exposure: "seen"` arg opts a not_overturned forecast into the new regime so old ones keep their meaning — p=0.7
decided (not asked): no host_verdict forecast added; 926c865723d7 is still open for L2 — p=0.8
forecasts: made 2 this session (64bd978641da pins_green, 25642ab35f27 review_accept, both by branch); resolved 0 so far; the first pins run was red, so the first will resolve false
obligations added: L3: CLAUDE.md A1.5 choice sentence (Part A item 3, Part B item 10) needs a reviewer-account `constitution` PR; PR #117 closes #76/#81/#82 as #111 directs though that sentence is open
obligations added: L3: probes (Part B item 6, k = 2) belong to the boundary brief; a `chose:` line is not yet required of every STATUS
NEEDS YOU (at most 1): none
next: reviewer round on PR #117; the first Builder after merge commits reports/switchback-seed.txt; then #112 (Batch S) unless a PR holds it
