# STATUS — L2 — 2026-10-24 — 7ad324b — PR #332
VERDICT: SESSION DONE: first part of brief 2 §3's NetHack 3.6.6 World variant: pinned game image recipe and server, built and witnessed deterministic on the host; not yet bound
LAYER BOUNDARY: no (per A1.3's definition: records no layer verdict in the root REPORT.md; adds or opens no brief)
pins CI run 40064027492 on 7ad324b: success (reports/L2/ci/40064027492.json)
pins: the CI run succeeded; per-pin counts not read from its log by this session; local `make pins` not run (the diff adds no pin, mutant or judge code; it adds files under worlds/, which changes judge_sha256, and the CI run covers that)
changed: worlds/nethack366/README.md, worlds/nethack366/image/Containerfile, worlds/nethack366/image/server.py, reports/L2/build/nethack366-image/{README.md,probe.py}, harness/proposer.d/l2b-nethack366-image.toml, reports/L2/forecasts/0356d8d0-9994-4f28-9730-71c67be3c06d.jsonl, reports/L2/ci/40064027492.json, reports/L2/status/l2b-nethack366-image.md
did: candidates in order: #330 closed (PR #331 merged 04:35Z); #320 skipped (held by PR #322); took STATUS next, brief 2 §3 NetHack 3.6.6 variant (no open PR holds it; #325 holds the MiniHack ladder)
did: NLE v0.7.3 builds on the runner host in python:3.9-bullseye (pinned digest), commit da62293 with submodules, pip cmake 3.27.9, --no-build-isolation; this falsifies the "cannot build" premise of #328 and #329 for this recipe
did: NLE v0.7.3 has no fix_moon_phase; the image's entrypoint is faketime -f <instant>; witness: 6 episodes to the game's end, 2/2 repeats identical, 3 instants give 3 hashes (reports/L2/build/nethack366-image/README.md)
did: no pin or mutant added and none claimed; the binding, manifest, pins (determinism goldens, frozen clock, P2 non-pooling) and the image in CI are the next items
decided (not asked): the game runs out of process in a container (two nle versions cannot share the judge's interpreter; 3.6.6's C does not build on a current glibc) — p(stands on review)=0.8
decided (not asked): the clock is frozen by libfaketime at a caller-named instant, NLE unpatched, rather than sed-patching NetHack's clock — p(stands on review)=0.7
decided (not asked): deliver the image and its witness as one PR before the binding, the smallest group that stands alone and is witnessed — p(stands on review)=0.75
forecasts: made 4 (pins_green, review_accept on #332; host_verdict L2 FIT 0.35; session_minutes 120); resolved 0; cumulative log-loss not recomputed here
price: guy-items 0; sessions 1; runner-min not measured by this session (`ledger price` not run)
obligations added: L2b: pins need the 3.6.6 image where pins run (build in CI or a pinned registry digest); a recipe whose apt packages are unsnapshotted is not bit-reproducible
NEEDS YOU (at most 1): none
next: brief 2 §3: worlds/nethack366/binding.py and manifest.json over this image, with the determinism, frozen-clock and non-pooling (P2) pins
