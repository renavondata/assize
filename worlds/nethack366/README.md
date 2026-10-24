L2b — the NetHack 3.6.6 World variant (brief 2 section 3, Version mismatch). Not yet bound: the judge binds a World
only beside a `manifest.json` and a `binding.py` (`judge.evaluate.bound`), and this directory has neither yet.

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
  image's entrypoint is `faketime -f <instant>`, so the caller freezes the clock at an instant it names.
- The build and the determinism witness are recorded in `reports/L2/build/nethack366-image/README.md`.

## Not yet here
`binding.py` (it runs the image per episode, with no network and a read-only root, and derives the seeds and the
frozen instant from the issued seed), `manifest.json` (observations, targets and price), the determinism and
non-pooling pins (brief 2 P2), and building the image where the pins run.
