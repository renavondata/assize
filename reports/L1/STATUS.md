# STATUS — L1 — 2026-10-08 — b96ff90 — PR #30
VERDICT: SESSION DONE
LAYER BOUNDARY: no (per A1.3's definition: no root REPORT.md verdict; opens no layer's brief)
pins: clean 29/29; mutants 73/73 KILLED; twins 73/73; leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0 (local make pins at b96ff90, steel-legend, 17:32:09Z–17:46:21Z: reports/L1/make-pins-b96ff90.txt; pins CI run 37819200188 on b96ff90: success, attempt 1, 24.2 min, record reports/L1/ci/37819200188.json)
changed: judge/{evaluate.py (new),__main__.py,README.md}; harness/{pins.py (P17),edits/P17_*.toml (5 new),README.md,proposer.toml}; reports/L1/{forecasts.jsonl,make-pins-b96ff90.txt,p17/,ci/,STATUS.md}
did: brief 1 §2 evaluate(image, world, n_episodes, request_id), and A4 §9 "every judge record carrying proposer taken from the registering credential" (review 02a7143 F2)
did: evaluate refuses an unregistered image before any seed; replays a signed request_id unchanged, running nothing; refuses request_conflict and interrupted; issues CSPRNG seeds; plays through episodes.run; stamps schema_version, judge_sha256, image, proposer_of, world, runtime, n_episodes, achievements; appends via ledger.append. CLI `python -m judge evaluate`
did: P17 under every usable runtime (podman here; docker and podman in CI) evaluates the incumbent for 2 full Crafter episodes. Mutants fixed_proposer, seeds_before_proposer, idempotency_dropped, conflict_unchecked, hash_partial each KILLED with a passing twin (reports/L1/p17/)
decided (not asked): judge_sha256 covers every file of judge/, worlds/ and uv.lock (the World's pinned version), bytecode excluded — p(stands on review)=0.75
decided (not asked): one PRIVATE dir holds seeds, credentials, registrations, key and heads; the ledger is LEDGERS/<world>.ledger.jsonl — p=0.75
decided (not asked): a request whose seeds were issued but never signed (judge died mid-request) is refused `interrupted`, its seeds spent, never reissued; the refusal names it, so nothing is dropped silently — p=0.6
decided (not asked): the candidate is named by its local image id (sha256:…); the judge never pulls a candidate (`image_absent` before seeds); the caller names the runtime, which each record carries — p=0.7
decided (not asked): builder commits are authored as assize-builder (pre-empting review 02a7143 F5), not the runner's git identity — p=0.85
forecasts: made 3 (3cc483b3d94e pins green on first CI run of PR #30 head p=0.7; 668cfe7aacaa Reviewer ACCEPT p=0.55; e69e4b94b997 host FIT p=0.6); resolved 0 this session; ledger L0+L1: 88 claims, 60 resolved; cumulative log-loss 22.532 vs base rate 41.589 (0.5) over 60
obligations added: L2: pins CI took 24.2 of its 30 job minutes at b96ff90; the next container pin may push it over. The timeout lives in .github/workflows/pins.yml (entrenched)
NEEDS YOU (at most 1): none
next: the §5 pilot runner over evaluate() (200 incumbent episodes or 2 h, throughput, timetolearn table, Hafner score, proposer on the pilot report); measure.yml's 45-min timeout is below the 2-h cap and is entrenched, so that session raises it as its NEEDS YOU
