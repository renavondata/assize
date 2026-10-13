VERDICT: ACCEPT WITH OBLIGATIONS
proposer: {kind: reviewer, model: claude-sonnet-5-5, session: e6bb2d52-892a-4a03-b66d-8179e048655a}
reviewed head: b7ee2fb86b52eb49ea1f1dfd1662a2e51d9fd776 (PR #160, Instruction: #136)

Instruction check (A1.5): issue #136 was labelled `instruction` by gfrmin (timeline 2026-10-12T10:19:54Z). The diff to `docs/briefs/brief-2-nethack.md` is the issue's amendment text verbatim, with the heading suffix "; instruction #136" (precedent: Wish #80). The `Price:` line and the edit note are issue metadata and are not transcribed. Other files are session bookkeeping (STATUS, forecasts, CI record, builder transcripts) and `harness/proposer.toml` (session id only, as every building session updates it). Nothing is implemented beyond the instruction. No entrenched path is touched; this is not a layer boundary.

Reproduction: `make pins` on a scratch worktree at the PR branch, GITHUB_HEAD_REF unset: clean 59/59; mutants 161/161 KILLED; twins 161/161; leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0 (reports/L2/review/b7ee2fb86b52eb49ea1f1dfd1662a2e51d9fd776/make-pins.txt). Hosted `pins` on this head: success, run 38308997650. Agrees with the Builder's 59/59, 161/161.

FLAKE (recorded, not a finding): my first reproduction ran on a detached worktree with GITHUB_HEAD_REF unset and read clean 58/59, mutants 160/161, 1 non-causal: P0r (real-branch name resolved to '') and P0r/late_forecast_admitted. Re-run on the same tree with the branch name checked out is green. Cause is my scratch setup, not the PR (reports/L2/review/b7ee2fb86b52eb49ea1f1dfd1662a2e51d9fd776/make-pins-detached-worktree.txt).

F1: P0r fails closed on a detached checkout with no GITHUB_HEAD_REF (name resolved as ''), and the failure shows as a clean-pin FAIL plus a NON-CAUSAL mutant rather than as an environment error — severity: OBLIGATION on L3 — witness: reports/L2/review/b7ee2fb86b52eb49ea1f1dfd1662a2e51d9fd776/make-pins-detached-worktree.txt (joins the Builder's L3 obligation on inherited GITHUB_HEAD_REF in STATUS).
F2: The Wish #134 amendment's scope items (parallel runner, `pins.yml` on `[self-hosted, pins]`, P-par, `ledger price` wall-clock) are unimplemented here by design; they become items for later sessions, and the self-hosted `pins` runner registration is Guy's alone — severity: OBLIGATION on L3 — witness: docs/briefs/brief-2-nethack.md (Stop-and-report boundaries).

forecasts resolved: 8497c8c6bc30 True (pins_green pr 160, run 38304768437); 40d37ee189e8 True (session_minutes, 41.9 of 50). Both appended by `harness.ledger resolve` as mechanism. 157fa18e1313 (review_accept) is left to the mechanism after merge.
