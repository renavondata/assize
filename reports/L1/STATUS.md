# STATUS — L1 — 2026-10-08 — 25f36e6 — PR #32
VERDICT: L1 SEALED; Crafter FIT; interface PROVISIONAL
LAYER BOUNDARY: yes (per A1.3's definition: root REPORT.md gains the L1 verdict line; brief 2 gains A2, the draft that opens L2)
pins: clean 30/30; mutants 81/81 KILLED; twins 81/81; leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0 (local make pins at 25f36e6, steel-legend, 20:35:52Z–20:50:20Z: reports/L1/make-pins-25f36e6.txt; pins CI run 37840644452 on 25f36e6: success, attempt 1; the earlier run 37840452533 on 1374d8f is superseded, not cited; record reports/L1/ci/37840644452.json)
changed: harness/{pins.py (P0b second mutant),edits/P0b_judge_imports_mutants.toml (new),proposer.toml}; REPORT.md (L1 line); docs/briefs/brief-2-nethack.md (A2 draft); reports/L1/{REPORT.md (new),STATUS.md,forecasts.jsonl,make-pins-25f36e6.txt,p0b/,ci/}
did: reports/L1/REPORT.md per brief 1 "On completion, report": the criteria table (every brief 1 and A1–A9 criterion, with its witness), schema and manifest, configs, judge hash, incumbent utilities, floor, compute, time-to-learn, pins and verdicts
did: root REPORT.md L1 line cites the pins runs 37829367792 (cab0ca0, the pilot's code) and 37836660872 (af3a8ea, master's tree); host verdict FIT from measure run 37831165785, judge_sha256 28710725… unchanged at this head
did: found A2 item 3 / A3 item 2 unmet as written: no mutant added a `harness.mutants` reference to judge code. Added P0b/judge_imports_mutants (edits judge/evaluate.py), KILLED with a passing twin (reports/L1/p0b/); the judge-image half is owed at the seal (brief 2 A2 P21)
did: interface finding: brief 2's zero-diff test cannot pass as written. judge/evaluate.py:33 hard-codes WORLDS = {"crafter": ...}, and prices are per World in judge/config.toml. Brief 2 A2 drafts L2a (World discovery and price as data) before the zero-diff baseline
did: collected 55 open L2 obligations (86 review lines, 25 STATUS versions, deduplicated), listed in reports/L1/REPORT.md and bound by brief 2 A2
decided (not asked): A2 item 3 closed in this PR by one patch mutant, not stopped on. The scan covers the tree that judge_sha256 hashes, which is what the judge runs in L1 — p(stands on review)=0.75
decided (not asked): no second host pilot. FIT stands on measure 37831165785: this PR changes no path judge_sha256 covers and no pilot code, and a second pilot would invite a choice between verdicts — p=0.8
decided (not asked): the root verdict line cites the runs at cab0ca0 and af3a8ea, not this head's. A line cannot cite a run on its own commit; this head's run is cited here — p=0.7
decided (not asked): the brief-2 draft is an appended amendment (A2) to Guy's existing brief 2, not a new file. It moves the zero-diff baseline to the merged L2a commit — p=0.55
forecasts: made 4 (cf224825301c pins green first CI run p=0.8; 565ed1f4dec5 Reviewer ACCEPT p=0.5; 04b6c97e9c28 host FIT stands p=0.85; e47d59b88286 P0b mutant KILLED locally and in CI p=0.9); resolved 0 this session; ledger L0+L1: 96 claims, 92 resolved; cumulative log-loss 37.254 vs base rate 63.770 (0.5) over 92
obligations added: L2: the 55 in reports/L1/REPORT.md "Obligations on L2", including the interface finding (World table and price in judge/)
obligations added: L2: P0b's scan of the built judge image (brief 1 A2 item 3), at the seal
NEEDS YOU (at most 1): merge PR #32, a layer-boundary PR (L1 verdict, brief 2 A2) that only Guy merges
next: after Guy's merge, L2a per brief 2 A2: World discovery and per-World price as data (P19, P20), then the judge-touching obligations 1–16, before the zero-diff baseline
