# STATUS — L2 — 2026-10-13 — fde1426 — PR #167
VERDICT: SESSION DONE: instruction #139 (Haiku and Fable enter review/audit/vizier; per-model price), rebuilt from master
LAYER BOUNDARY: no (per A1.3's definition: records no layer verdict, adds or opens no brief)
pins: clean 61/61; mutants 171/171 KILLED; twins 171/171; leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0 — local `make pins` on fde1426, 0/61 pins skipped (reports/L2/builder/fde1426843bbfb38d86ebb19803188887438184e/make-pins.txt); pins CI run 38340954631 on fde1426: success (reports/L2/ci/38340954631.json)
changed: harness/{entrants.toml,ledger.py,pins.py,README.md}, harness/edits/P0t_{first_entrant_only,costless_session_dropped,cost_pooled}.toml, harness/edits/P0u_entrants_beyond_second_ignored.toml, harness/proposer.d/instr-139-models-price-2.toml, reports/L2/{forecasts/15185207-cbdc-4c0c-9c30-5077204d1b1d.jsonl,ci/38340954631.json,status/instr-139-models-price-2.md,builder/fde1426.../}
did: carried the code of ff760c2 + c0e50d9 (review-e74a798: items 1–6 MET) onto master by cherry-pick, without PR #163's proposer row and forecasts; mutants first_entrant_only, costless_session_dropped, cost_pooled, entrants_beyond_second_ignored KILLED
did: answered #163's F1 by citing the CI pins run on the code sha fde1426, whose child adds only reports/; closed #162 (PR #165 merged at f44e230)
decided (not asked): took #139: the oldest signed instruction no open PR holds (#113 held by PR #143), since gfrmin closed PR #163 saying "#139 is rebuilt from master" — p(stands on review)=0.85
decided (not asked): new branch instr-139-models-price-2, since the old branch carries 8f42c9e (deleted STATUS) that breaks P0ad/P0ag — p=0.85
decided (not asked): F3's pairing of result events by order kept as built (it is an L3 obligation, and #139 says "Nothing else") — p=0.7
forecasts: made 4; resolved 0; builder cumulative log-loss 65.24 vs base rate 86.97 over 146 (`ledger proposer builder`, natural log; base rate is prequential per-type frequency, 0.5 before a type's first resolution)
price: guy-items 4; guy-latency median 0.0h max 0.3h; sessions 12; runner-min 493; models claude-opus-5-5 s4/170m/$4.24+?, claude-sonnet-5-5 s7/57m/$1.77+?, unknown s12/6m/$23.20+? (`ledger price --since 3ea5325`, run on fde1426)
obligations added: L3: the measured price shows unknown s12/6m/$23.20 against 12 session runs: runs whose logs hold more `result` events than draws attribute the extra cost to `unknown` with 0 minutes (F3 of review-e74a798, now witnessed on real data)
NEEDS YOU (at most 1): none
next: #140 (its stop boundary clears when this PR merges), else the oldest signed instruction no open PR holds
