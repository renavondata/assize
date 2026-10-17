# STATUS — L2 — 2026-10-17 — 1054e67 — PR #228
VERDICT: SESSION DONE: L2a obligation 28 (`The Overlap assertion has no pin`) is built and discharged by P0bd with mutant `overlap_unchecked`; pins CI run 38997225250 on 1054e67 concluded success
LAYER BOUNDARY: no (per A1.3's definition: records no layer verdict; adds or opens no brief)
pins: clean 79/79; mutants 224/224 KILLED; twins 224/224; leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0 (local `make pins` on 286d0e2, reports/L2/builder/286d0e2…/make-pins.txt)
pins CI run 38997225250 on 1054e67: success (reports/L2/ci/38997225250.json)
changed: harness/{pins.py,edits/P0bd_overlap_unchecked.toml,proposer.d/l2a-o28-overlap-pinned.toml}, reports/L2/{forecasts/a467d028-….jsonl,builder/286d0e2…/,ci/38997225250.json,status/l2a-o28-overlap-pinned.md}
did: no instruction issue open; no switchback seed, so the first candidate. `claims next "L2a obligation 27" …` printed 27 unheld, but PR #227 (`l2a-o27-outer-sweep`) builds 27: its title and VERDICT name it, while `holder` matches only `# STATUS` header lines, which name the PR, not the item. Skipped 27, held by PR #227; took 28
did: P0bd holds a live sleeper in the check process and calls `runner._spawn`: it must raise `Overlap` and the refused child (which would write a marker) must never run; control: the sleeper is a live descendant first, and once reaped the same spawn runs and returns ("pass", 0)
did: mutant `overlap_unchecked` (`if False and any(...)`) KILLED (fails on "raises Overlap" and "never ran"), twin passes; P0bd adds 1 pin and 1 mutant to master's registry
did: P0bd code and registry entry placed after P0bb, away from PR #227's hunks (pins.py 1748, 6183; registries.py untouched), so the two merge without conflict
did: the transcript was copied into reports/ with `cp`; every other file's content was written with Edit/Write; no tool call was denied
decided (not asked): 27 is held by #227 despite `claims next`, since building it twice wastes a session and conflicts — p(stands on review)=0.85
decided (not asked): a direct in-process call of `_spawn`, not a nested run: no clean path leaves a descendant past the sweep, so only an injected live descendant reaches the assertion — p=0.75
forecasts: made 4 (pins_green #228 p=0.6, review_accept #228 p=0.65, host_verdict L2 FIT p=0.35, session_minutes bound 80 p=0.5); resolved 0
price: guy-items 0; guy-latency median 0.0h max 0.0h; sessions 2; runner-min 160
obligations added: L3: none; L2a: `claims.holder` sees a brief item only in `# STATUS` header lines, which never name items; it should read the VERDICT line or the PR title, or the header shape should name the item
NEEDS YOU (at most 1): none
next: L2a obligation 29 of reports/L1/REPORT.md (the child environment is pinned only at `child_env`, not at the spawn sites); 27 (PR #227) is held
