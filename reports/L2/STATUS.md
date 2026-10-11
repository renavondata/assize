# STATUS — L2 — 2026-10-11 — eb67973 — PR #114
VERDICT: SESSION DONE (review a921c37 F1 worked: P0x rebuilt against instruction #70 as signed at gfrmin's 11:56Z edit)
LAYER BOUNDARY: no (per A1.3's definition: records no layer verdict, adds or opens no brief)
pins: clean 41/41; mutants 109/109 KILLED; twins 109/109; leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0 — local make pins on eb67973; CI run on the pushed head not yet read
changed: harness/claims.py, harness/pins.py, harness/edits/P0x_*.toml, harness/README.md, harness/proposer.toml, reports/L2/STATUS.md
did: F1(a): claims.PRICE_FROM removed. claims.price_from(repo, base) reads the committer time of the first commit on the merge base's first-parent line that adds the rule to harness/claims.py; a merge is read against its first parent, so the time is the merge's own
did: F1(b): PRICE_EXEMPT removed. There is no enumerated set and no issue number. F1(d): before the merge, price_from is None and the real-tree check covers no issue (transcript: "the rule has not merged … covers no issue")
did: F1(c): a batch carries exactly one `Price:` line in each `## Part` and none before the first; the probe's one-line two-Part batch is now refused. Fixture repository: the merge's committer time is the bound, not the branch commit's
did: F3: the mutant exemption_by_number is replaced by scoped_by_number (`n < 113` in place of the merge-time test), KILLED on #67 signed after the merge and #900 signed before it
decided (not asked): P0x, not P0v as the issue names it; P0v already holds review.yml's trigger (review F2, now recorded) — p(stands on review)=0.9
decided (not asked): in a mixed batch (some Parts priced, some `none`), a workflow-touching commit is not a finding; the commit cites the issue, not a Part, so only an all-`none` instruction is held to "changes no workflow" — p=0.6
decided (not asked): no new forecast rows this session; this branch's first pins run is past, so rows added now would be late under P0r (rule 2) and redden pins; the open forecasts on this branch stand — p=0.7
decided (not asked): the bound is read from the merge base, not from HEAD; a branch that adds the rule does not start its own clock before it merges — p=0.8
forecasts: made 0 (see decided); resolved 0 by this session; cumulative log-loss not recomputed this session
price: guy-items 1; guy-latency median 0.2h max 0.2h; sessions 20; runner-min 881 (python -m harness.ledger price --since 91352cc)
obligations added: L3: build.md step 2 (forecast before the first make pins) still makes every later session on an open PR add late rows under P0r; carried over from the last STATUS
obligations added: L3: PRICE_DECLARED takes a bare bound; real batch lines such as "Price: sessions; down; 2 (the #48/#106 class)" would be refused once in scope, so drafts should be told the exact form
NEEDS YOU (at most 1): none
next: the next signed instruction (#110), after #114 merges; close #70 then
