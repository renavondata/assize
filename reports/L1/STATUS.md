# STATUS — L1 — 2026-10-08 — ca0be63 — PR #29
VERDICT: SESSION DONE
LAYER BOUNDARY: no (per A1.3's definition: no root REPORT.md verdict; opens no layer's brief)
pins: clean 28/28; mutants 68/68 KILLED; twins 68/68; leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0 (local make pins at ca0be63, steel-legend, 16:29:01Z–16:43:11Z: reports/L1/make-pins-ca0be63.txt; pins CI run 37809169847 on ca0be63: success, attempt 1, record reports/L1/ci/37809169847.json)
changed: judge/{registry.py (new),__main__.py,README.md}; harness/{pins.py (P16),edits/P16_*.toml (3 new),README.md,proposer.toml}; reports/L1/{forecasts.jsonl,make-pins-ca0be63.txt,p16/,ci/,STATUS.md}
did: brief 1 A4 item 2. judge/registry.py: `credential` issues a 64-hex token to one A1.7 party and stores only the token's SHA-256 beside the party in judge-private storage (0700/0600)
did: `register` takes an image digest and a token on stdin and nothing of the image, so a candidate cannot name its own proposer. An unmatched token (none, forged, a self-named proposer, the stored hash of a real token) is refused `unattributed` and nothing is recorded. Another party's credential on a registered image is refused `registered`. `proposer_of` is the proposer a judge record carries
did: P16 drives `python -m judge credential|register` in child interpreters. Mutants unattributed_admitted, any_credential and registration_taken_over are each KILLED, with a passing twin (reports/L1/p16/)
decided (not asked): the trust root is whoever holds the judge's private storage and runs `judge credential` (Guy or the measure workflow). A credential is a judge-issued bearer token, not a GitHub identity — p(stands on review)=0.65
decided (not asked): an image is registered once. The first registrant owns it, and a second party is refused rather than co-registered, so attribution is a function of the digest — p=0.7
decided (not asked): "every judge record carries proposer" is met when evaluate() stamps each record with proposer_of. evaluate() does not exist yet, so record stamping is pinned when it is built. That pin is an obligation below, not a claim met now — p=0.6
decided (not asked): credentials are not revocable or expiring at L1, and none is listed in REPORT.md — p=0.75
forecasts: made 3 (51f4fd1d0d10 pins green on first CI run of PR #29 head p=0.7; 08df3b144502 Reviewer ACCEPT p=0.35; fa80fd5eaa55 host FIT p=0.6); resolved 0 this session; ledger L0+L1: 85 claims, 58 resolved; cumulative log-loss 21.125 vs base rate 40.203 (0.5) over 58
obligations added: L2: when evaluate() is built, a pin requires every ledger record of a request to carry proposer_of its image, and an unregistered image's evaluate() to be refused before any seed is issued, with a mutant that stamps a fixed proposer
NEEDS YOU (at most 1): none
next: the §5 pilot runner and evaluate() (CSPRNG seeds, ledger.append, proposer_of, judge/config hash on each record), then the host pilot via the measure label
