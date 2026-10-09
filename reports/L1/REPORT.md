# L1 report: interface, sealed judge, Crafter (brief 1, amendments A1–A9)

## Verdict
**SEALED. Crafter FIT. Interface PROVISIONAL.**

- **SEALED.** All pins pass (this head: pins CI run 37840644452 on 25f36e6, success) and every mutant is KILLED with a passing twin:
  - In CI at the pilot's code: pins CI run 37829367792 on cab0ca0, 30/30 clean, 80/80 KILLED, 0 leaked.
  - On the host in the same run as the pilot: measure 37831165785, 30/30, 80/80, 0 leaked.
  - At this pull request's head, with P0b's added mutant: 30/30 clean, 81/81 KILLED (`make-pins-25f36e6.txt`).
- **FIT.** δ = 0.5 achievements per episode is detected with 90% posterior mass at 33 episodes per arm. That is 92 s of wall-clock against the one-day budget (86400 s), so P(FIT | this pilot) is near 1 under the stated shift assumption.
  - The decision is insensitive to the weak-proxy caveat: even δ = 0.25 needs 403 s, a factor of about 214 inside the budget.
  - Sole witness: host measure run 37831165785, on a Ryzen 5 5600X, 12 threads, rootless Podman with crun on cgroup v2.
- **Interface PROVISIONAL.** Brief 1 decides only this much. Full acceptance is brief 2's zero-diff test. This report finds that test cannot pass as brief 2 is written: see *Interface finding*.

## Pre-stated criteria
Denominator: every criterion that brief 1 and its amendments state.

| Criterion | Status | Witness |
|---|---|---|
| FIT: δ = 0.5 detectable within one day on the host | MET (FIT) | `measure-37831165785/report.md`; reviewer recomputation `review/571ee563f91d71938cef0ff52d76a849073adccb/host-witness.txt` |
| SEALED: all pins pass (P1–P7, with P8 replaced by P0b under A3) | MET | see *Pins*; `make-pins-25f36e6.txt`; `ci/37829367792.json`; `measure-37831165785/pins-summary.json` |
| P2 passes under both runtimes (A1 item 2) | MET | `p2/ci-clean-*.log` (Docker, CI); `p2/host-clean-*.log` (rootless Podman, host) |
| A2 item 3 and A3 item 2: static scan; a patch adding a `harness.mutants` reference is caught | MET at the tree. The judge is not yet an image, so the image scan is owed at the seal (brief 2 A2 P21) | `P0b/judge_imports_mutants` KILLED, added in this PR |
| A4 item 1: P9 ledger tamper, 3 named mutants plus O_APPEND | MET (6 mutants) | P9 rows |
| A4 item 2: proposer from the registering credential; refusal pinned | MET | P16, P17, P18 |
| A4 item 3: reliability table and mean entropy per target | MET | P13; `measure-37831165785/report.json` |
| A4 item 4: compute price committed before the first scored run | MET. `[price.crafter]` was committed in 08856e7 (2026-10-07); the first scored run was measure 37831165785 (2026-10-08) | P12; `judge/config.toml` |
| A4 item 5: harness process hygiene and P10 | MET | P0h (5 mutants), P10 |
| A4 item 6: harness half of item 5 witnessed on the host before any pilot | MET | measure 37561995448 (P0h, 0 leaked), and the pins step of 37831165785 precedes its pilot |
| A4 items 7a, 7b, 7c | MET | P0k, P0l, P0m |
| A4 item 8: host facts | MET | P0j; `measure-37831165785/facts.txt` |
| A5: same-second bytecode, genesis `prev_sha256`, multi-party trailers | MET | P0i `pycache_top_level_only`, P9 `genesis_empty`, P0m `first_proposer_only` |
| A6: `PYTHONPYCACHEPREFIX` | MET | P0i `pycache_prefix_unset` |
| A7: determinism of the World of item 1; crafter==1.8.3 | MET | P11 (6 mutants); `crafter-nondeterminism.txt` |
| A9: merge commits attributed to their author account | MET | P0m `unknown_merge_author` |
| Configs, caps and targets committed before the first scored run | MET. The manifest's targets: c00170e. Price: 08856e7. `pilot/config.toml`: final at cab0ca0, the commit the pilot ran | git log |
| Stop-and-report: the cap is reached before the pilot completes | NOT TRIGGERED. 200/200 episodes in 277.9 s of a 7200 s cap | `measure-37831165785/report.md` |

