"""Compute priced in the World's utility (brief 1 A4 item 4).

An episode's measured compute (`compute.py`, `episodes.py`) is converted into units of the World's per-episode utility
at the rates the World's manifest commits in its `price` block, with their derivation in its `rationale`, by one rule.
A World whose manifest commits no price has none: the judge refuses to evaluate it (`Unpriced`), never borrowing
another World's rates (brief 2 A2, P20). The block commits `delta`, the smallest difference in per-episode utility its
World's FIT criterion requires the court to detect (brief 1: 0.5 achievements; brief 2: δ = 2 progression points), and its
rates must be that delta's derivation: an episode exhausting every allowance of `config.toml` is charged `delta`, half
for each resource. Rates that are not, another World's among them, are refused (`Underived`), so a World is priced in
its own utility before any scored run (brief 2 A2, L2a obligation 19, P33):

- CPU: the episode's measured `cpu_s`, plus its `unmeasured_s` at the configured CPUs. What the judge could not
  measure (a crashed container takes its cgroup with it) is charged at the most the candidate could have used, so that
  no candidate lowers its price by dying.
- Memory: `peak_memory_bytes`, whose scope the record states as `peak_memory_scope`, over the measured stretch
  `wall_s - unmeasured_s`, plus the configured memory limit over `unmeasured_s`, in gigabyte-seconds (1e9 bytes).

The peak's scope is `container_since_start`: the container's high-water mark from its start to the episode's last
sample, because a cgroup's `memory.peak` cannot be reset under both runtimes. An episode played in a container that
served earlier ones is therefore charged their high-water mark too. That is the rule, not an approximation of the
episode's own peak: the host must hold a container's high-water mark available for as long as the container runs, and
the episode's own peak, which no cgroup file reports, is never claimed."""

from __future__ import annotations

import math
import sys
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from judge import runtime

# The scope of every record's `peak_memory_bytes`, stated in the record beside it.
PEAK_SCOPE = "container_since_start"
GB = 1e9


@dataclass(frozen=True)
class Price:
    """Utility per CPU-second and per gigabyte-second of peak memory, for one World."""

    cpu_s: float
    memory_gb_s: float


class Unpriced(ValueError):
    """A World whose manifest commits no price."""


class Underived(Unpriced):
    """A World whose committed rates are not the derivation from its own committed `delta`."""


def derived(delta: float, lim: runtime.Limits, episode_s: float) -> Price:
    """The rates at which an episode exhausting every allowance, `lim` for `episode_s` seconds, is charged `delta`, half
    for each resource."""
    return Price(delta / 2 / (lim.cpus * episode_s), delta / 2 / ((lim.memory_mib << 20) / GB * episode_s))


def _episode_s(path: Path = runtime.CONFIG) -> float:
    return float(tomllib.loads(path.read_text())["timeouts"]["episode_s"])


def _same(a: float, b: float) -> bool:
    """`a` equals `b` up to the rounding of a few double-precision operations (a derived bound)."""
    return math.isclose(a, b, rel_tol=8 * sys.float_info.epsilon, abs_tol=0.0)


def of(manifest: Mapping) -> Price:
    """The rates `manifest` commits for its World, refused unless they are the derivation from its own `delta`."""
    c = manifest.get("price")
    if c is None:
        raise Unpriced(f"{manifest['world']!r} commits no price in its manifest")
    if c.get("delta") is None:
        raise Underived(f"{manifest['world']!r} commits no delta from which its price is derived")
    committed, want = Price(float(c["cpu_s"]), float(c["memory_gb_s"])), derived(float(c["delta"]), runtime.limits(),
                                                                                     _episode_s())
    if not (_same(committed.cpu_s, want.cpu_s) and _same(committed.memory_gb_s, want.memory_gb_s)):
        raise Underived(f"{manifest['world']!r} commits {committed}, not the derivation {want} from its delta "
                        f"{c['delta']}")
    return committed


def charge(used: Mapping, lim: runtime.Limits, p: Price) -> dict[str, float]:
    """The price of one episode's measured compute `used`, in the World's utility: the CPU and memory terms and their
    total."""
    if used["peak_memory_scope"] != PEAK_SCOPE:
        raise ValueError(f"peak memory of scope {used['peak_memory_scope']!r} has no price")
    unmeasured = used["unmeasured_s"]
    cpu = p.cpu_s * (used["cpu_s"] + lim.cpus * unmeasured)
    # A container that crashed early in an episode it did not start in was last read before the episode began, so its
    # unmeasured stretch can exceed the episode's wall-clock; the measured stretch is then empty, never negative.
    measured = max(used["wall_s"] - unmeasured, 0.0)
    memory = p.memory_gb_s * (used["peak_memory_bytes"] * measured + (lim.memory_mib << 20) * unmeasured) / GB
    return {"cpu": cpu, "memory": memory, "total": cpu + memory}
