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

The per-episode utility is BALROG's progression (brief 2 section 2, Utility): its `Progress` class and its
`achievements.json` table, vendored unmodified under `balrog/` from `BALROG_REPO` at `BALROG_COMMIT`, each file
checked against its recorded SHA-256 before the module is executed, and updated after every step as BALROG's own NLE
wrapper does. It is never reimplemented here.

The judge binds this World beside its `manifest.json` (`judge.evaluate.bound`). An episode emits the manifest's
observation: `glyphs`, the message line as `toplines`, and each of NLE's bottom-line stats under its own name, read
from the same NLE observation the trajectory hash covers."""

from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import json
import re
import sys
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
# BALROG's progression (brief 2 section 2, Utility), vendored under `balrog/`: each file's path at BALROG_COMMIT
# upstream and its SHA-256, recorded when it was copied byte for byte.
BALROG_REPO = "https://github.com/balrog-ai/BALROG"
BALROG_COMMIT = "b7afe79e3e4265811cfa985ed7c95c4d1a11e3f5"
BALROG_FILES = {
    "progress.py": ("balrog/environments/nle/progress.py",
                    "7c267bd24c9a78a15176b53738849cb9ce480849c031c6a77021869e0f5aa8f2"),
    "achievements.json": ("balrog/environments/nle/achievements.json",
                          "a582cff2ffcaa34117e7c94a5406faf70fe41369263f9e49a46dff19169d3101"),
    "LICENSE": ("LICENSE", "4e2bcd21929f977a0b6faae5f5461e6100f0328f959165336e5462348a22a118"),
}
BALROG_DIR = Path(__file__).with_name("balrog")
# What BALROG's progression reads besides the observed keys: the terminal, for its end-of-game reason.
PROGRESS_READS = ("tty_chars",)
MANIFEST = Path(__file__).with_name("manifest.json")
# NLE's bottom-line stats in `blstats` order, each under NLE's own name for it (`nethack.NLE_BL_<name>`, lowercased).
BLSTATS = tuple(n[len("NLE_BL_"):].lower() for n in sorted((n for n in dir(nle.nethack) if n.startswith("NLE_BL_")),
                                                            key=lambda n: getattr(nle.nethack, n)))


def installed_versions() -> dict[str, str]:
    """The `nle` distribution's version, and the NetHack version in the banner of the game library it ships."""
    lib = Path(nle.__file__).with_name("libnethack.so").read_bytes()
    banner = re.search(rb"NetHack Version (\d+\.\d+\.\d+)", lib)
    return {"nle": importlib.metadata.version("nle"), "nethack": banner.group(1).decode() if banner else ""}


def seeds(seed: int) -> dict[str, int]:
    """The game's seed for each stream: the first 8 bytes of SHA-256 of `<seed>:<stream>`, read big-endian and kept
    below 2**63, the range NLE draws its own seeds from. Independent of string-hash salting."""
    return {s: int.from_bytes(hashlib.sha256(f"{seed}:{s}".encode()).digest()[:8], "big") >> 1 for s in STREAMS}


def balrog(root: Path = BALROG_DIR):
    """BALROG's vendored `progress` module, loaded from `root` only after every file in BALROG_FILES there has its
    recorded SHA-256, and only if the table it loaded is the checked one. Raises ValueError otherwise."""
    data = {name: (root / name).read_bytes() for name in BALROG_FILES}
    altered = sorted(n for n, (_, sha) in BALROG_FILES.items() if hashlib.sha256(data[n]).hexdigest() != sha)
    if altered:
        raise ValueError(f"vendored BALROG files differ from their recorded SHA-256 at {BALROG_COMMIT[:12]}: {altered}")
    name = f"balrog_progress_{hashlib.sha256(str(root.resolve()).encode()).hexdigest()[:12]}"
    module = importlib.util.module_from_spec(importlib.util.spec_from_file_location(name, root / "progress.py"))
    sys.modules[name] = module  # the vendored module's dataclass looks itself up there
    exec(compile(data["progress.py"], str(root / "progress.py"), "exec"), vars(module))
    if module.ACHIEVEMENTS != json.loads(data["achievements.json"]):
        raise ValueError("the progression table loaded is not the checked achievements.json")
    return module


