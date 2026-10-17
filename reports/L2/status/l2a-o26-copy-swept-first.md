# STATUS — L2 — 2026-10-17 — 19449ff — PR #226
VERDICT: SESSION DONE: L2a obligation 26 is built and discharged by P0h with mutant `copy_deleted_before_sweep`; pins CI run 38985405986 on 19449ff concluded success
LAYER BOUNDARY: no (per A1.3's definition: records no layer verdict; adds or opens no brief)
pins: clean 78/78; mutants 222/222 KILLED; twins 222/222; leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0 (local `make pins` on a231054, reports/L2/builder/a2310543b08ef3e6391b933df3ac0a5f75f1a165/make-pins.txt)
pins CI run 38985405986 on 19449ff: success (reports/L2/ci/38985405986.json)
changed: harness/{runner.py,tree.py,pins.py,registries.py,fixtures/litter.py,fixtures/edits/toy_litters_copy.toml,edits/P0h_copy_deleted_before_sweep.toml,proposer.d/l2a-o26-copy-swept-first.toml}, reports/L2/{forecasts/a5e4b006-….jsonl,builder/{8c42f3c…,a231054…}/,ci/38985405986.json,status/l2a-o26-copy-swept-first.md}
did: took obligation 26, STATUS's `next` (`claims next` printed it unheld); PR #225 holds 21; no switchback seed, so the first candidate; no instruction issue open; no tool call denied
did: `_run_in_copy` makes its copy with new `tree.copy_tree` under the scratch root and leaves removal to `_scratch`, which sweeps first. P0h case `p0h_copy_swept_first`: `fixture.litter`'s mutant check leaves a non-cooperating grandchild rewriting files in its copy, then fails. P0h requires a LEAKED row, copy discarded, writer dead and a summary row. Mutant `copy_deleted_before_sweep` (the old order): `rmtree` raises ENOTEMPTY, no summary; KILLED, twin passes
did: first `make pins` at 8c42f3c exited 2: P0h/sweep_skipped LEAKED, because the case read the writer's PID from a row the Overlap exception never wrote. a231054 reads the PID from the run directory. Both transcripts are committed
did: transcripts were copied into reports/ with `cp`, a command rather than an edit; every file's content was written with Edit/Write
decided (not asked): a case inside P0h, not a new pin: P0h already holds the sweep's other non-cooperating cases and its scope names the sweep — p(stands on review)=0.75
decided (not asked): the copy is removed by `_scratch`'s `rmtree(..., ignore_errors=True)` with the scratch root; `copy_discarded` still checks the copy path — p=0.7
forecasts: made 4 (pins_green #226 p=0.55, review_accept #226 p=0.6, host_verdict L2 FIT p=0.35, session_minutes bound 60 p=0.55); resolved 0
price: guy-items 0; guy-latency median 0.0h max 0.0h; sessions 0; runner-min 0
obligations added: L3: none; L2a: the writer's race with `rmtree` is probabilistic (5/5 ENOTEMPTY locally, one KILL in make pins); a lucky interleaving would let the mutant survive one run
NEEDS YOU (at most 1): none
next: L2a obligation 27 of reports/L1/REPORT.md (`run_under_edits` neither sets the subreaper nor sweeps); 21 (PR #225) is held
