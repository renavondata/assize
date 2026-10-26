# Review of PR #358 at 5014f8b32b35115d34a0d879c1222705eb228777 — transcript

Reviewer session 7365d558-7625-438f-ad30-776579b0fbd2 (claude-fable-5-1), review run 40265730602 on runner thinkpad-agent (job start 2026-10-26T03:46:42Z; declaration 03:48:00Z, expected 120 minutes). Acting as assize-reviewer. Every file here was written with the Write tool except the verbatim copies of run outputs (`measure-40261491867-*.log`, `make-pins-5014f8b.txt`, `probe-p0bm.py`, `probe-p0bm.out`), copied with `cp`. No tool call was denied.

## 1. Context

- PR #358 `instr-356-measure-pilot` → master, author assize-builder, labels `needs-review`, MERGEABLE (`mergeStateStatus` BLOCKED = review pending). Base 23029f6; origin/master 6f970e9 adds only the PR #352 review files and resolutions (PR #357). No `build` run live on the branch (the one build run, 40260310790, was the master session that opened this pull request, 02:41:09Z–03:46:59Z on steel-agent).
- Builder of record: `harness/proposer.d/instr-356-measure-pilot.toml` = builder claude-opus-5-5 session 4488d198-a345-48d5-9560-3483e9e23f8d; not this session.
- Layer at head: L2 (last verdict line in REPORT.md is L1). Brief: docs/briefs/brief-2-nethack.md with amendments A1–A5, the audit findings, the wish amendments, `Admitted by instruction #315`, the Wish #341 section, `Admitted by instruction #342`, and this pull request's `Admitted by instruction #356`.
- Commits: a21c2f5 (items 1–3, proposer row, forecasts), 84f535d (trusted-base entry and brief heading), 5014f8b (STATUS, CI record, host witnesses). Each carries `Instruction: #356`, `Proposer: guy`, `Proposer: builder claude-opus-5-5 4488d198-…`, authored by assize-builder.
- Instruction #356: signed (signature-356.txt). Gfrmin's last body edit (02:40:50Z, appending `Price: runner-min; up; 120`) precedes the `labeled instruction` event (02:41:04Z), which is the last label event; no edit after it. The `/review` context command for the open-forecast count crashed on the two id-less L0 rows (known; the resolver's own count is used: 101 open, 95 typed in L2).
- `gfrmin` closed #342 at 02:44:39Z ("Items 1–3 merged (#350, #352); 3b/3d carried by #356"), three minutes after the Builder declared on #356 (02:42:05Z) while #342 was still open; the Builder's `decided (not asked): skipped #342` is thereby ratified.

## 2. The diff against the signed text

`git diff origin/master...5014f8b`: 12 files, 290 insertions, 1 deletion.

