# L2 report — brief 2 (NetHack)

## L2a — the judge carry-over is complete; the baseline is this pull request's merge commit

VERDICT (L2a, a layer-internal milestone, not a layer verdict; the root `REPORT.md` is not touched): **L2a COMPLETE.** A2's first criterion holds for L1 obligations 1–43: 43 of 43 are discharged by a pin whose named mutant is KILLED with a passing twin (obligation 41 in part; its remainder is A2's own fourth criterion, below). Obligations 44–55 are disposed of in `reports/L2/obligations-44-55.md` (Wish #179), and A4's 15 items in `reports/L2/a4-dispositions.md`. Brief 2 A2 makes this merge Guy's ("The L2a merge is a layer-internal milestone that Guy merges, because it changes the court"); auto-merge is not enabled.

### The baseline (brief 2 A1 item 4, as A2 amends it)
- The zero-diff baseline of brief 2's zero-diff pin (§Pins "P1 Zero diff"; unbuilt, see below) is **the merge commit of this pull request on `master`**. Its `judge/` and `worlds/spec/` are those of this branch's head, which a reader checks with `git rev-parse <merge>:judge <merge>:worlds/spec` against the two tree ids in this branch's STATUS.
- From that commit on, A2's refusal list holds: "No change to `judge/` or `worlds/spec/` after the L2a baseline."
- `judge_sha256` (`judge.evaluate.judge_hash`) at this branch's head: `036e92348149879095b121e9d5e4c00826747bbff4c8f571b4674883018ee19c`. At master 8190d4f, before this branch's one judge edit, it was `c005ecfa7ad7471e31223d15bbe9be9a076c7ed97abb87e24c3c59c525e7864e`; at L1 (`reports/L1/REPORT.md`) it was `28710725463f36b93123771ddcda4390e3b02f4ee15488b42834809929eda7ff`.
- A2's stop boundary "the Crafter judge hash changes in a way the L2a diff does not explain" is not met: `git log 4204e2e..8190d4f -- judge worlds/spec` (4204e2e is L1's merge, PR #32) lists 22 commits, every one an L2a item (A2 item 1, L1 obligations 1, 3–6, 8, 10–12, 14, 16–19, 22, 25, audit 8aae43c finding 5) or its merge; this branch adds the docstring edit below.

### The one judge edit of this branch
`judge/price.py:7` named a World ("δ = 2 for NetHack"). A2's refusal list: "No NetHack code, manifest or name under `judge/` or `worlds/spec/`, ever." The docstring now reads "δ = 2 progression points"; nothing else under `judge/` or `worlds/spec/` changes. After the edit, `grep -rniE 'nethack|autoascend|\bnle\b' judge worlds/spec` prints nothing (transcript in this branch's STATUS).

No pin holds the refusal yet (review of 9fe22d0, F1). Brief 2's zero-diff pin (§Pins "P1 Zero diff", A1 item 4, A2 Scope 2) is unbuilt at this baseline: the registry has no check comparing `judge/` or `worlds/spec/` with a baseline, its `P1` is the CSPRNG pin (row 7 below), and this branch's own edit under `judge/` passed `pins` (run 39566415270). Building that pin, under a registry id other than P1, is L2b's first item, since A2 Scope 2 puts L2b "under the zero-diff pin against the L2a baseline". Until it exists, nothing mechanical holds "No change to `judge/` or `worlds/spec/` after the L2a baseline"; only review does.

### A2's first criterion, obligations 1–43 of `reports/L1/REPORT.md`
Witness for every row: `pins` CI run 39545345182 on 8c317a2, attempt 1 (clean 92/92, killed 295 of 295, twins_ok 295 of 295, leaked 0, survived 0, skipped 0, exit 0). `git diff 8c317a2 8190d4f` is empty, so its registry is master's. Every mutant named below is KILLED with its twin `ok` in that run: `reports/L2/build/l2a-baseline-report/ci-39545345182-cited-mutants.txt` (64 rows read from the run's `pins-report` artifact). PR is the merged pull request that first carried the mutant's `harness/edits/` file to master (`git log --diff-filter=A`, then the first first-parent merge containing that commit), except row 2, whose PR is the one that changed P9's check.

