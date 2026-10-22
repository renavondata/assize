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

## Utility (brief 2 section 2)
- The per-episode utility is BALROG's progression: `balrog/progress.py` and its table `balrog/achievements.json`, with
  BALROG's MIT `LICENSE`, copied byte for byte from https://github.com/balrog-ai/BALROG at commit
  `b7afe79e3e4265811cfa985ed7c95c4d1a11e3f5` (paths `balrog/environments/nle/progress.py`, `.../achievements.json`,
  `LICENSE`). `binding.BALROG_FILES` records each file's SHA-256; `binding.balrog()` refuses to load the module unless
  every file matches. Nothing is reimplemented: each `Episode` holds a fresh `Progress` (the class BALROG's
  `get_progress_system` gives NetHackChallenge) and feeds it every step, as BALROG's NLE wrapper does. The game also
  emits `tty_chars`, which `Progress` reads for its end-of-game reason; it is not part of the emitted observation.
- Units: BALROG's value in [0, 1]; BALROG reports it times 100 as a percentage.
- P37 (brief 2 P4): the vendored files and the binding's record equal the commit and checksums committed in the pin;
  the binding refuses a copy with one table entry altered, and one with the code altered; the utility of two seeded
  streams equals its golden (seed 1: 0.0; seed 3: the `Dlvl:2` entry). Mutants `table_entry_altered`,
  `table_and_checksum_altered`, `checksum_unchecked`, `progress_not_updated`, `minihack_progress`.

## Manifest, observations, targets and price (brief 2 section 2)
- `manifest.json` makes the judge bind this World (`judge.evaluate.bound`) and price it (`judge.price.of`). The
  binding gives the judge's Episode protocol: `Episode(seed, manifest)`, `world_seed`, `manifest()`, and each episode's
  `termination` (`truncated` at NetHackChallenge's step limit, else `terminal`) and `achievements`.
- Observation: `glyphs` (21x79 glyph ids below nle's `MAX_GLYPH`), `toplines` (the 256-byte message line; `message`
  names a JSON-RPC field of the interface schema, P6), and NLE's 27 bottom-line stats, each its own integer field under
  NLE's name, with the bounds NLE's observation space declares, but the three target fields, bounded by their support.
  The trajectory hash (P36) still covers the NLE observation every emitted one is read from.
- Actions and utility components are NetHackChallenge's keys and BALROG's table keys, each lowercased with every
  character that is not a letter or digit dropped (`binding.identifier`), so no name splits into an interface token.
- Targets, one step ahead, committed before any run: `depth` (-5 to 53), `experience_level` (0 to 30) and `hunger`
  (0 to 6). Each support is derived from NetHack 3.6.7's source and the `dungeon.def` nle ships; 0 is NLE's zeroed
  observation outside a running game, which an episode's last observation after death is. Derivations are in each
  target's rationale.
- Price: `delta` = 0.02, brief 2's FIT effect of 2 progression points in BALROG's [0, 1] units, and the rates its
  derivation.
- P38: the manifest's names, bounds and supports are those derived from the installed nle, the vendored table and
  NetHack's source; the judge binds and prices the World; P36's seeded streams, played through the Episode protocol,
  emit only declared observations and supported target values and reach their golden achievements. Mutants
  `endgame_depths_dropped`, `zeroed_xp_dropped`, `delta_in_points`, `observation_raw`, `achievements_raw`.

## Not yet here
The MiniHack ladder, AutoAscend, and the version-pooling (P2) and long-episode (P3) pins.
