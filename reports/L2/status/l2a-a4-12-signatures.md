# STATUS — L2 — 2026-10-20 — 8e3d631 — PR #273
VERDICT: SESSION DONE: brief 2 A4 item 12 (signatures): P0m refuses a guy-attributed commit that does not verify against the base's `allowed_signers` (`claims.signature_check`); seven mutants KILLED; the entrenched `allowed_signers` file itself is not added here
LAYER BOUNDARY: no (per A1.3's definition: records no layer verdict; adds or opens no brief)
pins CI run 39427330923 on 8e3d631: success (reports/L2/ci/39427330923.json)
pins: clean 91/91; mutants 289/289 KILLED; twins 289/289; non-causal 0; inconclusive 0; stale 0; leaked 0; skipped 0 (CI run 39427330923 pins-report summary, whole suite since 544d10b). Local probe: reports/L2/build/l2a-a4-12-signatures/p0m-probe.txt
changed: harness/{claims.py,pins.py,README.md,edits/P0m_{unsigned_guy_accepted,signers_from_branch,any_status_signed,instruction_commit_attributed,web_flow_any_key,web_flow_signs_commits,signers_unentrenched_accepted}.toml,proposer.d/l2a-a4-12-signatures.toml}, reports/L2/{forecasts/3b780559-….jsonl,ci/39427330923.json,build/l2a-a4-12-signatures/,status/l2a-a4-12-signatures.md}
did: master session (ASSIZE_ACK=no), no dispatched PR; no seed file, so the first open candidate: STATUS `next`, A4 item 12 (`claims next`: not held); no open instruction issues; open PR #257 (not awaits-guy) touches no path of this item
did: fixture: real ssh-signed commits (listed key, unsigned, unlisted key, key the commit itself adds, builder, builder with Instruction) plus pure web-flow cases; reader takes `%G?` under ssh against the base's file and under openpgp
did: process: no tool call denied. One attempted `Write` to /tmp/probe12.py was refused (file not read first) and replaced by a run of the existing probe script copy
decided (not asked): "attributed to guy" = a `guy` party with no `Instruction:` trailer, since a Builder's instruction commit carries Guy's authority by the issue's signature (Amendment 4 rule 5), not his key — p(stands on review)=0.75
decided (not asked): the file is read from the range's base, not the head, so a branch cannot add its own key — p=0.85
decided (not asked): the entrenched `allowed_signers` file and the web-flow key in the CI keyring are not added (entrenched/workflow changes); until the file exists nothing verifies and a guy-attributed commit on a branch is refused; recorded as an obligation — p=0.7
decided (not asked): no local `make pins`; in-memory P0m/P0bg clean and a per-mutant probe, whole suite in CI — p=0.8
forecasts: made 3 (pins_green #273 p=0.7, review_accept #273 p=0.6, session_minutes run 39426581842 bound 60 p=0.7); pins_green resolves true (first run 39427330923 success); cumulative log-loss not recomputed here
price: guy-items 0; guy-latency median 0.0h max 0.0h; sessions 1; runner-min not read (ledger price timed out locally)
obligations added: L3: none; L2: entrenched `allowed_signers` listing Guy's signing key, with CODEOWNERS entry, and web-flow public key in the pins runner's keyring (needs Guy's instruction)
NEEDS YOU (at most 1): none
next: brief 2 A4 item 13 is superseded by Amendment 5 (P0ar); else audit findings 2 and 3 once Guy files the instruction #270 recommends, or audit finding 5/6 (judge/scoring.invalid range check; P20 schema mutant)
