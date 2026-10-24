# The NetHack 3.6.6 game image (brief 2 section 3, Version mismatch) — build and determinism record

VERDICT: NLE v0.7.3 (NetHack 3.6.6) builds on the agent runner host from `worlds/nethack366/image/Containerfile` and
plays deterministically given its two seeds and a frozen clock. Denominator: 6 episodes, 2 seed pairs, 3 frozen
instants, each played to the game's own end. All 6 ended with `done` and exit 0. Repeats agree: 2 of 2 pairs give
identical hashes. Different frozen instants give different hashes (3 instants, 3 hashes), so the clock is causal and
must be frozen. This falsifies the "cannot be built here" premise of issues #328 and #329 *for this recipe*. Those
issues tried the PyPI sdist on a current toolchain, and on python:3.8 images without the submodules.

This record adds no pin and no mutant, and it claims none. The image is not yet pinned to a World: there is no binding
or manifest (`worlds/nethack366/README.md`, *Not yet here*).

## Inputs
- `Containerfile` SHA-256 `3193fedcc80199fd5650647105f10649975bec2366ac7dd5cd89093a60f8cade`; `server.py` SHA-256
  `a56a38d601ec4b93cdcf3cfc1af3afc11c3817dad9a01b3058ff746b441a9445`.
- Base: `docker.io/library/python:3.9-bullseye@sha256:5bd3c295ffab8b738108c7705052086d78b036078d5605dfc51e328ab758cc07`.
- NLE: https://github.com/facebookresearch/nle tag `v0.7.3`, commit `da62293014df5661a75811de931d117424617dbd`;
  submodules deboost.context `325fed7ee8b7`, libtmt `1da7ba96c459`, pybind11 `8de7772cc72d` (v2.6.2). The commit is
  the one AutoAscend's `Dockerfile` checks out (`git checkout v0.7.3`). AutoAscend's Dockerfile also seds the seed
  lock out of `tasks.py` and adds `NLE_ALLOW_SEEDING`. Neither is needed here: v0.7.3's CMake enables seeding by
  default (`USE_SEEDING` ON), and `server.py` lifts the instance lock at run time. NLE is not patched.

## Build (host: the agent runner, rootless podman 6.1.4, 2026-10-24)

    podman build -q -t assize-nethack366:probe worlds/nethack366/image

exit 0; image ID `92bef5ddd753fe9ac01b1e1af26b841bffb90f2d76771d296e2d8a9a3d0a2a55`, 1093513220 bytes. The ID is not
claimed reproducible: apt's `flex`, `bison` and `faketime` come from the live bullseye mirror and are not snapshotted.
The versions it resolved are recorded below.

Failed steps on the way, each answered in the recipe:
1. The bullseye `cmake` package fails to install: `libarchive13_3.4.3-2+deb11u5` returns 404 from deb.debian.org's
   security pool. Answer: cmake 3.27.9 from PyPI. cmake 4 refuses deboost.context's `cmake_minimum_required`, which
   is the first error in #328.
2. Building NLE in pip's isolated build environment cannot see that cmake (`ModuleNotFoundError: No module named
   'cmake'`). Answer: `--no-build-isolation`.
3. gym 0.19.0's metadata is refused by wheel 0.43 (`packaging` `ParserSyntaxError` on a requirement marker). Answer:
   setuptools 57.5.0 and wheel 0.37.1, pinned first, and gym built against them.

Contents, read inside the image (`--network=none --read-only`):

    gcc (Debian 10.2.1-6) 10.2.1 20210110
    ldd (Debian GLIBC 2.31-13+deb11u13) 2.31
    Python 3.9.23
    uid=65534(nobody) gid=65534(nogroup) groups=65534(nogroup)
    bison	2:3.7.5+dfsg-1
    faketime	0.9.8-9
    flex	2.6.4-8
    cloudpickle==1.6.0
    cmake==3.27.9
    gym==0.19.0
    nle @ file:///nle
    numpy==1.21.2
    pybind11==2.6.2
    NetHack Version 3.6.6        (the banner compiled into the libnethack.so nle loads)
    0.7.3+da62293 0.19.0 1.21.2 Fri Jan  1 12:00:00 2021   (nle, gym, numpy, time.ctime() under faketime -f "2021-01-01 12:00:00")

## Determinism witness
`probe.py` (beside this file) starts a fresh container per episode (`podman run --rm -i --network=none --read-only`),
sends the seed pair, plays actions drawn from `random.Random("<core>:<disp>:actions")` over NetHackChallenge's 113
keys until the game ends, and hashes every line the server wrote. Command, run 6 times with the arguments shown:

    python3 reports/L2/build/nethack366-image/probe.py assize-nethack366:probe <core> <disp> "<instant>" 1000000

Output:

    {"core": 11, "disp": 22, "clock": "2021-01-01 12:00:00", "steps": 16478, "done": true, "end_status": 1, "sha256": "92f6d89100583841eba7a8f8f43db27bfe8f395f2399b174f479a5202e293ca4", "first_message": "You are lucky!  Full moon tonight.", "exit": 0}
    {"core": 11, "disp": 22, "clock": "2021-01-01 12:00:00", "steps": 16478, "done": true, "end_status": 1, "sha256": "92f6d89100583841eba7a8f8f43db27bfe8f395f2399b174f479a5202e293ca4", "first_message": "You are lucky!  Full moon tonight.", "exit": 0}
    {"core": 11, "disp": 22, "clock": "2021-01-13 12:00:00", "steps": 5922, "done": true, "end_status": 1, "sha256": "0fbeb4cdde916024b616f7dfa332228302d101be70d6f72b9e3a87ca5d07066d", "first_message": "Be careful!  New moon tonight.", "exit": 0}
    {"core": 11, "disp": 22, "clock": "2021-01-07 12:00:00", "steps": 5922, "done": true, "end_status": 1, "sha256": "cadc9127630bc0ee3c8b8ca10718158ee81e25c13e67302f81d8503ebc8c601e", "first_message": "Konnichi wa Agent, welcome to NetHack!  You are a lawful female human Samurai.", "exit": 0}
    {"core": 33, "disp": 44, "clock": "2021-01-07 12:00:00", "steps": 2452, "done": true, "end_status": 1, "sha256": "9a16767d059babaa7df2c33f995095ed1ca4be990d0f1f9295be6a3a88c6b6a6", "first_message": "Aloha Agent, welcome to NetHack!  You are a neutral female human Tourist.", "exit": 0}
    {"core": 33, "disp": 44, "clock": "2021-01-07 12:00:00", "steps": 2452, "done": true, "end_status": 1, "sha256": "9a16767d059babaa7df2c33f995095ed1ca4be990d0f1f9295be6a3a88c6b6a6", "first_message": "Aloha Agent, welcome to NetHack!  You are a neutral female human Tourist.", "exit": 0}

`end_status` 1 is NLE's `DEATH`. The new-moon and ordinary-day episodes of seed pair (11, 22) end at the same step,
5922, but their hashes differ. The full-moon episode runs to 16478 steps. A full moon adds +1 Luck, which changes
the game.

## What follows
1. `worlds/nethack366/binding.py` runs this image per episode, derives the seeds and the frozen instant from the
   issued seed, and computes BALROG's progression host-side from `blstats` and `tty_chars`, with the vendored files of
   `worlds/nethack/balrog/`. `manifest.json` declares the observation, targets and price.
2. The pins, with mutants: determinism with golden hashes, which needs the image wherever `pins` runs; the clock
   frozen (mutant: instant read from the wall clock); never pooled with `nethack` (brief 2 P2).
3. AutoAscend's image and adapter (feasibility record section 3).