- `.github/workflows/measure.yml` (+7 −1): `permissions:` gains `issues: read`, `pull-requests: read`, `actions: read` and keeps `contents: read` (item 1); the `make measure` step gains `env: GH_TOKEN: ${{ github.token }}` (item 2); `timeout-minutes: 45` → `120` (item 3). No other change under `.github/`. Criterion "The diff under `.github/` is exactly items 1–3, to `measure.yml` alone": met.
- `harness/trusted_base.toml` (+1): `"measure.yml github.token" = "Admitted by instruction #356"`, and `docs/briefs/brief-2-nethack.md` (+4): the heading `## Admitted by instruction #356` listing that token. Not named by #356. See §4 for the probe and the review file F1 for the reading: item 2 binds `github.token` in a workflow, which grows the token kind of the declared trusted base (`harness/trusted.py` `_tokens`), and the law admits that growth only by this heading and entry (instruction #315 items 1–3, "with the same strength as an audit heading").
- `harness/proposer.d/instr-356-measure-pilot.toml`, `reports/L2/forecasts/4488d198-….jsonl`, `reports/L2/status/instr-356-measure-pilot.md`: the session's own files.
- `reports/L2/ci/40261479796.json`, `reports/L2/seal/measure-40261491867-{facts.txt,excerpt.txt,P0h-clean.log,P0bf-clean.log,P0h-litter-stdout.log}`: witnesses of the STATUS's claims (the standing rule "No unwitnessed claims"); each compared with the run's own artifact in §3.
- Item 4 (apply `measure`, record #342 3b and 3d): not done; the host run failed in `make pins` before the pilot (§3). The root `REPORT.md` and `reports/L2/REPORT.md` are unchanged. STATUS `VERDICT: STOPPED`, one NEEDS YOU, `LAYER BOUNDARY: no` (A1.3's definition: no verdict line, no brief opened).

## 3. The host run and its artifact

Run 40261491867: `measure`, `workflow_dispatch` by assize-builder on `instr-356-measure-pilot` (not the `measure` label; the Builder's recorded reason is review 5c3ccac F4c: a `labeled` run checks out GitHub's merge ref, which `claims.measure_head_findings` refuses), head 84f535d, created 02:55:28Z, concluded failure 03:41:53Z (46 minutes; no timeout under the new 120-minute limit). Artifact `measure-host` 12626062083 fetched by the API zip route into a fresh directory.

- facts.txt: `head` 84f535d7c70bbb818aae139d875b9c334d6ea0a2, `host-id` da4749c0…, `uname` steel-legend, 12 CPUs (cpuset 3-5,9-11), `whoami` assize-runner, podman 6.1.2 rootless; identical to the pull request's `measure-40261491867-facts.txt`. `claims measure-head facts.txt 84f535d…`: 0 findings; against 5014f8b: `head_differs` (the reviewed head adds reports/ only).
- pins/pins.jsonl summary: clean 101/103 (P0h, P0bf FAILED), mutants 347/347 KILLED, twins 347/347 ok, leaked 0, stale 0, inconclusive 0, non-causal 0, exit 1 (measure-40261491867-rows.txt). P0m, P0r, P0x, P0ac and P0bm: clean ok, exit 0 — the four pins the instruction names pass on the host, for the first time since P0r, P0x and P0ac entered the registry (review 5c3ccac F4). P0m's transcript (measure-40261491867-P0m-clean.log) and P0bm's (measure-40261491867-P0bm-clean.log) copied.
- P0h clean: FAILED in 12.8 s; the nested `fixture.litter` run's `copy_tree` raised `shutil.Error` with `[Errno 28] No space left on device` on every entry under `/tmp/assize-scratch-wyaah79s/…` (P0h-litter-stdout.log, identical to the artifact's `pins/runs/P0h/clean/nested/litter/stdout.log`); the three earlier nested runs (leaks, escapee, daemon) had passed. P0bf clean: FAILED, `observed: timeout` at 120.1 s (`child_timeout_s = 120`), transcript ends after its six header lines. Both in the clean phase (02:55:39Z–03:02:00Z).
- The same pins' twins passed in the mutant phase of the same run: P0h's six twins (15.6–15.7 s each) and P0bf's one (6.1 s), 03:02Z–03:41Z (measure-40261491867-P0h-sweep_skipped-twin.log, measure-40261491867-P0bf-sigterm_unhandled-twin.log). The same pins pass in CI 40261479796 on the same code and in this session's reproduction (§6). The diff touches no file these pins run. The failure is the host's, and transient.
- Why the host: builder-log-excerpt.txt. The build runner (steel-agent) and the measure runner share steel-legend and its 16 GiB tmpfs `/tmp`; two minutes after the run, 8.0 GiB of it was held by `/tmp/claude-1000` (3.2 GiB) and scratch roots of earlier review and build sessions. The pins' own copies are 41 MiB each (`copy_tree` excludes `.git`, `.venv`, `out`, `reports`; `workers = 1`). Nothing in the run records free space before `make pins`.

## 4. Probe: is the trusted-base admission necessary at this head?

probe-p0bm.py on a `git archive` copy of 5014f8b (pure functions of `harness.trusted`; nothing edited), output probe-p0bm.out:

