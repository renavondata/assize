# STATUS — L2 — 2026-10-17 — 98bea19 — PR #234
VERDICT: SESSION DONE: L2a obligation 33 (P14 uses an asymptotic χ² p value) discharged by P14's exact multinomial tail and mutant `asymptotic_p`
LAYER BOUNDARY: no (per A1.3's definition: records no layer verdict; adds or opens no brief)
pins: pins CI run 39049958506 on 98bea19: success (reports/L2/ci/39049958506.json); local make pins (reports/L2/builder/98bea191fc5382c91b647b07e56e17adf5b6684c/make-pins.txt): clean 83/83; mutants 232/232 KILLED; twins 232/232; leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0
changed: harness/pins.py, harness/README.md, harness/edits/P14_asymptotic_p.toml, harness/proposer.d/l2a-o33-exact-uniform.toml, reports/L2/{forecasts/7a9fa70c-….jsonl,ci/39049958506.json,builder/98bea19…/,status/l2a-o33-exact-uniform.md}
did: no open instruction issue; `claims next 33 34 35 36` gave 33 (30, 31 merged; 32 held by PR #232)
did: `_uniform_sf` counts exactly (Fraction) the draw sequences whose sum of squared counts reaches the observed one, cell by cell over (draws placed, sum of squares), pruning states whose every or no completion reaches it; replaces `_chi2_sf`
did: P14 checks it against enumeration on (6,0,0), (2,2,2), (1,1,0), (2,1,0) and requires UNIFORM_BOUNDARY (exact p 1.65e-6, χ² p 7.0e-7) not refused at α=1e-6; `asymptotic_p` fails on the boundary and three oracles (p14-asymptotic_p-mutant.txt, p14-clean.txt beside make-pins.txt)
did: make-pins transcript captured by shell redirection of `make pins`, P14 transcripts copied with `cp`; no file edited by shell; no tool call denied
decided (not asked): item is obligation 33, the first open brief item no PR holds; the chooser seed is absent, so the first candidate — p(stands on review)=0.9
decided (not asked): exact enumeration rather than Monte Carlo, since a Monte Carlo p is at least 1/(N+1) and cannot refuse at 1e-6 without ~10^6 draws — p=0.85
decided (not asked): obligation 34 (`one_action_dropped`, power) left to its own item; this diff does not change P14's power — p=0.85
chose: reports/switchback-seed.txt absent; first candidate taken (L2a obligation 33)
forecasts: made 4 (pins_green #234 p=0.7, review_accept #234 p=0.75, host_verdict L2 FIT p=0.35, session_minutes run 39049269192 bound 90 p=0.5); resolved 0
price: guy-items 1; guy-latency median 2.6h max 2.6h; sessions 6; runner-min 604
obligations added: L3: none
NEEDS YOU (at most 1): none
next: L2a obligation 34 (P14 has low power against small departures: mutant `one_action_dropped`), unless PR #232 or another holds it
