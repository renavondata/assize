L2b — the NetHack 3.6.6 World variant (brief 2 section 3, Version mismatch). The judge binds it as `nethack366`, beside
its `manifest.json` and `binding.py` (`judge.evaluate.bound`); pin P40 witnesses it.

AutoAscend plays NLE v0.7.3, the NetHack 3.6.6 line; the `nethack` World plays NLE 1.3.0, NetHack 3.6.7
(`reports/L2/build/autoascend-feasibility/README.md`). The brief makes 3.6.6 a separate World variant with its own
manifest, never pooled with 3.6.7.

## The game image (`image/`)
- `Containerfile` builds NLE v0.7.3 at commit `da62293014df5661a75811de931d117424617dbd`, with its submodules, on
  `python:3.9-bullseye` pinned by digest, with every Python package pinned. NetHack 3.6.6's C does not compile against
  a current glibc, which is why the build is in an image and not in the judge's environment. Two `nle` versions cannot
  share one interpreter, so the game runs out of process in any case.
- `server.py` plays one NetHackChallenge episode over stdin and stdout, one JSON line per step, seeded from the two
  seeds it is sent (NLE v0.7.3 has no level-generator stream), with the instance seed lock lifted and reseeding off as
  in the 3.6.7 binding. It emits every key NLE v0.7.3 observes except the colour arrays, which include the ones
  AutoAscend reads.
- NLE v0.7.3 has no `fix_moon_phase`: the game reads moon phase, Friday the 13th and night from the system clock. The
  image preloads libfaketime and its entrypoint is `env`, so the caller freezes the clock at an instant it names with
  `FAKETIME=<instant>` (the `faketime` wrapper needs a writable /dev/shm, which a read-only root lacks).
- The build and the determinism witness are recorded in `reports/L2/build/nethack366-image/README.md`.

## The binding (`binding.py`) and manifest (`manifest.json`)
- Each episode is a container of the image, started through `judge.runtime.run_argv` (no network, a read-only root, all
  capabilities dropped, the judge's candidate limits) plus a size-bounded `/tmp` tmpfs, which NLE needs and `run_argv`
  does not give. The image is tagged with a hash of `image/Containerfile` and `image/server.py` (`image_tag`); `Episode`
  never builds or pulls, and `build` is the one act that does (P40 calls it).
- The seeds are `nethack`'s construction (a SHA-256 of the issued seed per stream); the frozen instant is another hash of
  it, a day of 2021 and an hour (`instant`), since NLE v0.7.3 has no `fix_moon_phase`.
- The manifest is `nethack`'s with NLE v0.7.3's 113 actions and 26 bottom-line stats (no `align`); targets, utility and
  price are the same, and the vendored BALROG table and class are `worlds/nethack/balrog/`, loaded through that binding.
- An episode the task aborts (`EndStatus.ABORTED`: step limit or no progress) ends `truncated`; the game's own end
  `terminal`.

## Not yet here
The incumbent: AutoAscend's image and adapter, its pilot, and the population check that never pools its episodes
with the 3.6.7 World's (brief 2 P2). The image is built, not pulled, so a registry digest for it is not pinned.
