# STATUS — L2 — 2026-10-17 — d85642b — PR #230
VERDICT: SESSION DONE: L2a obligation 30 (`SIGTERM to the orchestrator leaves scratch behind`) is built and discharged by P0bf with mutant `sigterm_unhandled`; pins CI run 39009196136 on d85642b concluded success
LAYER BOUNDARY: no (per A1.3's definition: records no layer verdict; adds or opens no brief)
pins: clean 81/81; mutants 227/227 KILLED; twins 227/227; leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0 (local `make pins` on 1a93960, reports/L2/builder/1a9396065fb79ab253bee71775310b4b6d927cd4/make-pins.txt)
pins CI run 39009196136 on d85642b: success (reports/L2/ci/39009196136.json)
changed: harness/{proc.py,runner.py,pins.py,edits/P0bf_sigterm_unhandled.toml,proposer.d/l2a-o30-sigterm-cleanup.toml}, reports/L2/{forecasts/cef6f382-….jsonl,builder/1a93960…/,ci/39009196136.json,status/l2a-o30-sigterm-cleanup.md}
did: no instruction issue open; no switchback seed, so the first candidate. `claims next "L2a obligation 29" …` printed 29 unheld, but open PR #229 (`l2a-o29-spawn-env`) builds 29 by its title (the `holder` defect #228's STATUS recorded); skipped 29, held by PR #229; took 30
did: `proc.exit_on_sigterm()`, armed in `runner.run` after the subreaper: SIGTERM raises SystemExit(128+15) in the main thread, so the open `_scratch` finally sweeps descendants and deletes the scratch root (copy included); a second SIGTERM during cleanup is ignored
did: P0bf SIGTERMs a nested `fixture.escapee` mutants run once its check and non-cooperating grandchild hang in a copy (controls: grandchild live, one scratch root and one copy present); asserts exit 143, no assize-scratch-*, no assize-copy-*, grandchild dead, no live descendant
did: mutant `sigterm_unhandled` KILLED (exit -15, scratch, copy and grandchild left; 4 assertions fail), twin passes; named P0bf, since #229 takes P0be; code after P0bd, away from #229's hunks (pins.py 1804, 6246; registries.py untouched)
did: three /tmp/assize-scratch-* dirs predate this session's run (mtimes 05:53–06:56 +0800, run began ~13:45 +0800) and were left alone; transcript copied with `cp`; no tool call was denied
decided (not asked): 29 is held by #229 despite `claims next` — p(stands on review)=0.85
decided (not asked): the handler is armed only in `run`, not `run_under_edits`, whose `subprocess.run` SIGKILLs the inner run on any exception, so a handler there alone would still leak the inner scratch; carried as an L2a obligation — p=0.7
forecasts: made 4 (pins_green #230 p=0.6, review_accept #230 p=0.65, host_verdict L2 FIT p=0.35, session_minutes bound 100 p=0.5); resolved 0
price: guy-items 0; guy-latency median 0.0h max 0.0h; sessions 4; runner-min 639
obligations added: L3: none; L2a: SIGTERM to `harness run --under-edits` SIGKILLs its inner run (subprocess.run's exception path), so the inner run's scratch is left; forward SIGTERM to the inner run and pin it
NEEDS YOU (at most 1): none
next: L2a obligation 31 of reports/L1/REPORT.md (P0m errors, rather than failing, on a tree with no `.git`); 29 (PR #229) is held
