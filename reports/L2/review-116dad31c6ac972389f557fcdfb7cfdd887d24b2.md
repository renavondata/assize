VERDICT: ACCEPT WITH OBLIGATIONS

Review of PR #287 (instruction #281: an awaits-guy label starts the next master Builder, queued behind any in progress) at 116dad31c6ac972389f557fcdfb7cfdd887d24b2.
proposer: {kind: reviewer, model: claude-opus-5-5, session: e7bce034-9dcb-47c2-9118-88e46935002b}; review run 39533467031.
Builder of record (harness/proposer.d/instr-281-awaits-guy-queue.toml): session 4eac5cf8-ca6a-4bec-a3ad-6335b351f655, not this session.
Instruction PR (`Instruction: #281`). #281 is signed: labelled `instruction` by gfrmin at 2026-10-21T01:23:25Z, and GraphQL `userContentEdits` shows no body edits. Paths: harness/{pins.py,README.md,edits/P0bq_*.toml,proposer.d/instr-281-awaits-guy-queue.toml} and reports/L2/ only. No entrenched path is touched (`.github/workflows/build.yml` is unchanged). Not a layer boundary: no verdict line in REPORT.md, and no brief is added or opened. Mergeable: MERGEABLE, base 088417a = origin/master.

Criteria under review, verbatim (instruction #281 and CLAUDE.md A1.5):
- A1.5: "The Reviewer's first criterion on an instruction pull request is that the diff does what the issue says and nothing else"
- #281.1: "When a pull request gains the `awaits-guy` label, the Builder's workflow starts the next master Builder on the next brief item, as it would after an acknowledgement. Pre-stated criterion: an `awaits-guy` pull request does not stop the master queue."
- #281.2: "The new trigger does not start a Builder while another Builder session is in progress on master."
- #281.3: "Pin: a mutant that drops the trigger fails the new pin."
- #281: "Nothing else."

Met:
- #281.1 already held on master through instruction #102: build.yml's job `if:` has an `awaits-guy` clause, the group expression routes that label to `build-master`, and the checkout step does not check out the PR. The Vizier's draft check on #281 (comment, 2026-10-21T00:24:14Z) said so, and Guy signed the draft anyway. A diff that changes no workflow and adds only the witness is the minimal reading. P0bq's clean run evaluates the awaits-guy event and finds that it starts a Builder on master in queue build-master.
- #281.2: the job-level group is `build-master` for every master-Builder event, and `cancel-in-progress: false`. A run that GitHub starts in that group therefore waits for the one in progress and does not replace it. P0bq asserts both, for all four events.
- #281.3: mutant `awaits_guy_trigger_dropped` (P0aj's `awaits_guy_clause_removed` edit, which deletes the awaits-guy clause from the job `if:`) is KILLED. So are `awaits_guy_own_queue` and `master_cancels_in_progress`. Each fails only its own assertion (Builder's scratch transcript p0bq-scratch-4d8d8ba.txt).
- Nothing else: besides the pin, its two edit files and the registry row, the diff adds a README paragraph, the proposer row, forecasts, the STATUS and CI witnesses. These are the Builder procedure's standard companions. No code beyond the pin.

Reproduction: `make pins` on a GitHub clone (`gh repo clone renavondata/assize`, origin https://github.com/renavondata/assize.git) checked out at 116dad3, 2026-10-21T02:33Z–03:27:44Z. Result: clean 92/93 (P0x FAILED); mutants 294/297 KILLED; twins 294/297; leaked 0; stale 0; inconclusive 0; non-causal 3 (P0x's); exit 2; PINS FAILED. P0bq is clean ok and its 3/3 mutants are KILLED. This equals the Builder's CI run 39527397797 on 4d8d8ba. No verdict differed and no flake is recorded.
CI on the reviewed head:
- `pins` run 39533464802: failure. Clean 92/93 (P0x), mutants 294/297, non-causal 3 (P0x).
- `pins-master` run 39533467714 (master's judge): failure on P0x alone, clean 91/92, mutants 291/294. Run 39533460734 was cancelled, superseded.
So master's own pins are red on P0x too; the red is not caused by this diff.
Witnesses: reports/L2/review/116dad31c6ac972389f557fcdfb7cfdd887d24b2/make-pins.txt (full transcript) and probe-on-trigger.txt.
Cleanup: scratch clone /tmp/rv287.oQgW, probe copies /tmp/rv287probe{,2}.* and /tmp/rv287-* were removed. `pgrep -af '[h]arness run|make [p]ins'` was empty at 2026-10-21T03:31:53Z. /tmp/assize-scratch-{2eqhwk0j,9keas62n,qdguqy2u} and /tmp/rv{159,201}-pins.txt predate this session and were left.

F1: P0x is red on every head, master included, because the signed instructions #281, #284 and #286 carry no `Price:` line. Only gfrmin can add one without unsigning them (Amendment 4 rule 5). P0x's three mutants are NON-CAUSAL for the same reason: the twin fails too. This diff does not cause it: master's pins-master run fails identically, and the reviewed criteria are met. But the approval gate of the review procedure ("`pins` success") cannot be reached until the price lines exist, so this review does not approve. — severity: OBLIGATION on L3: the Vizier's draft template carries a `Price:` line before Guy signs, and P0x's real-issue half is checked at the draft check. Mutant `draft_without_price` (the draft check passes a draft lacking `Price:`) is KILLED — witness: reports/L2/review/116dad31c6ac972389f557fcdfb7cfdd887d24b2/make-pins.txt
F2: neither P0bq nor P0aj reads build.yml's `on:` block. Two edits that stop GitHub from ever delivering an awaits-guy label to the job survive both pins (probe, reproduced): `pull_request: types: [labeled]` → `[opened]`, and deleting the `pull_request:` trigger. #281.3 is met as written, since "a mutant that drops the trigger" is killed and the issue's draft check named the `if:` clause as the trigger. So no criterion is unmet. But the pin's claim, "an awaits-guy label starts the next master Builder", is wider than what it evaluates. — severity: OBLIGATION on L3: P0bq requires `labeled` among `on.pull_request.types` (and `on.push.branches` ∋ master, `on.issues.types` ∋ labeled, `workflow_dispatch` present) for the events it evaluates. Mutants `pr_labeled_trigger_removed` and `pr_trigger_types_opened` are KILLED — witness: reports/L2/review/116dad31c6ac972389f557fcdfb7cfdd887d24b2/probe-on-trigger.txt
F3 (recorded, not a finding): GitHub's concurrency keeps at most one pending run per group. A third master-Builder event while one runs and one waits cancels the pending one, so a burst of awaits-guy labels yields one queued Builder, not one per label. #281.2 asks only that none start while one is in progress, and that holds.
F4 (recorded, not a finding): the Builder's session_minutes forecast (bound 30) resolved false at 68.4 minutes, and its pins_green forecast resolved false. Both resolutions are the mechanism's, in the following commit.
F5 (recorded, not a finding): the /review context command 5 (open-forecast count) crashes with `KeyError: 'id'` on id-less L0 rows, as in earlier reviews; `.claude/` is entrenched. The resolver's own count (L2: 86 open, 80 typed; resolved 3) is used instead.

Routing: ACCEPT WITH OBLIGATIONS, with `pins` failure on the head. The failure is not caused by the diff, but the approval gate is unmet. This review therefore does not approve. It removes `needs-review` and labels the PR `awaits-guy`, because the only unblocking act is Guy's: the `Price:` lines on #281, #284 and #286 (the Builder's STATUS NEEDS YOU item). Once those exist and a re-run of `pins` on this head is green, a review session can approve on this file without new findings.

forecasts resolved: by `harness.ledger resolve --session 39533467031` in the following commit (mechanism): da05f0736dc5 False, 2168eb6dffd2 False, fe571889b6ea True. None by hand. This session's own session_minutes forecast (comment on #287) is not resolved by this session.

NEEDS GUY: add the `Price:` line to #281, #284 and #286, then re-run pins on PR #287
