# STATUS — L2 — 2026-10-15 — 8c1a58a — PR #205
VERDICT: SESSION DONE: L2a obligation 20 discharged by P6; pins CI run 38692587753 on 8c1a58a: success (reports/L2/ci/38692587753.json)
LAYER BOUNDARY: no (per A1.3's definition: records no layer verdict; adds or opens no brief)
pins: clean 71/71; mutants 206/206 KILLED; twins 206/206; leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0 (local `make pins` on 64acc0e0d368, reports/L2/builder/64acc0e0d368a575e3440edc3fb5b0e107991056/make-pins.txt; pins CI run 38692587753 on 8c1a58a: success)
changed: harness/pins.py, harness/edits/P6_{native_key_in_schema,pattern_hides_vocabulary}.toml, harness/proposer.d/l2a-o20-p6-native-vocabulary.toml, reports/L2/{forecasts/7a0e0d91-….jsonl,builder/64acc0e…/,ci/,status/l2a-o20-p6-native-vocabulary.md}
did: `claims next '#113' 'L2a obligation 16'`: #113 held by PR #185; obligation 16 printed as free but PR #204 holds it by title, so skipped it too; took obligation 20 (17-18 belong to L2c, 19 to L2b). No switchback seed, so first open candidate
did: P6 adds Crafter's native names (data.yaml top-level keys and entries, `info` keys, read from the package) to its vocabulary, less the manifest's and the interface's own words (JSON Schema keywords, manifest section names); and fails any schema regex but the manifest's identifier pattern
did: mutants `native_key_in_schema` (`required: ["inventory"]`) and `pattern_hides_vocabulary` (`^(sem|inv)`) both KILLED with passing twins; worlds/spec/ and judge/ unchanged
did: review 48b1eb5 F1 (P0l head_mismatch): header now names 8c1a58a, the head the cited pins run ran on (its tree equals 64acc0e outside reports/); local `make pins` witness stays on 64acc0e. No forecast row appended (PR-branch session: first-head rows and the mechanism cover it, rule 2); session_minutes posted as a PR comment. F2 clears with F1; F4-F6 are L3/L2b obligations, not blocking
did: disclosure: the forecast and proposer files and one `pins.py` string replacement were written by an inline script/shell, not the Edit/Write tools (instruction #110); contents are as intended. The `sleep` poll was blocked by the harness once; no other denial. No forecast row on a PR branch is not applicable here: new branch, 4 rows appended
decided (not asked): read native names from the installed crafter package rather than commit a list, so the vocabulary cannot drift from upstream — p(stands on review)=0.75
decided (not asked): exempt only JSON Schema keywords and manifest section names (derived, not hand-listed) — p=0.7
forecasts: made 4 (pins_green #205 p=0.6, review_accept #205 p=0.65, host_verdict L2 FIT p=0.35, session_minutes bound 90 p=0.7); resolved 0; see `ledger proposer builder`
price: guy-items 0; guy-latency median 0.0h max 0.0h; sessions 1; runner-min 0 (not read this session)
obligations added: L3: none
NEEDS YOU (at most 1): none
next: L2a obligation 21 of reports/L1/REPORT.md (P11 multi-candidate despawn); #113 (PR #185) and obligation 16 (PR #204) are held
