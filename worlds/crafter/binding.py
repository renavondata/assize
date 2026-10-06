"""Crafter World binding (brief 1 section 3): one episode of the `crafter` package, observed through its semantic map
and inventory as `manifest.json` declares them, with utility the count of distinct achievements unlocked.

The package's `Env.step` runs unaltered, image rendering included: Crafter's night-time render draws from the
World's own random state, so skipping it would change the dynamics and leave the seeded trajectory no longer Crafter's.
The image itself is discarded.

The World is crafter 1.8.3 with one change (brief 1 A7 item 1), made here at every reset and never in the installed
package: each chunk's objects sit in an insertion-ordered container instead of a set. Crafter despawns
`creatures[randint(n)]` from a list built by iterating that set, whose order follows object addresses; ordered, the
same draw selects the same creature in every process, and the law of a trajectory is unchanged."""

from __future__ import annotations

import collections
import hashlib
import json
import math
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

import crafter

MANIFEST = Path(__file__).with_name("manifest.json")


class OrderedChunk(dict):
    """A chunk's objects in insertion order, with the two set methods `crafter.engine.World` calls."""

    def add(self, obj) -> None:
        self[obj] = None

    def remove(self, obj) -> None:
        del self[obj]


def ordered_chunks(world: crafter.engine.World) -> crafter.engine.World:
    """`world`, whose every reset leaves its chunk containers insertion-ordered before any object is added."""
    reset = world.reset

    def ordered_reset(seed=None):
        reset(seed=seed)
        world._chunks = collections.defaultdict(OrderedChunk)

    world.reset = ordered_reset
    return world


def make_env(seed: int) -> crafter.Env:
    """The World of brief 1 A7 item 1 for `seed`, before its first reset."""
    env = crafter.Env(seed=seed)
    ordered_chunks(env._world)
    return env


def chunk_departures(env: crafter.Env) -> list[str]:
    """Where the chunk containers differ from the package's own object list: each must hold exactly the live
    objects whose position falls in that chunk, so that every world-generated creature takes part in balancing."""
    world = env._world
    want = collections.defaultdict(set)
    for obj in world.objects:
        want[world.chunk_key(obj.pos)].add(id(obj))
    have = {k: {id(o) for o in objs} for k, objs in world._chunks.items() if objs}
    return [f"chunk {k}: {len(have.get(k, set()))} held, {len(want.get(k, set()))} live"
            for k in sorted(set(want) | set(have)) if have.get(k, set()) != want.get(k, set())]


def manifest() -> dict:
    return json.loads(MANIFEST.read_text())


def observe(env: crafter.Env, fields: Sequence[Mapping]) -> dict:
    """The manifest's observation of `env`: the categorical field is the semantic map, every integer field the
    inventory count of that name."""
    inventory = env._player.inventory
    return {f["name"]: env._sem_view().tolist() if f["type"] == "categorical" else int(inventory[f["name"]])
            for f in fields}


def unlocked(env: crafter.Env) -> frozenset[str]:
    return frozenset(name for name, count in env._player.achievements.items() if count > 0)


class Episode:
    """One Crafter episode from `seed`, of the package's default length. The seed stays here; nothing it returns
    carries it."""

    def __init__(self, seed: int, m: Mapping | None = None):
        self.manifest = m or manifest()
        self._env = make_env(seed)
        self._env.reset()
        self.t = 0
        self.done = False
        self.observation = observe(self._env, self.manifest["observation"])

    @property
    def legal_actions(self) -> list[int]:
        """Every Crafter action is legal at every step; one with no effect acts as `noop`."""
        return list(range(len(self.manifest["actions"])))

    def step(self, action: int) -> dict:
        if self.done:
            raise RuntimeError("step after the episode ended")
        if action not in self.legal_actions:
            raise ValueError(f"illegal action {action!r}")
        _, _, done, _ = self._env.step(action)
        self.t += 1
        self.done = bool(done)
        self.observation = observe(self._env, self.manifest["observation"])
        return self.observation

    @property
    def achievements(self) -> list[str]:
        return sorted(unlocked(self._env))

    @property
    def utility(self) -> int:
        """The per-episode scalar: the count of distinct achievements unlocked."""
        return len(self.achievements)


def _line(record: Mapping) -> bytes:
    return json.dumps(record, sort_keys=True, separators=(",", ":")).encode()


def trajectory(seed: int, actions: Iterable[int], m: Mapping | None = None) -> tuple[str, Episode]:
    """Play `actions` from `seed` until they run out or the episode ends. Returns the SHA-256 over every emitted
    observation, each action, the done flag and the unlocked set, step by step, with the final episode."""
    ep = Episode(seed, m)
    h = hashlib.sha256(_line({"t": 0, "observation": ep.observation}))
    for action in actions:
        if ep.done:
            break
        obs = ep.step(action)
        h.update(_line({"t": ep.t, "action": action, "observation": obs, "done": ep.done,
                        "achievements": ep.achievements}))
    return h.hexdigest(), ep


def violations(observation: Mapping, fields: Sequence[Mapping]) -> list[str]:
    """Where `observation` departs from the manifest's fields: missing or extra names, wrong shape, values outside
    a categorical vocabulary or an integer range."""
    names = [f["name"] for f in fields]
    found = [f"missing {n}" for n in names if n not in observation]
    found += [f"undeclared {n}" for n in observation if n not in names]

    def leaves(value, shape: Sequence[int]):
        if not shape:
            return [value]
        if not isinstance(value, list) or len(value) != shape[0]:
            return None
        rows = [leaves(v, shape[1:]) for v in value]
        return None if any(r is None for r in rows) else [x for r in rows for x in r]

    for f in (f for f in fields if f["name"] in observation):
        flat = leaves(observation[f["name"]], f["shape"])
        lo, hi = (0, len(f["vocabulary"]) - 1) if f["type"] == "categorical" else f["range"]
        if flat is None:
            found.append(f"{f['name']}: shape is not {f['shape']}")
        elif not all(type(x) is int and lo <= x <= hi for x in flat):
            found.append(f"{f['name']}: value outside [{lo}, {hi}]")
    return found


def hafner_score(achievement_sets: Sequence[Iterable[str]], components: Sequence[str]) -> float:
    """Hafner (2022)'s aggregate score over episodes: exp(mean_i ln(1 + s_i)) - 1, with s_i the percentage of
    episodes unlocking achievement i. Reported beside, never as, the per-episode utility."""
    sets = [frozenset(s) for s in achievement_sets]
    rates = [100 * sum(c in s for s in sets) / len(sets) for c in components]
    return math.exp(sum(math.log1p(r) for r in rates) / len(rates)) - 1
