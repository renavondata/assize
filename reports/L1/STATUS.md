# STATUS — L1 — 2026-10-06 — ff4a7c6 — PR #7
VERDICT: SESSION DONE
LAYER BOUNDARY: no (per A1.3's definition: no root REPORT.md verdict; adds or opens no brief)
pins: clean 9/9; mutants 13/13 KILLED; twins 13/13; leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0
changed: harness/{proc,runner,nested,tree,pins,config,registries}.py; harness/fixtures/{escapee,daemon,leaky}.py; harness/{config,fixtures/fast}.toml; harness/edits/{P0h_subreaper_not_set,P0h_sweep_skipped,P0i_pycache_top_level_only}.toml; harness/{README.md,proposer.toml}; reports/L1/{forecasts.jsonl,make-pins.txt,STATUS.md}
did: brief 1 A4 item 5 (harness half): orchestrator is a child subreaper; one child at a time, asserted (Overlap) before each spawn; after each run, sweep kills descendants until none remain, count = leaked_processes; >0 or scratch held after the sweep -> LEAKED
did: fixtures: cooperating grandchild (leaky, leaked_processes 0), non-cooperating grandchild (escapee: new session, no death signal, SIGTERM ignored, hangs), double-forked daemon from a clean check returning True (daemon)
did: P0h mutants subreaper_not_set, sweep_skipped added and KILLED; death_signal_reverted, scratch_kept, leaked_not_counted still KILLED with passing twins
did: A5 F1: copies exclude __pycache__ at every depth; child Pythons run with -B and PYTHONDONTWRITEBYTECODE=1; P0i (same-length edit in the second the .pyc recorded) KILLS pycache_top_level_only
did: make pins at ff4a7c6 (reports/L1/make-pins.txt): PINS PASSED; registry proposer session baad25ab-…; afterwards no harness process and no /tmp/assize-scratch-* or /tmp/assize-copy-* left
decided (not asked): A5 F1 grouped with A4 item 5, as A5 says it is "done within" that item — p(stands on review)=0.9
decided (not asked): sweep first waits reap_grace_s for descendants to die on their own (the death-signal path), then kills and counts the rest; without the wait a dying cooperating grandchild would be counted as leaked — p(stands on review)=0.8
decided (not asked): death signal kept; death_signal_reverted is still KILLED (the cooperating grandchild becomes a swept leak, LEAKED not INCONCLUSIVE), so A4's retire clause does not apply — p(stands on review)=0.85
decided (not asked): -B and PYTHONDONTWRITEBYTECODE=1 only disable writing; reading a stale .pyc is prevented by the every-depth exclusion, which is why the seeded mutant is killable. P0i makes "same second" deterministic with os.utime, plus a control showing a plain copy reads stale bytecode — p(stands on review)=0.75
decided (not asked): fixture.escapee repurposed as the non-cooperating grandchild (hangs until swept); escape_hold_s removed from config; no scored run exists — p(stands on review)=0.8
decided (not asked): measure.yml not triggered by this session (brief 1 A1.3 gives the trigger to Guy); A4 item 8 host facts must land first anyway, or the host run "is not a measurement" — p(stands on review)=0.75
forecasts: made 3; resolved 0 this session; ledger L0+L1: 17 claims, 11 resolved, 6 open; cumulative log-loss 2.416 vs base rate 7.625 (0.5) over 11
obligations added: L2: the one-child-at-a-time assertion (runner.Overlap) gets its own pin; seeded mutant: the descendant check before spawn removed
obligations added: L2: P0i tests the copy mechanism directly; a nested-harness variant should show the fixture mutant KILLED through the verdict path
NEEDS YOU (at most 1): none
next: brief 1 A4 item 8 (host_facts.sh: uptime, cpuset, runner version, podman info), then the host witness of the harness half via measure.yml (A4 §6)
