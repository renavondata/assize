# reports/L2/status/l2a-o12-init-rusage.md
# STATUS — L2 — 2026-10-14 — d3ef92d — PR #199
VERDICT: SESSION DONE: L2a obligation 12 delivered; pins green on d3ef92d (pins CI run 38647379593 on d3ef92d: success, reports/L2/ci/38647379593.json)
LAYER BOUNDARY: no (per A1.3's definition: records no layer verdict; adds or opens no brief)
pins: clean all; mutants 197/197 KILLED; twins 197/197; leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0 (full run in CI 38647379593; local make pins not run, over 10 minutes; locally P4 clean True, and in a scratch copy `init_process_rusage` fails exactly the busy_child assertion, 0.06 s measured vs 1.0 s)
changed: judge/README.md, harness/{pins.py,fixtures/candidates.py,edits/P4_init_process_rusage.toml,proposer.d/l2a-o12-init-rusage.toml}, reports/L2/{forecasts/270443c6-….jsonl,ci/38647379593.json,status/l2a-o12-init-rusage.md}
did: `claims next #113 'L2a obligation 12'`: #113 is held by PR #185, skipped. No switchback seed exists, so I took the first open candidate, L2a obligation 12 (review 42d73311a233 F3)
did: fixture `busy_child` forks a child per step that burns BUSY_S CPU, and waits with WNOWAIT so the child is never reaped: its CPU is in the cgroup and in no rusage of init. P4 requires measured CPU in [1.0, 2.0) s. Mutant `init_process_rusage` (init's utime+stime+cutime+cstime) is KILLED; the existing `busy` case still passes under it, so only the new fixture kills it
did: a first draft of the mutant read `cgroup.procs` of the cut cgroup, which is empty (processes live in a child cgroup), so it mutated nothing and survived; it now takes init's pid from the runtime's inspect, as `compute.cgroup_of` does
did: pins-master run 38647379419 failed on this head as on every PR (master's workflow, entrenched); not mine to change. No judge code changed; the fix is the pin
decided (not asked): kill the mutant by a new fixture and assertion in P4 rather than a new pin — the obligation names P4 — p(stands on review)=0.85
decided (not asked): bound measured CPU above by 2x known as `busy` does, no new constant — p=0.85
forecasts: made 4 (pins_green #199 p=0.75, review_accept #199 p=0.7, host_verdict L2 FIT p=0.35, session_minutes bound 40 p=0.6); resolved 0; see `ledger proposer builder`
price: guy-items 0; guy-latency median 0.0h max 0.0h; sessions 1; runner-min 32 (pins CI of the green run)
obligations added: none. L2: obligations 13+ remain
NEEDS YOU (at most 1): none
next: L2a obligation 13 (the price floor `max(wall_s - unmeasured, 0)` is never exercised); #113 (PR #185) and obligation 9 (PR #196) are held
