# STATUS — L2 — 2026-10-09 — 004822b — PR #42
VERDICT: SESSION DONE
LAYER BOUNDARY: no (per A1.3's definition: records no layer verdict in root REPORT.md, adds or opens no brief)
pins: clean 32/32; mutants 84/84 KILLED; twins 84/84; leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0 (local make pins at 004822b, steel-legend, 08:38:59Z–08:53:43Z: reports/L2/make-pins-004822b.txt; pins CI run 37907829725 on 004822b: success, attempt 1; record reports/L2/ci/37907829725.json)
changed: judge/{ledger.py,__main__.py,README.md}; pilot/__main__.py; harness/{pins.py,proposer.toml,edits/P9_independent_heads.toml}; reports/L2/{STATUS.md,forecasts.jsonl,make-pins-b68a8df.txt,make-pins-004822b.txt,ci/37907829725.json,p9/}
did: L2a, reports/L1/REPORT.md obligation 1 on L2 (review 2817eb7 F2): tail truncation passed `verify` because each signed head stood alone
did: `ledger.verify(ledger, private, anchor)`: the anchor, the last sha256 of a request the caller was returned, must be a signed head; CLI `verify LEDGER PRIVATE ANCHOR`; pilot anchors at its last record (no record: a finding, so STOPPED); P17 at its request's last
did: P9 adds `last_request_truncated`, `ledger_and_heads_deleted` (both fail under the anchor) and an earlier anchor verifying after a later request; mutant `independent_heads` KILLED by exactly the two truncation cases (reports/L2/p9/independent_heads-{mutant,twin}-004822b.log)
did: first make pins at b68a8df: 32/32, 83/84, P9/record_dropped INCONCLUSIVE (IndexError: anchor read from ledger rows the mutant shortened); fixed in 004822b by anchoring at what `append` returned; transcript kept (reports/L2/make-pins-b68a8df.txt)
decided (not asked): discharge obligation 1 by a caller-held anchor, not by chaining heads: the anchor alone commits every request up to it (later heads' cumulative `bytes` and the signed head list catch any earlier removal); head chaining would only add reorder detection, which no obligation names — p(stands on review)=0.7
decided (not asked): anchor is a required argument, no default: a None anchor would be a verification that cannot fail on truncation — p=0.8
decided (not asked): heads.jsonl format unchanged, so ledgers already on the host still verify given an anchor; judge_sha256 moves, explained by this diff (judge/ledger.py, judge/__main__.py, judge/README.md) — p=0.85
decided (not asked): one obligation per PR (obligation 1 only); 2 and 3 (P9 byte comparison, replay unchecked against the signed head) next — p=0.75
forecasts: made 3 (36182d70bd56 pins green first CI run of PR head p=0.75; a65606c41900 Reviewer ACCEPT p=0.65; 72972d0311d1 L2 NetHack host verdict FIT p=0.35); resolved 0 this session; ledger L0–L2: 108 claims, 101 resolved; cumulative log-loss 40.535 vs base rate 70.008 (0.5) over 101 (carried from 29b7dc5)
obligations added: L3: none
NEEDS YOU (at most 1): none
next: L2a obligation 2 of reports/L1/REPORT.md (P9 compares request a's bytes before parsing; mutant: same-length overwrite after a non-O_APPEND open), then 3 (replay checked against the signed head)
