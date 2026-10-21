L2 — NetHack World binding (brief 2). Empty at L0.

## Versions (brief 2 section 2)
- `nle` 1.3.0 (`pyproject.toml`, `uv.lock`), which builds NetHack 3.6.7: the banner of the `libnethack.so` it ships
  reads `Unix NetHack Version 3.6.7`. `binding.NLE_VERSION` and `binding.NETHACK_VERSION` record them; P36 checks both
  against what is installed, and nle's against `uv.lock`.

## Task and determinism
- The full-game task is NLE's `NetHackChallenge`, unchanged but for its seed lock: NetHackChallenge refuses every
  seed, so `binding.make_env` lifts the lock on its own instance and seeds the core, display and level-generator
  streams from the issued seed, with NetHack's anti-automation reseeding off. It also builds the game with NLE's
  `fix_moon_phase`, so moon phase, Friday the 13th and night come from the seed, not from the date the episode is
  played on; without it a trajectory differs between an ordinary day and a full moon.
- P36: the same seed and action stream give one trajectory hash, twice per process and in two processes, equal per
  seed to a committed golden hash, for three seeds whose seed-derived clock is an ordinary day, a new moon and a full
  moon; each stream plays its episode to the game's own end. Mutants `version_misrecorded`, `seed_lock_kept`,
  `reseed_on`, `moon_from_clock`, `seed_ignored`, `character_fixed`.

## Not yet here
No `manifest.json`, so the judge does not bind this World (`judge.evaluate.bound`): the utility (BALROG's progression,
vendored at a pinned commit with a checksum), the prediction targets, the price, and the MiniHack ladder come first.