## Schema and manifest
- **Schema.** `worlds/spec/rpc.schema.json` and `worlds/spec/manifest.schema.json`, `schema_version` 1.0.0, JSON-RPC 2.0 over stdio. The schema holds no World vocabulary (P6).
- **Manifest.** `worlds/crafter/manifest.json`: crafter 1.8.3 under A7; episode length 10000.
  - Observation: `semantic` (64×64 categorical) and the inventory counts.
  - 17 actions.
  - Six next-step targets, each with support 0–9: health, food, drink, energy, wood, stone. The rationale is in the manifest.
  - Utility: the count of distinct achievements, with Hafner's score reported beside it.

## Committed configs
- `judge/config.toml`: candidate limits (1 CPU, 1024 MiB, 64 pids); timeouts (step 10 s, episode 600 s); `[price.crafter]` (cpu_s 4.1667e-4, memory_gb_s 3.8805e-4 achievements); calibration bins 10.
- `pilot/config.toml`: 200 episodes; cap 7200 s; δ ∈ {0.25, 0.5, 1}; mass 0.9; fit 0.5, marginal 1.0; budget 86400 s; requests of 10; incumbent proposer from the trailer of 0f698c4.

## Judge hash
`judge_sha256 = 28710725463f36b93123771ddcda4390e3b02f4ee15488b42834809929eda7ff`.
- It covers `judge/`, `worlds/` and `uv.lock`.
- It is the same on every pilot record and at this pull request's head, which changes no hashed path.
- It does not cover `pilot/` (obligation 37).

## Incumbent (random), predictive floor, compute
Denominator: 200 episodes requested, 200 recorded, 200 `terminal`. Nothing dropped.
- Utility: mean 2.285, min 0, max 5.
  - Counts: 0:4, 1:67, 2:28, 3:72, 4:27, 5:2.
  - Hafner score 1.470.
- Floor log-loss per scored step: 35064 steps per target, 0 missing, 0 infinite. Mean entropy in brackets.
  - health 0.807 (0.798)
  - food 1.987 (1.597)
  - drink 2.120 (1.713)
  - energy 0.947 (1.148)
  - wood 0.298 (0.715)
  - stone 0.179 (0.672)
  - Reliability tables: `measure-37831165785/report.json`.
- Compute per episode: CPU mean 0.1027 s, wall mean 0.530 s, peak memory max 23.96 MB, price mean 4.62e-5 achievements.

## Time-to-learn and throughput
- Assumption: a candidate's utility is distributed as the incumbent's, shifted by δ.
- A random agent's variance is a weak proxy for a competent agent's (obligation 41).
- Throughput: 0.720 episodes/s over 277.9 s of whole-pilot wall-clock, 20 requests.

| δ | episodes per arm | posterior mass | wall-clock s (both arms) |
|---|---|---|---|
| 0.25 | 145 | 0.906 | 403 |
| 0.5 | 33 | 0.904 | 92 |
| 1.0 | 9 | 0.918 | 25 |

## Pins
Registry `harness`: 30 pins, 81 mutants at this head. Each pin with its mutants, every one KILLED with a passing twin:

| Pin | Mutants |
|---|---|
| P0 | survivors_ignored |
| P0b | env_switch, judge_imports_mutants (added in this PR) |
| P0c | clean_failures_ignored |
| P0d | inconclusive_dropped |
| P0e | validation_off |
| P0f | twin_ignored |
| P0g | stale_ignored |
| P0h | death_signal_reverted, scratch_kept, leaked_not_counted, subreaper_not_set, sweep_skipped |
| P0i | pycache_top_level_only, pycache_prefix_unset |
| P0j | incomplete_facts_accepted |
| P0k | proposer_check_dropped |
| P0l | sha_comparison_skipped |
| P0m | trailer_check_disabled, first_proposer_only, exemption_unkeyed, exemption_party_unchecked, unknown_merge_author |
| P1 | seed_reissued, reuse_check_skipped, domain_check_skipped, training_undomained |
| P2 | network_enabled, judge_mounted, rootfs_writable, memory_limit_dropped |
| P3 | failures_dropped |
| P4 | self_reported, client_rusage, not_differenced, peak_from_current |
| P5 | next_sent_early |
| P6 | crafter_field_in_schema |
| P7 | clipped, missing_imputed, sum_unchecked |
| P9 | record_dropped, utility_altered, chain_update_skipped, opened_for_rewrite, genesis_empty, signature_unchecked |
| P10 | removal_skipped |
| P11 | set_order_restored, seed_ignored, hash_constant, field_dropped, chunks_replaced_after_worldgen, golden_hash_altered |
| P12 | peak_differenced, unmeasured_free |
| P13 | infinite_dropped, realised_row_only, entropy_missing_imputed |
| P14 | first_legal_action, floor_unsmoothed, seen_not_reset |
| P15 | abs_difference, shift_dropped, one_arm, budget_one_arm |
| P16 | unattributed_admitted, any_credential, registration_taken_over |
| P17 | fixed_proposer, seeds_before_proposer, idempotency_dropped, conflict_unchecked, hash_partial |
| P18 | cap_ignored, failures_dropped, throughput_from_episodes, proposer_from_config, mixed_proposers_admitted, infinite_pooled_finite, short_request_admitted |

