# STATUS — L2 — 2026-10-14 — cd68769 — PR #192
VERDICT: SESSION DONE: L2a obligation 7 (review 9d8e7336a6b9 F1): P1 checks that every issued seed came from `secrets.randbelow`
LAYER BOUNDARY: no (per A1.3's definition: records no layer verdict; adds or opens no brief)
pins: pins CI run 38598395181 on cd68769: success (reports/L2/ci/38598395181.json). Local `make pins` on cd68769 with GITHUB_HEAD_REF unset: clean 67/67; mutants 189/189 KILLED; twins 189/189; leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0 (reports/L2/builder/cd68769584657390b8bf3d4f9949c0672a1d0574/make-pins-head-ref-unset.txt). The first local run failed P0r only, because GITHUB_HEAD_REF=instr-176-pins-master was inherited (make-pins.txt, same dir). pins-master run 38598395460 failed before `make pins`: its `git fetch` has no credentials, on every PR (issue #194)
changed: harness/pins.py, harness/edits/P1_csprng_replaced.toml, harness/proposer.d/l2a-o7-csprng-witness.toml, reports/L2/{forecasts/,builder/,ci/,status/}
did: P1 swaps in a wrapper for `secrets.randbelow` while seeds are issued, records each draw, and requires every issued seed to be a draw with bound SEED_SPACE. The original function is restored in `finally`.
did: mutant csprng_replaced (the review's probe: a fixed-seed `random.Random(0)` replaces `secrets` in `seeds.fresh`) is KILLED: "10 of 10 are not; 0 draws" (P1-csprng_replaced-mutant.log); its twin passed. judge/ is untouched, so judge_sha256 does not move.
did: closed #176 (PR #183 merged 15:14Z). Skipped: #113 is held by PR #185; L2a obligation 5 is already merged (PR #171); obligation 6 is held by PR #191. No awaits-guy PR is open. reports/switchback-seed.txt is absent, so no chooser: took the first open candidate.
did: no tool denial. Transcripts were written by shell redirection of `make pins` output; no file was edited by shell.
decided (not asked): witness the CSPRNG by recording draws in-process, not by a static scan of judge/seeds.py — p(stands on review)=0.8
decided (not asked): filed #194 to Guy rather than leave pins-master's failure unrouted; this PR does not touch .github/ — p=0.85
decided (not asked): GITHUB_HEAD_REF from PR #183's event is a runner-environment artifact, not a P0r defect; it is witnessed by the re-run with the variable unset — p=0.75
forecasts: made 4 (pins_green, review_accept, host_verdict, session_minutes) in reports/L2/forecasts/04149669-80b9-4bdf-bff9-77be47258f46.jsonl; resolved 0; cumulative figures unchanged
price: guy-items 8; guy-latency median 0.1h max 2.6h; sessions 33; runner-min 1315 (carried from the previous STATUS; not re-run this session)
obligations added: L3: build.yml on a master session inherits the dispatching PR's GITHUB_HEAD_REF, which points P0r (and anything else that reads it) at another branch
NEEDS YOU (at most 1): issue #194: pins-master (.github/, entrenched) cannot fetch master on any PR; fix it before adding it to required checks (#176 item 4)
next: L2a obligation 8 of reports/L1/REPORT.md (seed-store keys depend on CPython's tuple hash, and no version is recorded)