def make_env(seed: int) -> NetHackChallenge:
    """NetHackChallenge with its seed lock lifted and its game seeded from `seed`, before its first reset."""
    env = NetHackChallenge(observation_keys=OBSERVED + PROGRESS_READS, fix_moon_phase=True)
    for lock in LOCKS:
        delattr(env.nethack, lock)
    s = seeds(seed)
    NLE.seed(env, s["core"], s["disp"], False, s["lgen"])
    return env


def observe(obs: Mapping) -> dict:
    """The observation as plain lists: glyph ids by row, message bytes, bottom-line stats."""
    return {k: obs[k].tolist() for k in OBSERVED}


def identifier(name: str) -> str:
    """A manifest name for an nle or BALROG name: lowercased, every character that is not a letter or digit dropped."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def manifest() -> dict:
    return json.loads(MANIFEST.read_text())


def world_seed(seed: int) -> int:
    """The seed from which the World of `seed` generates: `seed` itself, since its game's streams are each a distinct
    hash of it (`seeds`), so distinct seeds name distinct Worlds."""
    return seed


def view(raw: Mapping) -> dict:
    """The manifest's observation of an NLE observation (`observe`'s): the map, the message line, and each
    bottom-line stat under its name."""
    return {"glyphs": raw["glyphs"], "toplines": raw["message"]} | dict(zip(BLSTATS, raw["blstats"], strict=True))


class Episode:
    """One NetHackChallenge episode from `seed`. The seed stays here; nothing it returns carries it."""

    def __init__(self, seed: int, m: Mapping | None = None):
        self.manifest = m or manifest()
        self._env = make_env(seed)
        obs, _ = self._env.reset()
        self.t = 0
        self.done = False
        self.truncated = False
        self.end_status = None
        self.nle = observe(obs)
        self.observation = view(self.nle)
        # The class BALROG's `get_progress_system` gives NetHackChallenge, fresh at reset as in BALROG's NLE wrapper.
        self.progress = balrog().Progress()

    @property
    def utility(self) -> float:
        """BALROG's progression of the episode so far, in [0, 1] (brief 2 section 2, Utility)."""
        return self.progress.progression

    @property
    def achievements(self) -> list[str]:
        """The progression table's entries the episode reached, depths then experience levels, as manifest names."""
        return [identifier(k) for k in self.progress.dlvl_list + self.progress.xplvl_list]

    @property
    def termination(self) -> str:
        """How the World ended the episode: `truncated` at NetHackChallenge's step limit, else `terminal`."""
        return "truncated" if self.truncated else "terminal"

    @property
    def legal_actions(self) -> list[int]:
        """Every key of NetHackChallenge's full keyboard is legal at every step; NetHack answers one it cannot use."""
        return list(range(self._env.action_space.n))

    def step(self, action: int) -> dict:
        if self.done:
            raise RuntimeError("step after the episode ended")
        if action not in self.legal_actions:
            raise ValueError(f"illegal action {action!r}")
        obs, reward, terminated, truncated, info = self._env.step(action)
        self.t += 1
        self.done = bool(terminated or truncated)
        self.truncated = bool(truncated) and not terminated
        self.end_status = int(info["end_status"])
        self.progress.update(obs, reward, self.done, info)
        self.nle = observe(obs)
        self.observation = view(self.nle)
        return self.observation

    def close(self) -> None:
        self._env.close()


def _line(record: Mapping) -> bytes:
    return json.dumps(record, sort_keys=True, separators=(",", ":")).encode()


def trajectory(seed: int, actions: Iterable[int]) -> tuple[str, int]:
    """Play `actions` from `seed` until they run out or the episode ends. Returns the SHA-256 over every NLE
    observation the episode's emitted ones are read from (`observe`; each emitted one is its `view`), each action and
    the done flag, step by step, with the number of steps played."""
    ep = Episode(seed)
    try:
        h = hashlib.sha256(_line({"t": 0, "observation": ep.nle}))
        for action in actions:
            if ep.done:
                break
            ep.step(action)
            h.update(_line({"t": ep.t, "action": action, "observation": ep.nle, "done": ep.done}))
        return h.hexdigest(), ep.t
    finally:
        ep.close()
