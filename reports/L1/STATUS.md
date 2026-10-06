# STATUS — L1 — 2026-10-06 — 3210f7e — PR #10
VERDICT: SESSION DONE
LAYER BOUNDARY: no (per A1.3's definition: no root REPORT.md verdict; adds or opens no layer's brief)
pins: clean 10/10; mutants 15/15 KILLED; twins 15/15; leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0
changed: harness/{proc.py,runner.py,pins.py,README.md,proposer.toml,edits/P0i_pycache_prefix_unset.toml}; reports/L1/{forecasts.jsonl,make-pins.txt,p0i-transcripts.txt,measure-37484737316.txt,STATUS.md}
did: brief 1 A6 item 1: proc.child_env(scratch) sets PYTHONPYCACHEPREFIX to a fresh pycache-* dir under the child's scratch root (inherited value dropped), beside -B and PYTHONDONTWRITEBYTECODE=1; the orchestrator passes each child its own scratch
did: P0i new case: a copy keeping a stale in-tree __pycache__ (same-length, same-second edit) runs the edited source under child_env ('5 1'); the control without a prefix still reads stale bytecode ('4 1'). Seeded mutant pycache_prefix_unset KILLED (fails only the prefix case), twin passes (reports/L1/p0i-transcripts.txt)
did: make pins at 3210f7e on steel-legend (reports/L1/make-pins.txt): PINS PASSED, 3m02s; registry proposer session 6d75feeb-…; afterwards no harness process and no /tmp/assize-scratch-*, -copy-* or -p0i-* left. A first run failed P0i (ERROR, then NON-CAUSAL ×2): the check itself now runs under the prefix, so cache_from_source pointed the fixture .pyc into the prefix; the fixture now builds the in-tree path by hand. That commit was amended before push; the run is recorded here so it is not dropped
did: first pins CI run 37485211229 on 3210f7e: success. Host witness (A6 item 2): label `measure` → run 37484737316 on 3210f7e: success; facts complete (load 0.34/0.46/0.36, cpuset 3-5,9-11, runner 2.337.0, `crun v2 systemd rootless=true`); host pins clean 10/10, 15/15 KILLED, leaked 0 (reports/L1/measure-37484737316.txt)
decided (not asked): child_env raises when no scratch root is known rather than falling back to the system temp dir, so no prefix dir outlives its run — p(stands on review)=0.85
decided (not asked): a fresh prefix dir per child_env call (per spawned child), not one per suite, so no child reads another's cache — p(stands on review)=0.85
decided (not asked): child_env drops an inherited PYTHONPYCACHEPREFIX before setting its own, so the seeded mutant truly unsets it whatever the caller's environment — p(stands on review)=0.85
decided (not asked): the P0i control strips the prefix explicitly, so the stale-read hazard stays demonstrated (non-vacuous) now that every child runs under a prefix — p(stands on review)=0.85
decided (not asked): run 37484737316 is recorded as the host witness of A4 item 5's harness half (A4 §6), with facts complete. It does not discharge review-70d26b8 F1/F2 (the measuring processes run in system.slice, not the pinned user-1002.slice); those remain L2 obligations — p(stands on review)=0.7
forecasts: made 3; resolved 0 this session; ledger L0+L1: 26 claims, 17 resolved, 9 open; cumulative log-loss 3.654 vs base rate 11.784 (0.5) over 17 (the 2 id-less L0 resolution rows named in A4 7a are not counted; review-70d26b8 F3 on the comparator stands as an L2 obligation)
obligations added: none
NEEDS YOU (at most 1): none
next: brief 1 A4 item 7 (7a ledger validator, 7b CI-claim checker, 7c trailer checker incl. A5 F2 multi-party), each pin with its seeded mutant; then §1 Interface
