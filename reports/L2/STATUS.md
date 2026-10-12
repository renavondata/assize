# STATUS — L2 — 2026-10-12 — c3a1997 — PR #127
VERDICT: SESSION DONE: instruction #108 done (pins declare the paths they witness; a pins run skips pins unchanged since the last green head)
LAYER BOUNDARY: no (per A1.3's definition: records no layer verdict, adds or opens no brief)
pins: clean 47/47; mutants 122/122 KILLED; twins 122/122; leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0; skipped 0 since d8afa09 (run 38205487270) — pins CI run 38208656897 on c3a1997 (success, run attempt 1; record reports/L2/ci/38208656897.json). Full run because harness/ changed
changed: harness/pin.py, harness/runner.py, harness/__main__.py, harness/nested.py, harness/pins.py, harness/registries.py, harness/fixtures/{witness,toy,broken,daemon,escapee,noncausal,no_mutants}.py, harness/edits/P0w_*.toml, harness/README.md, harness/proposer.toml, Makefile, .github/workflows/pins.yml, reports/L2/forecasts.jsonl, reports/L2/STATUS.md, reports/L2/ci/38208656897.json
did: #108 items 1–2: `Pin.witnesses` (validate refuses empty, `no_witnesses`); all 47 pins declare theirs, with P0k/l/m/q/r/x/y as `("**",)`; `run --since <sha> --since-run <id>` runs only matched pins (all of them on harness/, Makefile, pyproject.toml, uv.lock); skipped pins are rows with verdict `skipped` and never count as ok
did: #108 items 3–5: `harness base` + pins.yml step (comment states the rule); `make pins` bare runs all. In CI the base step chose run 38205487270 on d8afa09. P0w cases (i)–(iv); `witness_ignored`, `harness_change_skips`, `skip_counted_ok`, `non_ancestor_base` KILLED locally and in CI
did: `claims next` skipped #102 (held by PR #123, since merged) and took #108. Merged origin/master (#123) after the PR opened DIRTY: forecasts keep both sides, master's first; P0aj given witness `.github/workflows/build.yml`
did: simulated on the real registry: a reports-only diff runs 7/47 pins (the `**` set). Local P0r first read `GITHUB_HEAD_REF` leaked from this session's trigger event (PR #123 branch); with it unset it passes. No tool call was denied
decided (not asked): `--since-run` and `--repo` added beside `--since`: item 2 requires recording the run id, and P0w's synthetic git fixture needs a repository other than the tree — p(stands on review)=0.75
decided (not asked): judge-side pins share one witness set (judge/, worlds/, incumbents/, pilot/, scripts/) rather than per-file sets; this over-runs rather than under-runs. P0b witnesses every code-file suffix it scans — p=0.75
decided (not asked): renames are split (`--no-renames`) so a path moved out of a witness still counts; skipped pins are one row per pin with role `skipped`, listing their mutants — p=0.8
decided (not asked): `base` prints nothing (so everything runs) when the API or an artifact cannot be read, and states why on stderr — p=0.8
forecasts: made 3 (a1f7c97bd66b pins_green p=0.6, 6521a8aca863 review_accept p=0.6, 1124746f7c93 host_verdict FIT p=0.35); resolved 0 this session; builder cumulative log-loss 53.43 over 126 resolved (`ledger proposer builder`)
price: guy-items 6; guy-latency median 1.3h max 2.1h; sessions 9; runner-min 484; wish-latency median 0.0h max 0.0h open 1 (`ledger price --since 487cde7`)
obligations added: L3: the escape rate in #108's price remark (pins red on a master full run after a green skip-run on the same PR) has no ledger subcommand yet
obligations added: L3: `harness base` lists every successful pins run (paginated) on each PR; nothing bounds it as the run count grows
NEEDS YOU (at most 1): approve and merge PR #127 (touches entrenched .github/)
next: reviewer round on PR #127; then #111 unless a PR holds it
