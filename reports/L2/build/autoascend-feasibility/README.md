# AutoAscend against the judge's NetHack observation (brief 2 section 3) — feasibility record

VERDICT: no adapter on today's binding can run AutoAscend; one can once a separate World variant emits the observation AutoAscend reads. This is not "no adapter can make it run" (brief 2 section 3's stop): the missing fields are NLE's own observation keys, a binding-and-manifest change under A3 item 3, not a change to `judge/` or `worlds/spec/`. Nothing here edits either.

Source examined: https://github.com/maciej-sypetkowski/autoascend at `8527910bd85c4d851c18ad912aae606c92cd516a` (master at `git ls-remote`, 2026-10-23), tarball extracted to a scratch directory outside the repository. SHA-256: `requirements.txt` f3a3075d2d0180eb36be5cade92ed2a1bde72bd7bb019876b4495f9ad03d418a; `Dockerfile` ca697cae0fab2d0e1d6181381062fdbd85b2c4ede3a50d6377664a8b2985ea29. Denominator: every `obs[...]`/`observation[...]` subscript in `autoascend/` and `bin/` (regex below); dynamic access (`obs[key]` with a variable key) would not match and is not counted.

## 1. Version mismatch (brief 2 section 3, "Version mismatch")

AutoAscend's `Dockerfile` builds `nle` at `git checkout v0.7.3` and patches it to allow seeding; the binding runs `nle` 1.3.0 / NetHack 3.6.7 (`worlds/nethack/binding.py`, `NLE_VERSION`, `NETHACK_VERSION`). NLE v0.7.3 is the 3.6.6 line. The brief then requires AutoAscend to be a separate World variant with its own manifest, never pooled with the 3.6.7 World. Its requirements (`numba==0.52.0`, `numpy==1.21.2`, `gym==0.19.0`, `ray==1.8.0`, `torch==1.10.0a0+3fd9dcf`) are a different interpreter generation from the judge's.

## 2. Observation keys AutoAscend reads

Command (scratch copy at the commit above):

    grep -rhoE "obs(ervation)?\[['\"][a-z_]+['\"]\]" autoascend bin | sed -E "s/.*\['?\"?([a-z_]+).*/\1/" | sort | uniq -c

Output:

          4 blstats
          4 chars
          7 glyphs
          1 inv_glyphs
          1 inv_letters
          1 inv_oclasses
          4 inv_strs
          1 message
          6 misc
          3 specials
          9 tty_chars
          2 tty_cursor

The manifest's observation (`worlds/nethack/manifest.json`, `worlds/nethack/binding.py` `OBSERVED`) is `glyphs`, the message line as `toplines`, and the 27 `blstats` fields. Unmet: `chars`, `inv_glyphs`, `inv_letters`, `inv_oclasses`, `inv_strs`, `misc`, `specials`, `tty_chars`, `tty_cursor`. AutoAscend reads `tty_chars` nine times (it detects `[yn]` prompts and parses the screen lines) and `inv_*` for its item model; an adapter cannot synthesise these from glyphs and a message line.

## 3. Control inversion

AutoAscend calls `env.step(action)` itself (`autoascend/agent.py:372`, `autoascend/env_wrapper.py:322`), seeds with `env.env.seed(seed, seed)` (`bin/main.py:58`) and reads `env.get_seeds()` (`autoascend/env_wrapper.py:189,386`). The candidate protocol is the reverse: the judge sends `step` with an observation and receives an action. A thin adapter is a gym-shaped object whose `step` blocks on the JSON-RPC loop (a thread or coroutine that replies with the chosen action and receives the next observation). That adapter is small once the observation is complete. Run in-process with its own NLE it would play a second game beside the judge's, which is not the judge's episode; the adapter must therefore have no NLE of its own and take every observation from the judge.

## 4. What follows (not done here)

1. L2b: a NetHack 3.6.6 World variant (NLE 0.7.3 with seeding enabled, as AutoAscend's `Dockerfile` does) whose manifest declares the keys in section 2, with its own price and targets, never pooled with the 3.6.7 World. The judge binds Worlds by manifest and binding; it needs no edit.
2. L2b: the AutoAscend image, pinned by commit above, and the adapter of section 3, its full diff reported (brief 2 section 3).
3. The pin that this variant is never pooled (P2 of brief 2) and that the adapter's image does not import `judge/`.

This record adds no code, no pin and no mutant: it adds none of the checks it describes, so it carries no "kills a named mutant" claim.
