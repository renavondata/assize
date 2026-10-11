# STATUS — L2 — 2026-10-12 — 49d1d6a — PR #119
VERDICT: SESSION DONE: instruction #68 done (wish-to-merge latency in the price)
LAYER BOUNDARY: no (per A1.3's definition: records no layer verdict, adds or opens no brief)
pins: clean 45/45; mutants 117/117 KILLED; twins 117/117; leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0 — pins CI run 38184360362 on 49d1d6a (success, run attempt 1; record reports/L2/ci/38184360362.json)
changed: harness/ledger.py, harness/pins.py, harness/edits/P0t_wish_from_instruction.toml, harness/README.md, harness/proposer.toml, reports/L2/forecasts.jsonl, reports/L2/STATUS.md, reports/L2/ci/38184360362.json
did: #68 items 1–3: `ledger.wish_latency` (per wish filed in the window, hours from the wish's own created_at to the earliest merge of a PR citing an instruction whose body cites it; unmerged wishes counted open); price line gains `wish-latency median <h>h max <h>h open <n>`; P0t mutant `wish_from_instruction` KILLED in CI
did: code ported from closed PR #106 (6ca2547, reviewed ACCEPT WITH OBLIGATIONS at 5821d1a; closed for a trailer split in its review commit); README/proposer.toml/forecasts conflicts resolved to master plus this change
did: `claims next` skipped nothing (#68 first); #111 is held by PR #117; #110 already closed after PR #116 merged
did: no tool call was denied; local `make pins` not run (CI is the witness); P0t and its new mutant run locally: clean passes, mutant fails (latency 1.0h vs 5.0h)
decided (not asked): CLAUDE.md not edited for item 2; the price line is defined by `Price.status_line`, as PR #106's accepted review read it — p(stands on review)=0.75
decided (not asked): wish-latency prints 0.0h when no wish is merged, with the open count beside it (review 5821d1a F2 carried as an L3 obligation, not fixed, since #68 says nothing else) — p=0.7
forecasts: made 3 (4f9f273bc96b pins_green p=0.7, 88881be69289 review_accept p=0.7, 4245f53c7871 host_verdict FIT p=0.35); resolved 0 this session; builder cumulative log-loss 52.43 over 123 resolved (`ledger proposer builder`); per-type base rate not recomputed this session
price: guy-items 1; guy-latency median 0.4h max 0.4h; sessions 0; runner-min 0; wish-latency median 0.0h max 0.0h open 0 (`ledger price --since 2940bc7`)
obligations added: L3: review 5821d1a F2 (wish-latency 0.0h indistinguishable from a real zero when none merged), F4 (nothing asserts STATUS carries the line the command prints)
obligations added: L3: STATUS forecasts line should carry the per-type base-rate log-loss; a ledger subcommand should print it
NEEDS YOU (at most 1): none
next: reviewer round on PR #119; then #102 unless a PR holds it