- as committed (entry + heading): PASS
- entry removed from trusted_base.toml: FAIL `['unlisted token measure.yml github.token']`
- heading removed from the brief, entry kept: FAIL `["unadmitted token measure.yml github.token: 'Admitted by instruction #356'"]`
- both removed, i.e. master's list against this head's `.github/` (what `pins-master` composes): FAIL `['unlisted token measure.yml github.token']`

So item 2 cannot be done with `make pins` clean (which #356's second criterion requires of the host run) unless the token is admitted, and the only admission the law provides for an instruction is this heading and entry (instruction #315).

## 5. CI

ci-runs.txt. Head 84f535d: `pins` 40261479796 success (whole suite, 103/103, 347/347), equal to the STATUS and to reports/L2/ci/40261479796.json. Reviewed head 5014f8b: `pins` 40265720219 success (`--since 84f535d`: 14 clean, 63 KILLED, 89/284 skipped). `pins-master` 40265730866 on 5014f8b: see §8. Forecast rule 2 holds (rows in a21c2f5, before the first run); the four ids verify. `claims status-check` on the STATUS: 0 findings.

## 6. Reproduction

`gh repo clone renavondata/assize /tmp/rv358.XXXX`, checkout 5014f8b (origin = GitHub), `make pins` started 03:52:37Z on thinkpad-agent (8 cores, load 0.5 at start, /tmp tmpfs 7.7 GiB with 5.8 GiB free). Clean phase: 103/103 PASS by 04:01Z. Mutant phase 04:01Z–04:56Z (the harness-side pins at about 10 a minute, the judge-side container mutants at 2–3 a minute). Ended 04:56:53Z, 64 minutes in all. Tally (make-pins-5014f8b.txt): `clean: 103/103 passed, 0/103 failed`; `mutants: 347/347 killed, 0/347 survived, 0/347 inconclusive, 0/347 stale, 0/347 non-causal, 0 leaked (clean and mutant)`; `PINS PASSED`; exit 0. Equal to CI 40261479796 on the same code. P0h and P0bf passed clean here, as their twins did on the host. No flake.

## 7. Resolver

resolve-40265730602.txt: 5 rows (2 of this pull request's forecasts, 3 re-resolutions of ids master closed in PR #357, same outcomes). Empty L0/L1 files removed. Nothing resolved by hand. `f850ab2127c8` (review_accept #358) resolves on this review's verdict by the next resolver; `c4102796bda3` (host_verdict L2 FIT) stays open until a host verdict exists.

## 8. End of session

- `pins-master` 40265730866 on 5014f8b (03:47:32Z–04:42:15Z): failure. Summary: clean 102/103 (P0bm FAILED: `['unlisted token measure.yml github.token']`), mutants 341/347 KILLED, 6 NON-CAUSAL (P0bm's), twins 341/347. By construction (it restores master's `harness/`, so master's `trusted_base.toml`, over the head's `.github/`): review file F3, probe case 4. Witness: pins-master-40265730866-P0bm-clean.log.
- This file and the review file are committed before the push, so the post-push `pins` run on the new head and the labels set are cited in the approval body and the pull request's labels, not here. Verdict ACCEPT WITH OBLIGATIONS on an entrenched-path pull request: approve (not a layer boundary, not my pull request), `needs-review` → `awaits-guy`, reviewer gfrmin requested, `NEEDS GUY: approve and merge`.
- Cleanup at the session's end: the reproduction clone `/tmp/rv358.IjNt`, the artifact directories `/tmp/rv358-art.*`, `/tmp/rv358-ci.*`, `/tmp/rv358-ci2.*`, `/tmp/rv358-build.*`, `/tmp/rv358-pm.*`, the probe copy `/tmp/rv358-probe.*` and `/tmp/rv358-probe-scripts`, and the `/tmp/rv358-*.txt|log` notes are removed; `pgrep -fa 'harness run'` and `ls /tmp | grep rv358` are run afterwards to show nothing of this session's remains. The `assize-*` directories under /tmp that predate this session (2026-10-17 to 2026-10-25, earlier sessions' leftovers of the kind F2 names) are left as found.