Per-pin transcripts of each kill are under `reports/L1/p*/`. The full suite's transcript is `make-pins-25f36e6.txt`.

## Interface finding
Brief 2 §1 requires a zero diff on `judge/` and `worlds/spec/`. Binding NetHack as the code now stands needs two judge edits, neither of them NetHack's fault:
- `judge/evaluate.py:33` hard-codes `WORLDS = {"crafter": "worlds.crafter.binding"}`.
- Compute prices are per World in `judge/config.toml` (`[price.crafter]` only).

The minimal change is World discovery and pricing as data: a binding plus a manifest carrying its committed `price`. It is drafted as brief 2 A2's L2a, before the zero-diff baseline. It is not made here: brief 1 names no such change, and L1's hash would move.

## Obligations on L2
Source: 86 OBLIGATION lines on L2 in 42 of 44 L1 review files, plus 25 STATUS versions, deduplicated.
- 55 are open; listed below and carried into brief 2 A2.
- 10 are discharged by pins already in place: P0i ×2, P0m, P9 `genesis_empty`, P3/P7/P11 reply validation, P11 golden hash, P17 ×3, P18 tables.
- All four L0 obligations on L1 are discharged (P0k, P0l, P0m).

Source key: R = `review-<12hex>.md`, S = STATUS at that sha.

**Judge and ledger**
1. Tail truncation passes `verify`, because each signed head stands alone (R 2817eb747815 F2).
2. P9 `opened_for_rewrite` is killed by a parse error, not by a byte comparison (R 2817eb747815 F3).
3. Replay returns ledger lines unchecked against the signed head (R 6debf231b630 F2).
4. An interrupted request loses its played episodes (R 6debf231b630 F3).
5. The CLI episode guard is `str.isdigit`: `²` gives a traceback (R 6debf231b630 F4).
6. Judge-private storage checks the directory's mode only, not each file's (R 02a71436d9ff F3).
7. Nothing witnesses that seeds come from a CSPRNG (R 9d8e7336a6b9 F1).
8. Seed-store keys depend on CPython's tuple hash, and no version is recorded (R 9d8e7336a6b9 F2).
9. P5's clairvoyant searches only top-level step keys (R 5f2be905f98c F1).
10. The probability-sum tolerance is pinned only against gross violations (R c2a87f6478ad F3).
11. Missing predictions are unpriced in comparisons (R c2a87f6478ad F4).
12. P4 cannot tell init-process rusage from cgroup accounting (R 42d73311a233 F3).
13. The price floor `max(wall_s - unmeasured, 0)` is never exercised (R c6679c6aa83a F4).
14. Reliability bin edges: `int(q*bins)` disagrees with P13's float edges (R 7e18816c626e F2).
15. P10 has no clean case that records and counts `leaked` (R 2402ed7d56a5 F3).
16. An exception escaping `episodes.run()` skips teardown (S c8fdf97).
17. The sealed image must state which digest the records mean (R 6debf231b630 F5).
18. The released image carries `verify` (S 2817eb7).
19. NetHack needs its own committed price before any scored run (S c6679c6).

**Interface and Worlds**
20. P6's vocabulary is manifest-only: native keys and regex patterns pass (R 1247b4d888dd F2).
21. P11 does not assert that its streams reach a multi-candidate despawn (R 4d34943d5037 F3).
22. P2 passes on one runtime when the declared one is unusable (R be10563c5496 F2).
23. The Podman pause-process prestart lives in the Makefile, not in the harness (R be10563c5496 F3).
24. P2's probe paths are a hand list, not derived from the judge's paths (R be10563c5496 F4).
25. Stray-container detection is runtime-global (R 2402ed7d56a5 F4; R aa993f415150 F2).

