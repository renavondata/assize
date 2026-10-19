# STATUS — L2 — 2026-10-19 — 2ecc223 — PR #254
VERDICT: SESSION DONE: review ef1e03c F7 (review commits authored as assize-builder) is built as `claims.author_check`: a non-merge commit whose Proposer party acts through an account (builder: assize-builder; reviewer, auditor, vizier: assize-reviewer) is authored by it, from the rule's own commit on; the pre-push hook refuses one that is not; P0bj witnesses it with four mutants, KILLED with passing twins
LAYER BOUNDARY: no (per A1.3's definition: records no layer verdict; adds or opens no brief)
pins CI run 39225503537 on 2ecc223: success (reports/L2/ci/39225503537.json)
pins: clean 87/87; mutants 251/251 KILLED; twins 251/251; leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0 (harness summary row of the run's pins-report artefact, since 03ec9a7, skipped 0)
changed: harness/{claims.py,pins.py,hooks/pre-push,edits/P0bj_{identity_swapped,procedures_unbound,retrospective,hook_unchecked}.toml,proposer.d/l2a-r-ef1e03c-f7-author-account.toml}, reports/L2/{forecasts/cbdfc432-….jsonl,ci/39225503537.json,status/l2a-r-ef1e03c-f7-author-account.md}
did: no open `instruction` issue; `claims next` took review ef1e03c F7, the first candidate of master STATUS's `next` (none held); `reports/switchback-seed.txt` absent, so no chooser; no `awaits-guy` PR
did: the misattribution's source is the agent runner's systemd override, which sets GIT_AUTHOR_*/GIT_COMMITTER_* to assize-builder for every job, review jobs included; it persists: PR #251 carries four reviewer commits authored as assize-builder (86051cc, 39ea670, 1ec6c2d, 132878c). The fix to `.github/workflows/review.yml` is Guy's (entrenched); its text is in PR #254's body; `.github/` untouched
did: the rule binds the commits descending from the one adding `def author_findings(` (`claims.author_law`, read from git as PRICE_MARK dates its rule), so #251's commits are outside it: a simulated merge of this branch into #251 gives 0 findings. Local probe on scratch copies KILLED all four mutants, clean passed; P0m, P0y, P0ba, P0bg, P0e passed clean in-process
did: no local full `make pins` (exceeds the 10-minute cloud limit); witnessed by the CI artefact. No tool call was denied
decided (not asked): a prospective rule (from its own commit) rather than a sha exemption table for #251's unrewritable commits — p(stands on review)=0.75
decided (not asked): auditor and vizier bound to assize-reviewer (Amendments 2 and 3, appended: procedures of the reviewer account); guy, counsel, mechanism bound to no account — p(stands on review)=0.8
decided (not asked): log-loss base rate is the sequential per-type empirical frequency of the builder's resolved forecasts (0.5 before any resolution, clipped at 1e-6), voided rows excluded — p(stands on review)=0.7
forecasts: made 4 (pins_green #254 p=0.75, review_accept #254 p=0.7, host_verdict L2 FIT p=0.35, session_minutes run 39224503751 bound 100 p=0.7); resolved 273 builder forecasts to date; cumulative log-loss 140.80 vs base rate 196.57 over 273
price: guy-items 0; guy-latency median 0.0h max 0.0h; sessions 2; runner-min 1
obligations added: L2a: `.github/workflows/review.yml` to set the reviewer's git identity (Guy's, entrenched; text in PR #254's body)
NEEDS YOU (at most 1): none
next: review ef1e03c F6; L2a obligation 36 if PR #251 is not merged
