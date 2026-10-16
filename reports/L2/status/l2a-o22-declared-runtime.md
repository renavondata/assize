# STATUS — L2 — 2026-10-15 — e8f7b00 — PR #213
VERDICT: STOPPED: review round 1 F1 answered (this STATUS cites its run); L2a obligation 22 discharged by P32, but pins is red on P0x: signed issues #211 and #212 carry no `Price:` line, which no session can edit
LAYER BOUNDARY: no (per A1.3's definition: records no layer verdict; adds or opens no brief)
pins: clean 73/75; mutants 208/213 KILLED; twins 208/213; leaked 0; stale 0; inconclusive 0; non-causal 5 (P0l's 2, P0x's 3); exit 2 — pins CI run 38766897404 on e8f7b00: failure (reports/L2/ci/38766897404.json; excerpt reports/L2/builder/e8f7b0030582924d9a0d8780f9cbaba68610b941/ci-pins.txt). Red: P0l, on the old uncited STATUS this file replaces; P0x, on issues #211 and #212. Code unchanged since 04bc967
changed: reports/L2/{ci/38766897404.json,builder/e8f7b00…/ci-pins.txt,status/l2a-o22-declared-runtime.md}
did: review 436088e F1 (BLOCK, P0l): the previous STATUS named 04bc967, which has no `pins` run, and cited none. This STATUS names e8f7b00, the head with a completed run, cites run 38766897404 on it, and states the head's real counts (two red, not one). Verdict STOPPED, not SESSION DONE, because the cited run failed and P0l accepts a failed run only under STOPPED; that is also the truth (precedent: the STATUS for instruction #174)
did: F2 and F3 are obligations, not worked here (A1.4). PR branch: no forecast row appended; the session_minutes declaration was posted as a `vizier-ledger:` comment on #213. Proposer row left as the first session's (code unchanged; precedent PR #207 round 2). No tool call denied
decided (not asked): STOPPED is the right verdict while P0x is red on every branch — p(stands on review)=0.8
decided (not asked): keep harness/proposer.d/l2a-o22-declared-runtime.toml unchanged; this session wrote only reports/ — p=0.75
forecasts: made 0 here (PR branch; declaration posted as a comment); earlier on this branch 4 (pins_green #213 p=0.5, review_accept #213 p=0.55, host_verdict L2 FIT p=0.35, session_minutes bound 90 p=0.6); see `ledger proposer builder`
price: guy-items 0; guy-latency median 0.0h max 0.0h; sessions 10; runner-min 480 (`ledger price --since` the merge base; 9286784 carried a value typed before the command returned, corrected here)
obligations added: L3: none. L2a (from review 436088e): F2, a pin whose mutant deletes the `_expect_declared` call from `p2_peek` (with `ASSIZE_RUNTIME` set); F3, P0x red on every branch until #211/#212 carry a `Price:` line or P0x treats signed drafts otherwise
NEEDS YOU (at most 1): none
next: a master Builder takes signed instruction #211 (oldest open signed), then #212; then this PR rebuilds once P0x is green on master