**Harness**
26. The copy is deleted before the sweep (R 4649b6b2b4e0 F4).
27. `run_under_edits` neither sets the subreaper nor sweeps (R 4649b6b2b4e0 F5).
28. The `Overlap` assertion has no pin (S 359bebf).
29. The child environment is pinned only at `child_env`, not at the spawn sites (R 8e8b676bf197 F1).
30. SIGTERM to the orchestrator leaves scratch behind (R 7498b94a505b F2).
31. P0m errors, rather than failing, on a tree with no `.git` (R bb7b3875f8f6 F3).
32. The `PROPOSER_EXEMPTIONS` entry for bb7b387 is dead config (R 576fe9632eab F2).
33. P14 uses an asymptotic χ² p-value (R d3c24bf7133f F1).
34. P14 has low power against small departures (R d3c24bf7133f F2).

**Pilot and measurement**
35. The pilot can return a verdict with wall_s > cap_s, because the cap is checked only between requests (R 571ee563f91d F2).
36. The `pilot/__main__.py` paths are unpinned (R 571ee563f91d F3).
37. `pilot/` is not in `judge_sha256` (S 571ee56).
38. Time-to-learn reports expected mass, not assurance (R 0d5e9ecf3c6f F1).
39. m* carries no Monte Carlo standard error, and its search assumes monotonicity (R 0d5e9ecf3c6f F2).
40. P15 is pinned on a two-point fixture only (S a9de119).
41. The random incumbent's variance is a weak proxy: recheck with the first non-random candidate (S 571ee56).
42. The cpuset fact reads the user slice, not the measuring process's own cgroup (R 70d26b83818e F1, F2).
43. Nothing binds a measure artefact to the reviewed head (R 7498b94a505b F1).

**Process, git and CI** (44, 53, 54 and 55 touch entrenched paths and are Guy's)
44. P0m's real-branch check is skipped in CI's shallow clone (R bb7b3875f8f6 F2 and others).
45. `make pins` wall time is unbounded: 15–20 min, against the 10-min rule (S 9780803 and others).
46. The 7b checker ignores uncited CI claims beside a valid citation (R 05df03c6b88c F3).
47. The STATUS header sha is not bound to the branch (R cb09d10b7ae0 F3; R dd40393024fe F4).
48. STATUS claims carry no transcript path (R 8e8b676bf197 F2; R a814d28c7c1d F5).
49. The STATUS `forecasts:` line is not recomputed, and its base rate is a constant (R 7c4e9376d5b4 F4 and others).
50. Forecast-obligation checks are missing: host-verdict forecast, timing, duplicate ids (R dd40393024fe F3 and others).
51. `LAYER BOUNDARY` is chosen, not derived (R 705cc471f078 F3).
52. Proposer attribution is not checked against the git author (R 05df03c6b88c F4; R 45cdcea5128a F2; R 02a71436d9ff F5).
53. Defects in the `.claude` build and review commands (R dd40393024fe F2; R b35a68fb4e2a F2–F4; R d553dc5cb7fe F2 and repeats).
54. No workflow parse or stale-selection pins (R 7bed231de16d F1, F2).
55. Role separation by credential in `review.yml` and `.claude/settings.json` (R 7bed231de16d F4; R 7c4e9376d5b4 F3).

## Witness index
| Path | Content |
|---|---|
| `make-pins-25f36e6.txt` | `make pins` at this pull request's pinned head, including P0b's added mutant |
| `make-pins-cab0ca0.txt` | `make pins` at the pilot's code |
| `ci/*.json` | records of every cited `pins` run |
| `measure-37831165785/` | host facts, pins summary, records (gz plus sha256), pilot report |
| `review/571ee563f91d71938cef0ff52d76a849073adccb/host-witness.txt` | the Reviewer's recomputation of FIT |
| `p*/` | per-pin kill transcripts |
| `crafter-nondeterminism.txt` | A7's finding |

## Transcript: pilot verdict (host, measure 37831165785)
```
VERDICT: FIT
world crafter; runtime podman; image sha256:4ae7df19a747a8d7d8b7c697d9efc7f2ef4864737dd87d9ed6829931b9d7ebcb; judge_sha256 28710725463f36b93123771ddcda4390e3b02f4ee15488b42834809929eda7ff
episodes: 200 recorded of 200 requested (cap 7200 s); terminations {'terminal': 200}
throughput: 0.7197369313958408 episodes/s over 277.9 s wall-clock, 20 requests
  0.25 | 145 | 0.9059349999999999 | 402.92499571695015
  0.5 | 33 | 0.903826 | 91.70017143903003
  1.0 | 9 | 0.9183389999999999 | 25.009137665190007
```
