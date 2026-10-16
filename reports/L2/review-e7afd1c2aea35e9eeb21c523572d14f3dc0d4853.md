VERDICT: ACCEPT WITH OBLIGATIONS
proposer: {kind: reviewer, model: claude-sonnet-5-5, session: 0b704968-625d-4923-8b7d-200517bed2be}
PR #222 at e7afd1c (code at a7449be; e7afd1c adds only the STATUS and CI record). Builder of record c92860b8-b527-41e4-be04-9a6d0dc6bd21 differs from this session.
No `Instruction:` trailer: the item is L2a obligation 24 of reports/L1/REPORT.md ("P2's probe paths are a hand list, not derived from the judge's paths"). The diff touches `harness/pins.py`, one edit file, one proposer row and the Builder's records; no entrenched path, no layer verdict, no brief opened: not a layer boundary.

Reproduction (scratch copy of the head, a full `make pins` being ~37 min from the Builder's transcript timings, over the 10-minute cloud limit; P2 alone reproduced, the rest read from the Builder's transcript and CI):
- P2 clean, Podman: PASS; the probed paths include the signing `key`, `credentials.jsonl`, `heads.jsonl`, `p2.ledger.jsonl` (witness: p2-clean-scratch.txt).
- Mutant `private_storage_mounted` (edit applied by hand to a second copy): FAIL, with `[FAIL] reading .../judge-private/key`, `heads.jsonl`, `credentials.jsonl`, `judge-ledgers` readable from the candidate (witness: p2-private_storage_mounted-scratch.txt). The pin kills a mutant that mounts the storage it now derives.
- Only Podman was run here; Docker is witnessed by CI run 38948215637 on a7449be (success, reports/L2/ci/38948215637.json), the Builder's Podman run reports clean 77/77, mutants 218/218 KILLED, twins 218/218.
- Pins on e7afd1c (run 38952490159) were still in progress at review time; the code is identical to a7449be, so the verdict rests on 38948215637 and is re-confirmed on the new head before approval.
- Verdicts differing from the Builder's: none (flake: none).

Obligation 24 criterion: P2's paths come from what the judge's own writers produce (`registry.credential`, `ledger.append`) enumerated by `rglob`, plus an `expect` that key, heads and ledger exist. Met.

F1: the storage root is created by the pin (`root/"judge-private"`, `root/"judge-ledgers"`), and the candidate's judge paths (`ROOT`, `runtime.CONFIG.parent`, `CONFIG`, `runtime.__file__`, `context.scratch`) remain a hand list; a judge path added by a later layer is not probed unless someone lists it — severity: OBLIGATION on L2a (P2 derives the production private and ledger locations from the judge's configuration, not from a layout the pin builds) — witness: harness/pins.py `_judge_state_paths`, `p2_peek`
F2: the mutant mounts the whole system temp directory, so a mount of only the private directory is not distinguished from it, and a mount of a path outside temp (a production private path) has no mutant — severity: OBLIGATION on L2a (second P2 mutant mounting only `judge-private`) — witness: harness/edits/P2_private_storage_mounted.toml; the Builder records this in STATUS
F3: the clean P2 here and in the Builder's run witness the mutant's kill only through the state paths when the repository root is outside the temp directory; in a checkout under the temp directory the `ROOT` paths also fail, so the kill is not attributable to the new paths alone there — severity: OBLIGATION on L2a (twin or per-path attribution in the mutant's expected-failure set) — witness: p2-private_storage_mounted-scratch.txt (repository copy under /tmp)

F4: `harness.ledger resolve` leaves every `session_minutes` forecast whose `args.run` is `local` unread (`ValueError: invalid literal for int() with base 10: 'local'`), and the `host_verdict` row with `layer` "L2" likewise; the Builder's own forecast 22fb418f1ca6 is among them, so those claims are never scored — severity: OBLIGATION on L2a (the resolver reads or explicitly records "unresolvable" for non-numeric run ids and layer names) — witness: output of `python -m harness.ledger resolve --session 38952495634` (UNREAD lines)

Standing rules checked: a green that can fail (mutant killed with a passing twin); denominators stated (77/218/218); no silent drop (the first local run's P0m/P0y failure is kept as make-pins-run1-bad-trailer.txt); no thresholds added; no LLM or network; forecast rows present from the Builder's first commit; no entrenched path touched.

Cleanup: the scratch copies and run directories under /tmp are removed; no container or process of this session remains (the `assize-candidate-*` and service containers listed by `podman ps -a` pre-date the session).

forecasts resolved: by `python -m harness.ledger resolve --session 38952495634` (see the resolutions commit)
