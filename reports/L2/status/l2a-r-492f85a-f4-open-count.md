# STATUS — L2 — 2026-10-19 — 03ec9a7 — PR #253
VERDICT: SESSION DONE: review 492f85a F4 (the open-forecast counter raises `KeyError: 'id'` on the legacy L0 `resolves` rows) is built as `python -m harness.ledger open`, which reads both resolution shapes and names the legacy and skipped rows; P0bi witnesses it with three mutants, KILLED with passing twins
LAYER BOUNDARY: no (per A1.3's definition: records no layer verdict; adds or opens no brief)
pins CI run 39219338310 on 03ec9a7: success (reports/L2/ci/39219338310.json)
pins: clean 85/85; mutants 244/244 KILLED; twins 244/244; leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0 (harness summary row of the run's pins-report artefact, since dd5e8a2, skipped 0)
changed: harness/{ledger.py,pins.py,edits/P0bi_{resolves_unread,skipped_unnamed,legacy_unnamed}.toml,proposer.d/l2a-r-492f85a-f4-open-count.toml}, reports/L2/{forecasts/e687ebb3-….jsonl,ci/39219338310.json,status/l2a-r-492f85a-f4-open-count.md}
did: no open `instruction` issue; `claims next` took review 492f85a F4, the first candidate of master STATUS's `next` (none held); `reports/switchback-seed.txt` absent, so no chooser; no `awaits-guy` PR; ef1e03c F5 and cf5286c F4 are the same defect, carried
did: `open_count` reuses `outcomes`/`open_forecasts` (the resolver's own definitions), so the count equals `resolve`'s: at master e0ea222, 371 forecasts, 92 open, legacy 876d1d05c550 and a30e37db1152, 0 skipped. Mutants: `resolves_unread` (keys by `id` alone; reproduces the KeyError), `skipped_unnamed`, `legacy_unnamed`; local probe on a scratch copy KILLED all three, clean passed, as on CI
did: the counter that crashed is in `.claude/commands/review.md` (entrenched; brief 2: "Obligations on them are drafted as text for Guy"): the PR body drafts its replacement line, `uv run --frozen python -m harness.ledger open --head FETCH_HEAD || echo none`; `.claude/` untouched
did: no local full `make pins` (exceeds the 10-minute cloud limit); witnessed by the CI artefact. No tool call was denied
decided (not asked): a harness command plus a drafted one-line swap for Guy, rather than leaving the obligation open until `.claude/` is amended — p(stands on review)=0.8
decided (not asked): log-loss base rate is the sequential per-type empirical frequency of the builder's resolved forecasts (0.5 before any resolution, clipped at 1e-6), voided rows excluded — p(stands on review)=0.7
forecasts: made 4 (pins_green #253 p=0.8, review_accept #253 p=0.75, host_verdict L2 FIT p=0.35, session_minutes run 39217725955 bound 70 p=0.7); resolved 270 builder forecasts to date; cumulative log-loss 139.94 vs base rate 194.89 over 270
price: guy-items 0; guy-latency median 0.0h max 0.0h; sessions 1; runner-min 118
obligations added: L2a: `.claude/commands/review.md`'s open-forecast context line to call `harness.ledger open` (Guy's, entrenched; text in PR #253's body)
NEEDS YOU (at most 1): none
next: review ef1e03c F7; review ef1e03c F6; L2a obligation 36 if PR #251 is not merged
