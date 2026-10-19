# STATUS — L2 — 2026-10-19 — 7f99c61 — PR #256
VERDICT: SESSION DONE: review ef1e03c F6 (carrying dba90c5 F5) is built: `harness.ledger resolve` reads layer ids `L<n>`, resolves void `unobservable` (counted, never scored) a session_minutes forecast on run `local` and a pull-request forecast whose number is an issue, and still names every other unreadable row; P0bk witnesses it with four mutants, KILLED with passing twins
LAYER BOUNDARY: no (per A1.3's definition: records no layer verdict; adds or opens no brief)
pins CI run 39241815631 on 7f99c61: success (reports/L2/ci/39241815631.json)
pins: clean 88/88; mutants 255/255 KILLED; twins 255/255; leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0 (harness summary row of the run's pins-report artefact, skipped 0)
changed: harness/{ledger.py,pins.py,edits/P0bk_{local_unread,layer_prefix_unread,issue_unchecked,any_failure_void}.toml,proposer.d/l2a-r-ef1e03c-f6-unobservable.toml}, reports/L2/{forecasts/b133901e-….jsonl,ci/39241815631.json,build/l2a-r-ef1e03c-f6-unobservable/p0bk-probe.txt,status/l2a-r-ef1e03c-f6-unobservable.md}
did: no open `instruction` issue; `claims next` took review ef1e03c F6, the first candidate of master STATUS's `next` (none held; PR #251 is merged, so obligation 36 is not a candidate); `reports/switchback-seed.txt` absent, so no chooser; no `awaits-guy` PR
did: a dry resolve of master's ledger gave 20 unreadable rows: 15 session_minutes on run `local`, 1 host_verdict on layer `L2`, 4 on #58 and #103, which are wish issues, not pull requests; with this head: 19 void, the L2 row open (no L2 verdict line yet), unreadable 0 (reports/L2/build/l2a-r-ef1e03c-f6-unobservable/p0bk-probe.txt)
did: local probe on scratch copies: clean P0bk True, all four mutants False; P0s, P0ak passed clean in-process. No local full `make pins` (exceeds the 10-minute cloud limit); witnessed by the CI artefact. No tool call was denied
decided (not asked): run `local` and an issue-numbered PR are void `unobservable` (the shape a cancelled run already takes), not false: no outcome of the claim exists to score — p(stands on review)=0.75
decided (not asked): a pull request is judged an issue only when its read fails and `issues/<n>` answers without `pull_request`; a number not yet taken or any other API failure stays named unread, so a transient failure never voids a real forecast — p(stands on review)=0.8
decided (not asked): log-loss base rate is the sequential per-type empirical frequency of the builder's resolved forecasts (0.5 before any resolution, clipped at 1e-6), voided rows excluded, as in PR #254's STATUS — p(stands on review)=0.7
forecasts: made 4 (pins_green #256 p=0.75, review_accept #256 p=0.75, host_verdict L2 FIT p=0.35, session_minutes run 39241228123 bound 90 p=0.65); resolved 279 builder forecasts to date; cumulative log-loss 144.26 vs base rate 200.26 over 279
price: guy-items 0; guy-latency median 0.0h max 0.0h; sessions 1; runner-min 1
obligations added: none
NEEDS YOU (at most 1): none
next: the next unfinished item of brief 2 (review ef1e03c F4, F5 and F7 are built by PRs #252, #253 and #254)
