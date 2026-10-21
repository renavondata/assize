# STATUS — L2 — 2026-10-21 — 838df32 — PR #288
VERDICT: STOPPED: instruction #284 built (P0ad's `departure_unscored_admitted` KILLED in CI), but pins is red on P0x because the signed issues #281, #284 and #286 carry no `Price:` line, which only gfrmin can add without breaking the signature
LAYER BOUNDARY: no (per A1.3's definition: records no layer verdict; adds or opens no brief; appends an amendment to brief 2)
pins CI run 39533871975 on 838df32: failure (reports/L2/ci/39533871975.json)
pins: clean 91/92; mutants 292/295 KILLED; twins 292/295; leaked 0; stale 0; inconclusive 0; non-causal 3 (P0x's, its twin fails too); exit 2 (attempt 1; reports/L2/build/instr-284-departure-scored/ci-39533871975-summary.txt). Scratch-copy transcript of P0ad clean and under the new mutant: reports/L2/build/instr-284-departure-scored/p0ad-scratch.txt (a transcript, not a CI citation)
changed: docs/briefs/brief-2-nethack.md, harness/{chooser.py,pins.py,README.md,edits/P0ad_departure_unscored_admitted.toml,proposer.d/instr-284-departure-scored.toml}, reports/L2/{forecasts/ca090d46-d131-4dbf-87ee-df2f30430195.jsonl,ci/39533871975.json,build/instr-284-departure-scored/,status/instr-284-departure-scored.md}
did: master session; signed instructions #281, #284, #286 (all `signed`); `claims next '#281' '#284' '#286'` skipped #281 (held by PR #287) and printed #284; no switchback seed, so A1.5's order. No awaits-guy PR. Declaration on #284 (comment 6306547213)
did: brief 2 gains `## Wish #74 (appended; instruction #284)`, the issue's text verbatim. `chooser.chose_findings` reports `unscored_departure` for a `chose:` line that picks a candidate other than its first (A1.5's) when no `fixed-order` `guy_picks` row of that round is sealed in a strict ancestor of the line: the scored default the departure is measured against
did: P0ad fixture rounds R7 (no fixed-order row → finding), R8 (sealed before → none), R9 (added with the line → finding); mutant `departure_unscored_admitted` KILLED, twin passes (CI 39533871975)
did: forecasts pins_green, review_accept, session_minutes committed before the PR opened (987d28c, the branch's first commit); denials: none
decided (not asked): a mutant and fixture rounds on P0ad, not a new pin: the check extends P0ad's own `chose:` seal and shares its fixture — p(stands on review)=0.8
decided (not asked): a choice outside the candidates is not also an `unscored_departure` (`not_a_candidate` already reports it; the first clean run showed both on R6) — p=0.85
decided (not asked): "a chooser that loses to the fixed order on resolved choices is not elected" is recorded as the amendment's pre-stated criterion only; the issue asks "only for the scored default and the pin", and P0af's Fixed Share already weighs `fixed-order` against the mixture — p=0.7
decided (not asked): did not put a `Price:` line on #281/#284/#286; an edit by another account after the signature unsigns the instruction (Amendment 4 rule 5) — p=0.95
forecasts: made 3 (fa643b45bf20, 44a25c63bec7, d50672a6cfa5); resolved 0 this session; cumulative log-loss not recomputed here
price: guy-items 0; guy-latency median 0.0h max 0.0h; sessions 0; runner-min 0 (`ledger price --since 088417a` did not finish within 120 s; not recomputed)
obligations added: L3: a Builder that departs from A1.5's order without any `chose:` line is not detected (STATUS declares no machine-readable candidate list); carried
NEEDS YOU (at most 1): add a `Price:` line (`<quantity>; down|up; <bound>`, or `none (recording-only)`) to the bodies of #281, #284 and #286 (same item as PR #287's STATUS); then re-run pins on PR #287 and PR #288
next: after the price lines, re-run pins on PR #288 (the Vizier may, once per head); master's next item is #286, which needs its own price line first
