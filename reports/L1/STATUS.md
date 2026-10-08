# STATUS — L1 — 2026-10-08 — b2ca5ee — PR #24
VERDICT: SESSION DONE
LAYER BOUNDARY: no (per A1.3's definition: no root REPORT.md verdict; opens no layer's brief)
pins: clean 21/21; mutants 43/43 KILLED; twins 43/43; leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0 (local make pins at b2ca5ee, steel-legend, 9m36s: reports/L1/make-pins-b2ca5ee.txt; pins CI run 37730664698 on b2ca5ee: success, attempt 1, 05:05:54Z–05:21:36Z, record reports/L1/ci/37730664698.json)
changed: judge/{seeds.py (new),README.md}; worlds/crafter/binding.py (world_seed); harness/{pins.py (P1),edits/P1_{seed_reissued,reuse_check_skipped,domain_check_skipped,training_undomained}.toml (new),README.md,proposer.toml}; reports/L1/{forecasts.jsonl,make-pins-b2ca5ee.txt,ci/37730664698.json,STATUS.md}
did: brief 1 §2 seeds and pin P1. `judge/seeds.py`: CSPRNG (`secrets`) evaluation seeds over [0, 2**31-1), keyed by the seed the World generates from (`binding.world_seed`, captured at Crafter's first `World.reset`; Crafter reduces `hash((seed, 1)) % (2**31-1)`, so distinct seeds can name one World)
did: domains by key parity, odd = evaluation, even = the public training stream (SHA-256 of a tag, the World and a counter, filtered to even keys): disjoint by construction, and checked at issuance and by P1
did: `admit` is the issuance check: flock on the World's O_APPEND store (file 0600, dir 0700, owner checked); it rereads every record and refuses, writing nothing, a used key, a key repeated within the request, a training key, an out-of-range seed, or a reused request id; `issue` returns only admitted seeds
did: P1 (~2 s) KILLS seed_reissued (the brief's evaluator mutant: the issuance check refuses request-b with `reused`; transcript appended to the make-pins file), reuse_check_skipped, domain_check_skipped, training_undomained, each with a passing twin
decided (not asked): P1 taken as the brief's first unfinished item not in flight (#22 holds A4.1, #19 A4.4/A4.3); A4.2 (proposer from the registering credential) waits on #22's ledger and on evaluate() — p(stands on review)=0.8
decided (not asked): seeds keyed by the World's effective seed, not the raw seed, so reuse means "the same World", not "the same integer" — p=0.85
decided (not asked): domain separation by key parity, halving the evaluation space to ~2**30 — p=0.75
decided (not asked): a reused request_id is refused at issuance; evaluate()'s idempotency (returning recorded results) is left to evaluate(), which is not yet built — p=0.7
decided (not asked): the store's location is the caller's; evaluate() will pass judge-private storage; P1 uses a 0700 dir under the scratch root — p=0.75
forecasts: made 3 (31fe65757ab7 pins green on first CI run of PR head p=0.7, now resolvable: run 37730664698 success; 2c9a35e034e6 Reviewer ACCEPT p=0.7; f06b2b8cbd34 host FIT p=0.6); resolved 0; ledger L0+L1: 60 claims, 41 resolved; cumulative log-loss 12.264 vs base rate 28.419 (0.5) over 41
obligations added: L2: evaluate() draws every evaluation seed through seeds.issue into judge-private storage, and its records carry no seed; a pin that an evaluate() seed absent from the store fails
NEEDS YOU (at most 1): none
next: A4 item 2 (proposer from the registering credential, refusal witnessed by a pin) once #22 merges; else evaluate() over seeds.issue and the ledger
