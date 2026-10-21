"""NetHack World binding (brief 2 section 2): one episode of NLE's NetHackChallenge task, its game seeded from the
issued seed, observed through glyphs, message and bottom-line stats.

The task is `nle.env.tasks.NetHackChallenge` with one change, made here on each instance and never in the installed
package: NetHackChallenge locks its game's seeds (it replaces `set_initial_seeds`, `set_current_seeds` and
`get_current_seeds` on the instance with functions that raise, and overrides `seed` to raise), so that a challenge
entrant could not choose its dungeon. Here the judge issues the seed (brief 1 section 2), so the binding deletes the
three instance attributes, restoring the package's own methods, and seeds the game through `nle.env.base.NLE.seed`:
the core, display and level-generator streams each from the issued seed, with NetHack's anti-automation reseeding
off, without which no trajectory is reproducible (brief 2 section 2, Determinism). The game is built with NLE's
`fix_moon_phase`, so its clock-driven effects (moon phase, Friday the 13th, night, midnight) are derived from the seed,
not read from the date the episode is played on. The action set, character choice, yes/no and mode handling, step and
no-progress limits are NetHackChallenge's own.

Not yet bound: this directory holds no `manifest.json` until its utility (BALROG's progression, vendored) and its
prediction targets are committed, so the judge does not bind it (`judge.evaluate.bound`)."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import re
from collections.abc import Iterable, Mapping
from pathlib import Path

import nle
from nle.env.base import NLE
from nle.env.tasks import NetHackChallenge

# The versions installed and recorded (brief 2 section 2, Versions): the `nle` distribution, and the NetHack it
# builds, read from the version banner compiled into the game library it loads.
NLE_VERSION = "1.3.0"
NETHACK_VERSION = "3.6.7"
# The observation keys the binding reads (brief 2 section 2, Observations): the map's glyph ids, the top-line
# message, and the bottom-line stats.
OBSERVED = ("glyphs", "message", "blstats")
# The game's three RNG streams, each seeded from the issued seed under its own name.
STREAMS = ("core", "disp", "lgen")
# The locks NetHackChallenge sets on its game instance.
LOCKS = ("set_initial_seeds", "set_current_seeds", "get_current_seeds")


def installed_versions() -> dict[str, str]:
    """The `nle` distribution's version, and the NetHack version in the banner of the game library it ships."""
    lib = Path(nle.__file__).with_name("libnethack.so").read_bytes()
    banner = re.search(rb"NetHack Version (\d+\.\d+\.\d+)", lib)
    return {"nle": importlib.metadata.version("nle"), "nethack": banner.group(1).decode() if banner else ""}


def seeds(seed: int) -> dict[str, int]:
    """The game's seed for each stream: the first 8 bytes of SHA-256 of `<seed>:<stream>`, read big-endian and kept
    below 2**63, the range NLE draws its own seeds from. Independent of string-hash salting."""
    return {s: int.from_bytes(hashlib.sha256(f"{seed}:{s}".encode()).digest()[:8], "big") >> 1 for s in STREAMS}


def make_env(seed: int) -> NetHackChallenge:
    """NetHackChallenge with its seed lock lifted and its game seeded from `seed`, before its first reset."""
    env = NetHackChallenge(observation_keys=OBSERVED, fix_moon_phase=True)
    for lock in LOCKS:
        delattr(env.nethack, lock)
    s = seeds(seed)
    NLE.seed(env, s["core"], s["disp"], False, s["lgen"])
    return env


def observe(obs: Mapping) -> dict:
    """The observation as plain lists: glyph ids by row, message bytes, bottom-line stats."""
    return {k: obs[k].tolist() for k in OBSERVED}


class Episode:
    """One NetHackChallenge episode from `seed`. The seed stays here; nothing it returns carries it."""

    def __init__(self, seed: int):
        self._env = make_env(seed)
        obs, _ = self._env.reset()
        self.t = 0
        self.done = False
        self.end_status = None
        self.observation = observe(obs)

    @property
    def legal_actions(self) -> list[int]:
        """Every key of NetHackChallenge's full keyboard is legal at every step; NetHack answers one it cannot use."""
        return list(range(self._env.action_space.n))

    def step(self, action: int) -> dict:
        if self.done:
            raise RuntimeError("step after the episode ended")
        if action not in self.legal_actions:
            raise ValueError(f"illegal action {action!r}")
        obs, _, terminated, truncated, info = self._env.step(action)
        self.t += 1
        self.done = bool(terminated or truncated)
        self.end_status = int(info["end_status"])
        self.observation = observe(obs)
        return self.observation

    def close(self) -> None:
        self._env.close()


def _line(record: Mapping) -> bytes:
    return json.dumps(record, sort_keys=True, separators=(",", ":")).encode()


def trajectory(seed: int, actions: Iterable[int]) -> tuple[str, int]:
    """Play `actions` from `seed` until they run out or the episode ends. Returns the SHA-256 over every emitted
    observation, each action and the done flag, step by step, with the number of steps played."""
    ep = Episode(seed)
    try:
        h = hashlib.sha256(_line({"t": 0, "observation": ep.observation}))
        for action in actions:
            if ep.done:
                break
            obs = ep.step(action)
            h.update(_line({"t": ep.t, "action": action, "observation": obs, "done": ep.done}))
        return h.hexdigest(), ep.t
    finally:
        ep.close()