| # | Obligation (short) | Pin and mutant(s) | PR |
|---|---|---|---|
| 1 | Tail truncation passes `verify` | P9 `independent_heads` | #42 |
| 2 | P9 `opened_for_rewrite` killed by a parse error | P9 `opened_for_rewrite`, now killed by P9's byte comparison before any parse (the edit dates from L1, #22) | #60 |
| 3 | Replay unchecked against the signed head | P22 `replay_unchecked` | #166 |
| 4 | An interrupted request loses its played episodes | P23 `closing_unattributed` | #169 |
| 5 | CLI episode guard is `str.isdigit` | P24 `isdigit_guard` | #171 |
| 6 | Private storage checks the directory's mode only | P25 `entries_unchecked`, `verify_unchecked`, `heads_world_readable` | #191 |
| 7 | Nothing witnesses a CSPRNG | P1 `csprng_replaced` | #192 |
| 8 | Seed keys depend on CPython's tuple hash | P26 `key_version_ignored` | #195 |
| 9 | P5's clairvoyant searches top-level keys only | P5 `next_in_begin`, `next_in_notice`, `next_in_observation` | #196 |
| 10 | Sum tolerance pinned only against gross violations | P27 `tolerance_loose`, `tolerance_zero` | #197 |
| 11 | Missing predictions unpriced in comparisons | P28 `scored_only` | #198 |
| 12 | P4 cannot tell init rusage from cgroup accounting | P4 `init_process_rusage` | #199 |
| 13 | The price floor is never exercised | P12 `floor_dropped` | #200 |
| 14 | Bin edges disagree with P13's | P13 `bin_exact_rational`, `bin_product_rounded` | #201 |
| 15 | P10 has no clean case recording `leaked` | P10 `leaked_not_recorded` | #202 |
| 16 | An escaping exception skips teardown | P29 `escape_untorn`, `close_untorn` | #204 |
| 17 | The image must state which digest records mean | P30 `image_id_unchecked` | #206 |
| 18 | The released image carries `verify` | P31 `verify_omitted`, `eager_imports` | #207 |
| 19 | NetHack needs its own committed price | P20 `crafter_price_fallback`, P33 `rates_underived`, `schema_delta_optional` | #35, #223 |
| 20 | P6's vocabulary is manifest-only | P6 `native_key_in_schema`, `pattern_hides_vocabulary` | #205 |
| 21 | P11 does not reach a multi-candidate despawn | P11 `stream_truncated` | #225 |
| 22 | P2 passes when the declared runtime is unusable | P32 `declared_runtime_ignored`, `declaration_env_ignored` | #213 |
| 23 | Pause-process prestart lives in the Makefile | P0bb `pause_not_prestarted` | #218 |
| 24 | P2's probe paths are a hand list | P2 `private_storage_mounted` | #222 |
| 25 | Stray-container detection is runtime-global | P10 `stray_scope_global` | #224 |
| 26 | The copy is deleted before the sweep | P0h `copy_deleted_before_sweep` | #226 |
| 27 | `run_under_edits` sets no subreaper, no sweep | P0bc `outer_subreaper_not_set`, `outer_sweep_removed` | #227 |
| 28 | The `Overlap` assertion has no pin | P0bd `overlap_unchecked` | #228 |
| 29 | Child env pinned only at `child_env` | P0be `spawn_env_inherited`, `nested_env_inherited`, `under_edits_env_inherited` | #229 |
| 30 | SIGTERM leaves scratch behind | P0bf `sigterm_unhandled` | #230 |
| 31 | P0m errors on a tree with no `.git` | P0bg `base_unguarded` | #231 |
| 32 | Dead `PROPOSER_EXEMPTIONS` entry | P0m `stale_exemption_accepted` | #232 |
| 33 | P14 uses an asymptotic χ² p-value | P14 `asymptotic_p` | #246 |
| 34 | P14 has low power against small departures | P14 `one_action_dropped`, `top_up_dropped` | #248, #255 |
| 35 | The pilot cap is checked only between requests | P18 `cap_overrun_admitted` | #236 |
| 36 | `pilot/__main__.py` paths unpinned | P34 `registration_unbound`, `ledger_findings_ignored` | #251 |
| 37 | `pilot/` not in `judge_sha256` | P34 `pilot_hash_config_omitted`, `pilot_hash_is_judge_hash` | #258 |
| 38 | Time-to-learn reports expected mass, not assurance | P15 `expected_for_assurance` | #260 |
| 39 | m* has no Monte Carlo error; search assumes monotonicity | P15 `first_crossing` | #261 |
| 40 | P15 pinned on a two-point fixture only | P15 `weights_equal` | #262 |
| 41 | Random variance is a weak proxy | in part: P18 `proxy_note_dropped` (the note is stated); the recheck is A2's fourth criterion | #263 |
| 42 | The cpuset fact reads the user slice | P0j `unpinned_slice_accepted`, `own_cgroup_unchecked` | #264 |
| 43 | Nothing binds a measure artefact to the head | P0j `head_unrecorded`, P0bl `head_unchecked`, `two_heads_accepted` | #265 |

