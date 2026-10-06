# STATUS — L1 — 2026-10-06 — fe99a83 — PR #13
VERDICT: STOPPED: Crafter 1.8.3 is non-deterministic given a seed (brief 1 stop-and-report boundary); draft A7 proposes the fix
LAYER BOUNDARY: no (per A1.3's definition: no root REPORT.md verdict; amends the current layer's brief, opens no layer's brief)
pins: clean 14/14; mutants 20/20 KILLED; twins 20/20; leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0
changed: docs/briefs/brief-1-judge-and-crafter.md (A7 appended); harness/proposer.toml; reports/L1/{crafter-nondeterminism.txt,forecasts.jsonl,make-pins.txt,make-pins-f73f74b-failed.txt,ci/37511509891.json,STATUS.md}
did: started brief 1 §3. A determinism check of the binding failed clean: same seed and actions, 4 distinct trajectory hashes over 2 runs × 2 processes
did: cause: crafter.engine.World keeps each chunk's objects in a set; Env._balance_object despawns creatures[random.randint(…)] from a list built by iterating that set, so the order follows id(). 5/5 seeds diverge across processes, first at a balance step (t ≡ 0 mod 10) on a despawn; 5/5 diverge within one process; 5/5 identical with insertion-ordered chunk containers — reports/L1/crafter-nondeterminism.txt
did: drafted brief 1 Amendment A7: the World is crafter 1.8.3 with insertion-ordered chunk containers, set by the binding at reset (same RNG draws, same law of a trajectory under a uniform seed); P11 determinism with mutants set_order_restored, seed_ignored, hash_constant, field_dropped; crafter pinned ==1.8.3
did: binding (worlds/crafter/binding.py: Episode, observe, trajectory hash, manifest conformance, Hafner score), P11 and 3 mutant edits, crafter==1.8.3 in pyproject/uv.lock: pushed to branch l1-s2-crafter-binding-wip @ db77191, not for merge; its P11 fails clean on stock crafter, as A7 predicts
did: make pins at fe99a83 on steel-legend, start 18:24:05Z end 18:27:12Z, PINS PASSED (reports/L1/make-pins.txt); first pins CI run 37511509891 on fe99a83: success (reports/L1/ci/37511509891.json). The first local run, at f73f74b, failed P0m because the commit's Proposer trailer was not in the final trailer block. The commit was amended to fe99a83 and the failed transcript kept (reports/L1/make-pins-f73f74b-failed.txt)
decided (not asked): this is the brief's boundary "Crafter is non-deterministic given a seed"; stop rather than ship a patched World under the unamended brief — p(stands on review)=0.85
decided (not asked): propose the fix as a brief amendment (A1.10: amendable by PR with Reviewer approval) in this PR, not as a NEEDS YOU — p=0.6
decided (not asked): fix = insertion-ordered chunk containers, not sorting by position or seeding a separate RNG: it consumes the same draws, so a trajectory's law is Crafter's — p=0.75
decided (not asked): keep Crafter's image render inside Env.step (the night render draws from world.random; skipping it would change the dynamics), discard the image — p=0.8
decided (not asked): binding WIP kept off this PR on its own pushed branch so that pins stay green here — p=0.75
forecasts: made 3; resolved 0 this session; ledger L0+L1: 35 claims, 23 resolved; cumulative log-loss 5.199 vs base rate 15.942 (0.5) over 23; empirical-frequency base rate is +∞ (a review BLOCK followed only ACCEPTs)
obligations added: none
NEEDS YOU (at most 1): none
next: if A7 is accepted and merged: rebase l1-s2-crafter-binding-wip on master, add the A7 change and the set_order_restored mutant, and make P11 green; if A7 is rejected: the reviewer's finding
