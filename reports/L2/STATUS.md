# STATUS — L2 — 2026-10-12 — 3f925b4 — PR #117
VERDICT: SESSION DONE: review of 473a72d F1 and F2 worked (instruction #111 Part B items 3 and 6); local `make pins` green at 3f925b4 (witness reports/L2/builder/3f925b4/make-pins.txt); CI pins on the pushed head not yet run
LAYER BOUNDARY: no (per A1.3's definition: records no layer verdict, adds or opens no brief)
pins: clean 52/52; mutants 140/140 KILLED; twins 140/140; leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0
price: guy-items 1; guy-latency median 0.4h max 0.4h; sessions 1; runner-min 1
changed: harness/chooser.py, harness/ledger.py, harness/pins.py, harness/proposer.toml, 8 mutants under harness/edits/ (P0ah_*, P0ai_*), harness/README.md, .claude/commands/{build,vizier}.md, reports/
did: F1: `chooser choose` also prints the act's `not_overturned {item, until, exposure: seen, chose, round}` (item = the instruction's issue, or the PR for a brief item) and #77's `merged {pr}`, both with the Builder's p and proposer; pin P0ah, 4 mutants KILLED
did: F2: `ledger probe --brief` reads k from the brief, draws k acts from the exposed-and-silent set by SHA-256 of `<ledger head>:<id>`; a probe defaults to keep, is false on gfrmin's reversal, and counts as a guy-item (route `probe`); vizier.md trigger 4 runs it; pin P0ai, 4 mutants KILLED
did: P0ad/P0af updated for the new required chooser arguments; build.md step 1 passes them
did: first local run (fa58322) failed P0r: this session's two forecasts were late under A4 rule 2 (the branch's first pins run was 38180562904); removed them from the unpushed commit; no tool call was denied
decided (not asked): no new forecasts this session: A4 rule 2 (later law) forbids rows added after the branch's first pins run, though A1.6/build.md step 2 ask for them; branch forecasts 64bd978641da/25642ab35f27 stand — p(stands on review)=0.75
decided (not asked): the act's p values (`--p-kept`, `--p-merged`) are the acting Builder's, given on the command line; the chooser has no model for them — p=0.6
decided (not asked): a brief item's `not_overturned` is filed on its pull request, the only GitHub item it has — p=0.7
decided (not asked): "ledger head" = the last commit that changed a forecast ledger (`ledger.probe_seed`); a probe's p = its act's p; a probe carries no `exposure`, so left alone it is kept — p=0.65
forecasts: made 0 this session; branch: 64bd978641da resolved false; 25642ab35f27 open (review at 473a72d was BLOCK, so it resolves false); builder cumulative log-loss 52.79 over 124 resolved (`ledger proposer builder`)
obligations added: L3: build.md step 2 and A1.6 require a forecast from every Builder session before `make pins`; A4 rule 2 makes a rework session's rows late; one of the two needs amending
obligations added: L3: CLAUDE.md A1.5 choice sentence (Part A item 3, Part B item 10) still needs a reviewer-account `constitution` PR (review F3)
NEEDS YOU (at most 1): none
next: reviewer round on PR #117 at the pushed head; after merge, the first Builder commits reports/switchback-seed.txt; then #112 (Batch S) unless a PR holds it