Counts over the 43: discharged 42; discharged in part 1 (41). Its remainder is not dropped. A2's fourth criterion carries it word for word: "Brief 2's time-to-learn verdict is rechecked against the first non-random candidate's variance once one exists. Until then the random incumbent's variance is reported as a weak proxy and is not used." It is also recorded as an L3 obligation in `reports/L2/status/l2a-o41-proxy-note-pinned.md`. Rows 17 and 18 hold the mechanism. The digest itself is L2c's deliverable (A2 §Scope 3). Row 19 holds the mechanism, which refuses an unpriced or underived World. NetHack's own `price` block is L2b's, in `worlds/nethack/`, outside `judge/`.

### A2's stop boundaries at this baseline
- "any judge-touching obligation turns out to need NetHack-specific knowledge": none did. The one NetHack word under `judge/` was a docstring example, removed above.
- "the Crafter judge hash changes in a way the L2a diff does not explain": not met (§The baseline).
- "re-running the L1 pins after L2a gives anything other than all clean and all KILLED": the registry, L1's pins among it, is all clean and all KILLED in run 39545345182. This branch's own `pins` run re-witnesses it on the head (STATUS).

### What remains of brief 2
L2b (first the zero-diff pin against this baseline, then §§2–4, NetHack, under it) and L2c (the seal). Open pull requests at this writing: #257 (audit 8aae43c finding 1, `harness/` only, no path under `judge/` or `worlds/spec/`), #287 and #290 (instructions #281 and #286, `awaits-guy`). None touches the baseline's trees.

## L2b — the zero-diff pin (appended; corrects nothing above, supersedes "unbuilt" from this pull request's merge)
- The baseline is `bcc9ac6662495d4c0d7bce823482adafe9836f19`, PR #293's merge commit on master. `git rev-parse bcc9ac6:judge bcc9ac6:worlds/spec` gives `113d9ffd7520f65f57448bf98f617e6d40661a35` and `079b2084d7d7b6739cf961a189e951567e7a4dbe`, recorded in `harness/baseline.toml`.
- Brief 2's "P1 Zero diff" is registry pin **P35** (registry P1 stays the CSPRNG pin, review 9fe22d0 F4). It holds A2's refusal "No change to `judge/` or `worlds/spec/` after the L2a baseline" mechanically: both trees must hash to the recorded ids, and the ids must be those of the baseline commit, which must be in the branch's history. Mutants `judge_edited`, `spec_edited`, `baseline_rewritten`; their kills are witnessed in this pull request's STATUS.
- A2's criterion "P1 (zero diff) holds from the L2a baseline to the L2b head" is read from P35 on every pins run from this merge on.

### L2b correction (appended; review f84ed6f F1)
- The paragraph above says the ids "must be those of the baseline commit, which must be in the branch's history". That bound only to HEAD's history, which a branch can move along with a judge edit (witness: reports/L2/review/f84ed6f7043a32086ee8b84a040dee764b1cd3fe/probe-moved-baseline.txt). From this head P35 also requires the baseline commit to be in `origin/master`'s history (`baseline_moved`; an unreadable master is `base_unreadable`), and its fourth mutant `baseline_moved` is killed by a fixture history in which a commit is in HEAD's history but not master's.

