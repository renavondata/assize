# STATUS — L2 — 2026-10-18 — a874b28 — PR #247
VERDICT: SESSION DONE: L2a obligation 36 (`pilot/__main__.py` paths unpinned, R 571ee563f91d F3) is discharged by pin P34; mutants `ledger_findings_ignored` and `registration_unbound` each KILLED with a passing twin
LAYER BOUNDARY: no (per A1.3's definition: records no layer verdict; adds or opens no brief)
pins CI run 39131820782 on a874b28: success (reports/L2/ci/39131820782.json)
pins: clean 85/85; mutants 240/240 KILLED; twins 240/240; leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0 (summary row of the run's pins-report artefact, since becb3fc, skipped 0)
changed: harness/{pins.py,edits/P34_ledger_findings_ignored.toml,edits/P34_registration_unbound.toml,proposer.d/l2a-o36-pilot-main-pinned.toml}, reports/L2/{forecasts/e45383fa-….jsonl,ci/39131820782.json,status/l2a-o36-pilot-main-pinned.md}
did: dispatched by Guy (ASSIZE_ACK=yes) after #241 and #242 merged; no open signed instruction; no `reports/switchback-seed.txt`, so no `chooser choose`: the first free candidate was taken
did: P34 runs `pilot()` over a faked runtime, build and `evaluate()` that writes through the real `judge.ledger` and `judge.registry` in scratch storage: intact ledger → image registered under `[incumbent].proposer`, records carry it, a verdict, no finding, exit 0; one record altered → `STOPPED: the ledger fails verification`, findings in report.json, exit 1
did: scratch-copy probe before push (`python -m harness check --pin P34`): clean PASS; under each mutant FAIL; P0b, P0aj, P0ak, P0an, P0v, P0ab, P0aw clean PASS; no tool call was denied; no push was refused
decided (not asked): obligation 33 is held by open PR #246 (its title and VERDICT name it), though `claims next` printed it free, since #246's STATUS header names no item; skipped — p(stands on review)=0.9
decided (not asked): obligation 34 (P14's power) is skipped until #246 merges: it is a property of the exact test #246 installs, in the same lines of `harness/pins.py` — p(stands on review)=0.8
decided (not asked): `pilot()` is called directly with P18's fixture config, not through `main()`, whose committed config would play the full pilot; the reviewer's proposed pin names `pilot()` — p(stands on review)=0.85
decided (not asked): no line added to `harness/README.md`, which #246 also edits on its single line; the pin's docstring carries the description — p(stands on review)=0.75
decided (not asked): no local `make pins` (whole suite over the cloud limit); CI run 39131820782 is the whole-suite witness — p(stands on review)=0.85
forecasts: made 4 (pins_green #247 p=0.75, review_accept #247 p=0.75, host_verdict L2 FIT p=0.35, session_minutes run 39128138376 bound 60 p=0.5); resolved none this session; cumulative log-loss not recomputed here
price: guy-items 5; guy-latency median 0.5h max 1.1h; sessions 9; runner-min 562
obligations added: none
NEEDS YOU (at most 1): none
next: close #243 (its unblocking condition, #241 merged, is met); then L2a obligation 34 once PR #246 merges, else 37 (`pilot/` not in `judge_sha256`); review ef1e03c F4; review 492f85a F4
