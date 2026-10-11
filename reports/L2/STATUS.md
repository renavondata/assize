# STATUS — L2 — 2026-10-11 — 1cfd9a1 — PR #114
VERDICT: SESSION DONE (review 1fc37c6 F1 worked: this STATUS cites pins CI run 38148339961 on 1cfd9a1: success)
LAYER BOUNDARY: no (per A1.3's definition: records no layer verdict, adds or opens no brief)
pins: clean 41/41; mutants 109/109 KILLED; twins 109/109; leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0 — pins CI run 38148339961 on 1cfd9a1: success; local make pins on 1cfd9a1 agrees
changed: harness/claims.py (PROPOSER_EXEMPTIONS), harness/proposer.toml, reports/L2/STATUS.md, reports/L2/ci/
did: F1: interim STATUS 39eb9f2 cited the failed run 38144888825 on 29dabe2 (STOPPED); its run 38146782078 then showed P0m red too
did: P0m red cause: reviewer commit 29dabe2 has a blank line between Proposer and Co-Authored-By, so git parses no Proposer trailer; exempted by full sha with its one party, as e37357e was (1cfd9a1)
did: F2 (obligation): PR body regenerated to describe the diff as it stands
decided (not asked): exempt 29dabe2 rather than rewrite the pushed branch; the entry turns inert once merged and is then removed like bb7b387's — p(stands on review)=0.75
decided (not asked): no new forecast rows; this branch's first pins run is past, so rows now would be late under P0r — p=0.7
forecasts: made 0 (see decided); resolved 0 by this session; cumulative log-loss not recomputed this session
price: guy-items 1; guy-latency median 0.2h max 0.2h; sessions 22; runner-min 1087
obligations added: L3: review commits must keep Proposer and Co-Authored-By in one trailer block; a blank line between them reddens P0m on the reviewed branch
NEEDS YOU (at most 1): none
next: the next signed instruction (#110), after #114 merges; close #70 then
