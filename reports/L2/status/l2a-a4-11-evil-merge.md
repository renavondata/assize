# reports/L2/status/l2a-a4-11-evil-merge.md
# STATUS — L2 — 2026-10-20 — 544d10b — PR #272
VERDICT: SESSION DONE: brief 2 A4 item 11 (evil merges): P0m refuses a merge that changes an entrenched path relative to both of its parents (`claims.evil_paths`, over the merge's `diff-tree -c` paths), whoever authored it; mutants `evil_merge_accepted` and `any_parent_evil` KILLED
LAYER BOUNDARY: no (per A1.3's definition: records no layer verdict; adds or opens no brief)
pins CI run 39417469305 on 544d10b: success (reports/L2/ci/39417469305.json)
pins: clean 91/91; mutants 282/282 KILLED; twins 282/282; non-causal 0; inconclusive 0; stale 0; leaked 0; skipped 0/91 pins (CI run 39417469305 pins-report summary, whole suite since cfe23e2); pins-monotone origin/master..HEAD: 0 findings; trailers origin/master..HEAD: 0 findings. Local probe: reports/L2/build/l2a-a4-11-evil-merge/p0m-probe.txt
changed: harness/{claims.py,pins.py,README.md,edits/P0m_evil_merge_accepted.toml,edits/P0m_any_parent_evil.toml,proposer.d/l2a-a4-11-evil-merge.toml}, reports/L2/{forecasts/1fca68e0-….jsonl,ci/39417469305.json,build/l2a-a4-11-evil-merge/,status/l2a-a4-11-evil-merge.md}
did: master session (ASSIZE_ACK=no), no dispatched PR; no seed file (reports/switchback-seed.txt absent), so the first open candidate was taken: STATUS `next`, A4 item 11 (`claims next`: not held); no open instruction issues; no awaits-guy PR
did: fixture: the gfrmin CLAUDE.md merge case now wants `evil_merge` (it writes CLAUDE.md anew, relative to both parents); the reviewer .github/ merge case wants `evil_merge` beside `entrenched_without_guy`; the builder merge after it, whose tree differs from its second parent in CLAUDE.md, wants none (carried, not authored)
did: read all 118 merges in master's history with `evil_paths`: none is evil, so the rule refuses nothing already merged
did: process: no tool call denied. Commit messages by heredoc to `git commit -F -` (not a file edit); probe transcript copied with cp from /tmp
decided (not asked): the rule binds merges by gfrmin too, because item 11 says "may not change an entrenched path relative to both of its parents" with no exception for an author; the entrenched change itself must arrive in a commit a parent carries — p(stands on review)=0.75
decided (not asked): `evil_merge` is added beside `entrenched_without_guy`, not in place of it, so no earlier finding changes meaning — p=0.8
decided (not asked): a second mutant `any_parent_evil` (`-m` for `-c`) witnesses "relative to both" and not "relative to either" — p=0.85
decided (not asked): no local `make pins` (31–40 min here); an in-memory probe of P0m clean and under each mutant (fixture half) plus clean P0m on the real repository, and the whole suite in CI run 39417469305 — p=0.8
forecasts: made 3 (pins_green #272 p=0.75, review_accept #272 p=0.7, session_minutes run 39416851354 bound 90 p=0.7); resolved none this session; pins_green resolves true (first run 39417469305 success); cumulative log-loss not recomputed here
price: guy-items 0; guy-latency median 0.0h max 0.0h; sessions 1; runner-min 1 (ledger price --since efcc75b, read before CI finished)
obligations added: L3: none
NEEDS YOU (at most 1): none
next: brief 2 A4 item 12 (guy-attributed commits verify against an entrenched allowed_signers) if the check can be pinned before the entrenched file lands; else audit findings 2 and 3 once Guy files the instruction #270 recommends