### L2b second correction (appended; review 89c757f F1)
- The correction above still let any commit of master's history stand as the baseline, so a branch could rewind `judge/` to an older master commit and record that commit (witness: reports/L2/review/89c757f7e9fb10df6bc972b99c3d015816c8b195/probe-older-master-baseline.txt). From this head P35 also requires master itself to carry every recorded tree id (`git rev-parse origin/master:<directory>`; a difference is `baseline_rewound`), so the trees a branch is compared with are master's as it stands, and its fifth mutant `baseline_rewound` is killed by a fixture history whose master changed `judge/` after the recorded commit. Under that binding the two L2b sentences above, that P35 holds A2's refusal "No change to `judge/` or `worlds/spec/` after the L2a baseline" and A2's criterion "P1 (zero diff) holds from the L2a baseline to the L2b head", read as: the branch's trees equal master's, and master's equal those of a commit of master's history that the record names, `bcc9ac6` today. That master has not moved them since `bcc9ac6` is witnessed by the trees themselves: `harness/baseline.toml` records `bcc9ac6`'s ids, and P35 refuses any master that differs.

## L2c — the seal (brief 2 A2 Scope 3, A3 item 2): digest composed and pinned; CODEOWNERS entry and host verdict outstanding

VERDICT (L2c, a layer-internal milestone, not a layer verdict; the root `REPORT.md` is not touched): **NOT YET SEALED.** The image is composed and its digest recorded below, held by P21. Two of A3 item 2's parts are outstanding: `judge/` and `worlds/spec/` entering CODEOWNERS (blocked, below), and the Crafter host verdict under this image (a `measure` run).

- Seal digest: `sha256:c7856fe2cc22222a9c1af4bde31272acd4e4ae4f60bae605c975e75ed918259c`
- Image ID (config digest): `sha256:263af24fa713379111cadbc0d206742953d578b1d066f18f745acd3e0529108d`
- Built from: `judge/` of the L2a baseline bcc9ac6 (PR #293's merge; tree `113d9ffd7520f65f57448bf98f617e6d40661a35`, the same tree at master 8e49986), over the base `docker.io/library/python@sha256:0dd364ba7e10242f07755449e3a3d0e35f9efd987952737b90def6709ab0c5ce` (base image ID `sha256:541096ae9b05d3b850341b78790e2ed31e94d5aa0ea086933c6ff0c09ffa2e63`).
- Recipe: `python -m harness.seal OUT` writes the image as an OCI layout and prints both digests. The image is composed from bytes, not built (`harness/seal.py`): one uncompressed ustar layer of `judge/` with fixed owner, modes and mtime, a canonical-JSON config and manifest. Its digest is a function of the tree and the pinned base alone, so no runtime or compressor version enters it, and anyone holding the baseline re-derives it.

### Released
Content-addressed: the digest above is re-derived offline by P21 from the tree on every `pins` run. The image is not yet pushed to a registry. A push must keep the layers uncompressed so the manifest digest stays the same (`skopeo copy oci:OUT docker://<registry>/<name>`). The push credential is Guy's.

### Outstanding
- CODEOWNERS (A3 item 2, A4 item 8, CLAUDE.md A1.1). P0bm holds `harness/trusted_base.toml` equal to the CODEOWNERS lines, and it admits a line only under an `Audit findings at <sha>` heading in a brief (`harness/trusted.py:29`, `ADMISSION`). No such heading admits `/judge/ @gfrmin` or `/worlds/spec/ @gfrmin`, and Amendment 2's audit criterion 7 says the trusted base "has not grown since the last audit". The lines are therefore not added here. They go in on the same pull request as the seal, once an audit-dated amendment admits them.
- The Crafter host verdict under the sealed image: a `measure` run at this pull request's head. The `judge/` bytes the run measures are the image's, because the digest is a function of those bytes and P21 re-derives it at the same head.

### Addendum: where P21 reads the recorded digest
Harness copies carry no `reports/`, so P21's mutants cannot edit this file (CI run 39710710128: P21 clean ok, its three mutants STALE). The digest is therefore also committed in `release/seal.toml`, and P21 checks both: the composed digest against `release/seal.toml`, and this report against `release/seal.toml` at the invocation tree, with a fixture-tested rule (mutant `report_unchecked`). In that same run, P21's clean case passed on GitHub's `ubuntu-latest` runner, which has a different podman, so the digest above was re-derived on a second host.
