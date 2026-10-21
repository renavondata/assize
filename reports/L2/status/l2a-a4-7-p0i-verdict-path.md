# STATUS — L2 — 2026-10-20 — 48f6001 — PR #275
VERDICT: SESSION DONE: brief 2 A4 item 7's remainder discharged by P0bp `bytecode_defences_off` (P0i through the runner's verdict path); A4 has no open Builder item
LAYER BOUNDARY: no (per A1.3's definition: records no layer verdict; adds or opens no brief)
pins CI run 39467394544 on 48f6001: success (reports/L2/ci/39467394544.json)
pins: clean 92/92; mutants 291/291 KILLED; twins 291/291; leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0 (attempt 2; reports/L2/build/l2a-a4-7-p0i-verdict-path/ci-39467394544-attempt2-summary.txt). Attempt 1: clean 91/92, P31 clean FAILED (ci-39467394544-summary.txt, ci-39467394544-P31-clean.log). Local subset (13 pins calling run_nested, 25 mutants KILLED): out/local-subset/stdout.log, not committed
changed: harness/{pins.py,nested.py,registries.py,fixtures/stamp.py,fixtures/stamped.py,fixtures/edits/stamped_same_length.toml,edits/P0bp_bytecode_defences_off.toml,proposer.d/l2a-a4-7-p0i-verdict-path.toml}, reports/L2/{a4-dispositions.md,forecasts/7b84b218-3aff-4b24-bd9a-b93121eec58c.jsonl,ci/39467394544.json,build/l2a-a4-7-p0i-verdict-path/,status/l2a-a4-7-p0i-verdict-path.md}
did: master session; no open instruction issue; no switchback seed, so the first candidate: master STATUS `next` (A4 item 7 remainder); `claims next` printed it, none held; no awaits-guy PR. Declaration on #274 (comment 6297044007)
did: P0bp: a disposable copy with an unchecked-hash stale pyc for harness/fixtures/stamped.py runs a nested orchestrator over fixture.stamp (one same-length mutant); the rows must say KILLED, twin pass, 1/1, exit 0; control proves the cache armed. `run_nested` gains `prepare(copy)`
did: P31 failed its clean run on attempt 1 by a race, not this diff: `_each_runtime` runs docker and podman at once over one data/ledger.jsonl, and docker's "record altered" case rewrote it while podman verified ("p9-request-a[0]: sha256 is not the record's own digest"). Failed job re-run once (attempt 2 green)
did: forecasts pins_green, review_accept, session_minutes committed before the PR opened (4063e57). Process: no tool call denied
decided (not asked): an unchecked-hash pyc stands in for the timestamp pyc whose second and size the edit matches: the importer accepts both without reading the source, and unchecked makes the coincidence certain instead of timed — p(stands on review)=0.75
decided (not asked): a new pin P0bp, not a widened P0i: a mutant turning both defences off is already KILLED by P0i's own checks, so only a separate pin attributes the kill to the verdict path; a single defence off does not reach the verdict (each is P0i's) — p=0.8
decided (not asked): P31's shared-ledger race carried as the next item, not fixed in this PR (outside item 7); its failure witnessed and the job re-run, not dropped — p=0.7
forecasts: made 3 (bb9bdbf6de95, 8ebcdea9dfc6, 1128a3097cd0); resolved 0 this session; cumulative log-loss not recomputed here
price: guy-items 0; guy-latency median 0.0h max 0.0h; sessions 0; runner-min 0
obligations added: L2: P31 gives each runtime its own copy of the fixture ledger, with a mutant that shares one and a fixture that makes the interleaving certain
NEEDS YOU (at most 1): none
next: P31's race: each runtime of `_each_runtime` verifies its own copy of data/; mutant `shared_ledger` (one copy, the altered case run before the other runtime's pass case) must be KILLED
