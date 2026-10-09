"""Compute priced in the World's utility (brief 1 A4 item 4).

An episode's measured compute (`compute.py`, `episodes.py`) is converted into units of the World's per-episode utility
at the rates the World's manifest commits in its `price` block, with their derivation in its `rationale`, by one rule.
A World whose manifest commits no price has none: the judge refuses to evaluate it (`Unpriced`), never borrowing
another World's rates (brief 2 A2, P20):

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

from collections.abc import Mapping
from dataclasses import dataclass

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


def of(manifest: Mapping) -> Price:
    """The rates `manifest` commits for its World."""
    c = manifest.get("price")
    if c is None:
        raise Unpriced(f"{manifest['world']!r} commits no price in its manifest")
    return Price(float(c["cpu_s"]), float(c["memory_gb_s"]))


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
