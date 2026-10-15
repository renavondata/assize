# STATUS — L2 — 2026-10-15 — 2a80456 — PR #206
VERDICT: SESSION DONE: L2a obligation 17 discharged by P30; pins green on 2a80456 (pins CI run 38697151649 on 2a80456: success, reports/L2/ci/38697151649.json)
LAYER BOUNDARY: no (per A1.3's definition: records no layer verdict; adds or opens no brief)
pins: clean 73/73; mutants 207/207 KILLED; twins 207/207; leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0 (pins CI run 38697151649 on 2a80456, Docker and Podman, skipped 0/73; local `make pins` on 2a80456 agrees, Podman only, reports/L2/builder/2a80456802a9977d2ee790aefb32a0c9b133142c/make-pins.txt)
changed: judge/{evaluate.py,README.md}, harness/{pins.py,edits/P30_image_id_unchecked.toml,proposer.d/l2a-o17-image-digest-stated.toml}, reports/L2/{forecasts/7f8b49ba-….jsonl,ci/38697151649.json,builder/2a80456…/,status/l2a-o17-image-digest-stated.md}
did: `claims next '#113' 'L2a obligation 17' …`: #113 held by PR #185; took 17, master STATUS's `next`. PR #205 (obligation 20) holds no 17–19. No switchback seed, so the first open candidate
did: stated in evaluate's docstring and judge/README.md: a record's `image` is the image ID its `runtime` reports (`.Id`), under Podman and Docker's classic store the SHA-256 of the config blob, never a manifest digest or a name; `_present` refuses `image_not_id` before any seed when the asked reference resolves to another ID
did: P30: under every usable runtime the incumbent's record `image` equals the config blob's SHA-256 read from `save`; through a shim runtime resolving an alias to the incumbent (control: it does), the registered alias is refused `image_not_id`, seed store and ledger unchanged. Mutant `image_id_unchecked` KILLED, twin passes
did: new branch, so 4 forecast rows appended before the first pins run. Witness copied by `cp`; files written with Edit/Write; no tool call denied
decided (not asked): obligation 17 is L2a, not L2c (PR #205 read it as L2c): the meaning of `image` lives in judge/, which freezes at the L2a baseline, and A4 item 15 asks the seal's needs be in place by then — p(stands on review)=0.75
decided (not asked): state the digest as the runtime's image ID and witness it as the config digest under the runtimes CI has, rather than refuse Docker's containerd store outright; under that store P30 would fail, not pass silently — p=0.7
decided (not asked): a new pin P30 rather than cases in P17, so P17's five mutants do not each pay for a `save` — p=0.85
forecasts: made 4 (pins_green #206 p=0.6, review_accept #206 p=0.6, host_verdict L2 FIT p=0.35, session_minutes bound 120 p=0.6); resolved 0; see `ledger proposer builder`
price: guy-items 0; guy-latency median 0.0h max 0.0h; sessions 2; runner-min 176
obligations added: L3: none
NEEDS YOU (at most 1): none
next: L2a obligation 18 of reports/L1/REPORT.md (the released image carries `verify`); #113 (PR #185) and obligation 20 (PR #205) are held
