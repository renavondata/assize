# STATUS — L2 — 2026-10-16 — a7449be — PR #222
VERDICT: SESSION DONE: L2a obligation 24 is built and discharged by P2 with mutant `private_storage_mounted`; pins CI run 38948215637 on a7449be concluded success
LAYER BOUNDARY: no (per A1.3's definition: records no layer verdict; adds or opens no brief)
pins: clean 77/77; mutants 218/218 KILLED; twins 218/218; leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0 (local `make pins` on a7449be, Podman only, reports/L2/builder/a7449be099bf746966053f61cef6caab8809b6d8/make-pins.txt)
pins CI run 38948215637 on a7449be: success (reports/L2/ci/38948215637.json)
changed: harness/{pins.py,edits/P2_private_storage_mounted.toml,proposer.d/l2a-o24-p2-derived-paths.toml}, reports/L2/{forecasts/c92860b8-….jsonl,builder/a7449be…/,ci/38948215637.json,status/l2a-o24-p2-derived-paths.md}
did: closed #211 (PR #214 merged); #212 is held by PR #221; took obligation 24, the next obligation no open PR names; no switchback seed. No tool call denied
did: P2 builds judge-private storage and a ledger directory in its scratch with the judge's own writers (`registry.credential`, `ledger.append`) and probes every path found there (key, credentials, heads, ledger), beside the existing judge paths. Mutant `private_storage_mounted` mounts the system temp directory read-only into the candidate: KILLED, twin passes
did: the first local `make pins` failed P0m and P0y because my commit message had a blank line between the `Proposer:` and `Co-Authored-By:` lines; I amended the unpushed commit and reran (`make-pins-run1-bad-trailer.txt` keeps the first). Only Podman was witnessed locally; Docker ran in CI
decided (not asked): the mutant mounts the system temp directory, since private storage has no fixed location and the pin's scratch lives under it — p(stands on review)=0.7
decided (not asked): P2 does not probe a host-configured production private path, only the layout the judge's writers produce — p=0.6
forecasts: made 4 (pins_green #222 p=0.5, review_accept #222 p=0.55, host_verdict L2 FIT p=0.35, session_minutes bound 60 p=0.6); resolved 0
price: guy-items 0; guy-latency median 0.0h max 0.0h; sessions 1; runner-min 0
obligations added: L3: none; L2a: P2's mutant mounts the whole temp directory, so a narrower mount of only the private directory is not distinguished from it
NEEDS YOU (at most 1): none
next: L2a obligation 25 of reports/L1/REPORT.md (stray-container detection is runtime-global); #113 (PR #185), 19 (PR #217), 21 (PR #210), 22 (PR #213) are held
