# reports/L2/status/l2a-o18-image-carries-verify.md
# STATUS — L2 — 2026-10-15 — b264ff0 — PR #207
VERDICT: STOPPED: review round 1 BLOCK (F1: STATUS cited no `pins` run, so P0l failed and its mutants went NON-CAUSAL); pins CI run 38720970186 on b264ff0 failed on P0l alone; this reports-only commit cites it, and the next commit will cite the green run on this head. Code is unchanged since 9cc7af6; local `make pins` green there
LAYER BOUNDARY: no (per A1.3's definition: records no layer verdict; adds or opens no brief)
pins: clean 74/74; mutants 209/209 KILLED; twins 209/209; leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0 (local `make pins` on 9cc7af6, Podman only, Docker not usable here, reports/L2/builder/9cc7af6ba348ae731078848237479152a6de7442/make-pins.txt)
changed: release/Containerfile, judge/{__main__.py,README.md}, harness/{pins.py,edits/P31_*.toml,proposer.d/l2a-o18-image-carries-verify.toml}, reports/L2/{forecasts/8d5ce540-….jsonl,builder/9cc7af6…/,status/l2a-o18-image-carries-verify.md}
did: `claims next '#113' 'L2a obligation 18'`: #113 held by PR #185 (skipped); took 18, master STATUS's `next`. PR #205 (obligation 20) holds no 18. No switchback seed, so the first open candidate
did: `release/Containerfile` (outside judge/) builds offline from the judge's pinned base; entrypoint `python -m judge`. `judge/__main__` imports `evaluate` (needs jsonschema, absent from the base) only inside `_evaluate`, so verify/credential/register need the standard library alone
did: P31: under every usable runtime the image is built from a context of the Containerfile and judge/; with no network and a read-only root, verify passes P9's fixture ledger printing what the host's prints, and fails an altered record and a non-head anchor. Mutants `verify_omitted`, `eager_imports` KILLED, twins pass
did: new branch, so 4 forecast rows were committed before the first pins run; files written with Edit/Write; no tool call denied. The declaration comment on #206 said 60 minutes; the forecast row says 90 (the row stands)
decided (not asked): obligation 18 is L2a, via brief 2 A2 item 15 (Containerfile, entrypoint and verify in place by the baseline, outside judge/) — the L2c seal then only builds and pins it — p(stands on review)=0.75
decided (not asked): lazy import of `evaluate` in `__main__` rather than shipping the Worlds' dependencies in the image — p=0.8
decided (not asked): P31 witnesses `release/**` as well as JUDGE_SIDE — p=0.85
forecasts: made 4 (pins_green #207 p=0.5, review_accept #207 p=0.6, host_verdict L2 FIT p=0.35, session_minutes bound 90 p=0.6); resolved 0; see `ledger proposer builder`
price: guy-items 0; guy-latency median 0.0h max 0.0h; sessions 1; runner-min 0
obligations added: L3: none
NEEDS YOU (at most 1): none
next: L2a obligation 19 of reports/L1/REPORT.md (NetHack's own committed price); #113 (PR #185) and obligation 20 (PR #205) are held
