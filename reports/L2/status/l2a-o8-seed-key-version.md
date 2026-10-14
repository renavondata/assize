# reports/L2/status/l2a-o8-seed-key-version.md
# STATUS — L2 — 2026-10-14 — 775f2c9 — PR #195
VERDICT: SESSION DONE: L2a obligation 8 delivered; pins green on 775f2c9 (pins CI run 38609729409 on 775f2c9: success, reports/L2/ci/38609729409.json)
LAYER BOUNDARY: no (per A1.3's definition: records no layer verdict; adds or opens no brief)
pins: clean 69/69; mutants 192/192 KILLED; twins 192/192; leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0 (full run in CI; local make pins not run, over 10 minutes; P26 key_version_ignored KILLED 1.8s + twin 1.6s in that run)
changed: judge/seeds.py, judge/README.md, harness/pins.py, harness/edits/P26_key_version_ignored.toml, harness/proposer.d/l2a-o8-seed-key-version.toml, reports/L2/{forecasts/3e50a03b-….jsonl,ci/38609729409.json,status/l2a-o8-seed-key-version.md}
did: `claims next #113`: held by PR #185; obligation 7 held by PR #192; took L2a obligation 8 (review 9d8e7336a6b9 F2); no switchback seed, so the first open candidate
did: every seed record states `key_version` (implementation-version); `admit` refuses `key_version`, recording nothing, if any earlier record states another or none; new pin P26 rather than P1 to avoid PR #192's edits
did: pins-master run 38609729271 failed on this head as on every PR (master's workflow, entrenched, per review of #191 F6); not mine to change
decided (not asked): a record without `key_version` counts as another version (fail closed) — p(stands on review)=0.8
decided (not asked): version is the full `platform.python_version()`, so a micro upgrade also needs a new store — p=0.7
forecasts: made 4 (pins_green #195 p=0.6, review_accept #195 p=0.6, host_verdict L2 FIT p=0.35, session_minutes bound 40 p=0.5); resolved 0; see `ledger proposer builder`
price: guy-items 0; guy-latency median 0.0h max 0.0h; sessions 1; runner-min 35 (pins CI of the green run)
obligations added: L3: none. L2: obligations 9+ remain (L2a obligation 9 next, once not held); the declared 40 minutes was about met
NEEDS YOU (at most 1): none
next: L2a obligation 9 (P5's clairvoyant searches nested step keys); #113 (PR #185) and obligation 7 (PR #192) are held
