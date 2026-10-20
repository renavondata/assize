# reports/L2/status/l2a-o38-ttl-two-readings.md
# STATUS — L2 — 2026-10-19 — 32b92b3 — PR #260
VERDICT: SESSION DONE: L2a obligation 38 (time-to-learn reports expected mass, not assurance; review 0d5e9ec F1): the table carries the assurance reading beside the committed expected one; mutant `P15/expected_for_assurance` KILLED with a passing twin
LAYER BOUNDARY: no (per A1.3's definition: records no layer verdict; adds or opens no brief)
pins CI run 39298114059 on 32b92b3: success (reports/L2/ci/39298114059.json)
pins: clean 88/88; mutants 259/259 KILLED; twins 259/259; leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0 (CI run 39298114059, whole suite, skipped 0 pins and 0 mutants; log read from the run via `gh run view --log`)
changed: pilot/{timetolearn.py,run.py,README.md}, harness/{pins.py,edits/P15_expected_for_assurance.toml,edits/P15_abs_difference.toml,proposer.d/l2a-o38-ttl-two-readings.toml}, reports/L2/{forecasts/471a7224-….jsonl,ci/39298114059.json,status/l2a-o38-ttl-two-readings.md}
did: master session; seed `reports/switchback-seed.txt` absent; STATUS's `next` (review ef1e03c F4) was already merged in PR #252 (commit dd5e8a2), so the first open brief item, L2a obligation 38, was taken; no PR held it; declaration on PR #258
did: `timetolearn.masses`, `measure` (expected, committed), `assurance` (fraction of experiments whose mass reaches `mass`); `table` rows carry the assurance m*, fraction and wall-clock; `verdict(..., assured=True)` reads the other verdict; report.json/report.md show both; P15 checks the assurance column against the closed-form oracle 8 sigma^2 z^2 / delta^2 within the existing x1.5, and that the committed verdict never reads it
did: first push's CI run 39292875491 on ad6475f FAILED: `P15/abs_difference` STALE (my refactor moved the text its edit targets); retargeted it in 32b92b3, probe KILLED. The `pins_green` forecast on the first head is therefore false and stays as data. Obligation 39 (review 0d5e9ec F2, Monte Carlo error) not touched
did: process slips: two heredocs (a forecast-id hash computation and the commit messages) against instruction #110's spirit; every file change used Edit and Write. No tool call denied; the Edit of P15_abs_difference.toml failed once on my own bad parameter. Pull-request branch session after CI: no forecast row appended (rule 2)
decided (not asked): "90% posterior mass" kept as the expected reading for the verdict, assurance shown beside it, exactly as review 0d5e9ec F1 asked — p(stands on review)=0.8
decided (not asked): the assurance reading reuses `mass` (0.9) as its fraction, adding no config constant — p(stands on review)=0.7
forecasts: made 4 (pins_green #260 p=0.65, review_accept #260 p=0.6, host_verdict L2 FIT p=0.35, session_minutes run local bound 120 p=0.55); resolved none this session; pins_green resolves false (first run failed); cumulative log-loss not recomputed here
price: guy-items 0; guy-latency median 0.0h max 0.0h; sessions 0; runner-min 0
obligations added: L3: none
NEEDS YOU (at most 1): none
next: L2a obligation 39 (review 0d5e9ec F2: m* Monte Carlo standard error; mutant `first_crossing`)
