# STATUS — L2 — 2026-10-17 — 74388b6 — PR #232
VERDICT: SESSION DONE: L2a obligation 32 (`The PROPOSER_EXEMPTIONS entry for bb7b387 is dead config`) is built and discharged by P0m with mutant `stale_exemption_accepted`; review 492f85a F1 (no STATUS for the branch) is answered by this file
LAYER BOUNDARY: no (per A1.3's definition: records no layer verdict; adds or opens no brief)
pins CI run 39046859099 on 74388b6: success (reports/L2/ci/39046859099.json)
pins: Reviewer's full reproduction on 492f85a: clean 82/82; mutants 229/229 KILLED; twins 229/229; leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0 (reports/L2/review/492f85a326c01a58d826b5074a7976464cb2a625/make-pins.txt)
changed: harness/{claims.py,pins.py,edits/P0m_stale_exemption_accepted.toml,edits/P0bg_base_unguarded.toml,proposer.d/l2a-o32-stale-exemption.toml}, reports/L2/{forecasts/afb09511-….jsonl,ci/39046859099.json,status/l2a-o32-stale-exemption.md}
did: round 1 (session afb09511, claude-sonnet-5-5): `claims.stale_exemptions` makes P0m's real-branch half fail an exemption sha outside base..HEAD; mutant `stale_exemption_accepted` KILLED with passing twin; P0bg probes with a non-empty table so `base_unguarded` still dies
did: round 1 removed the last PROPOSER_EXEMPTIONS entry, e37357e (reachable only from instr-46/instr-49 branches); bb7b387 was already gone (instruction #54 item 5)
did: round 2 (this session, 806ee6c6, claude-opus-5-5): the only item is review 492f85a F1; this STATUS is the whole answer, the code is unchanged
did: on a pull-request branch no forecast row is appended (rule 2, P0r); this session's declaration forecast (session_minutes, run 39046862626, bound 30) is the PR's `vizier-ledger:` comment; no tool call was denied
decided (not asked): bb7b387 had already been removed, so the obligation is discharged by the pin review 576fe9632eab F2 named (every exemption in base..HEAD, mutant `stale_exemption_accepted`) and by removing the stale e37357e instead — p(stands on review)=0.85
decided (not asked): harness/proposer.d/l2a-o32-stale-exemption.toml keeps session afb09511, which built the harness state; this session changes no harness file, so the code head stays 74388b6 and no new pins run is needed — p(stands on review)=0.75
decided (not asked): no local `make pins` this round; the code is identical to 492f85a, which the Reviewer reproduced in full, and CI run 39046859099 on 74388b6 is green — p(stands on review)=0.8
forecasts: made 4 in round 1 (pins_green #232 p=0.6, review_accept #232 p=0.65, host_verdict L2 FIT p=0.35, session_minutes local bound 40 p=0.5), 1 this round (session_minutes run 39046862626 bound 30 p=0.6, by comment); resolved 8c504df3a3b8 pins_green #232 true; review_accept #232 resolves false on review 492f85a; builder record 247 resolved, log-loss 128.52
price: guy-items 1; guy-latency median 2.6h max 2.6h; sessions 4; runner-min 385
obligations added: L2a: review 492f85a F3 (P0bg mutant `stale_base_unguarded` dropping the `base is not None` guard on `stale_exemptions`); L2a: review 492f85a F4 (the review procedure's open-forecast counter crashes on legacy `resolves` rows)
NEEDS YOU (at most 1): none
next: L2a obligation 33 of reports/L1/REPORT.md (P14 uses an asymptotic χ² p-value); 29 (PR #229) is held
