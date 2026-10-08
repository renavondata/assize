"""Time-to-learn (brief 1 section 5): episodes per arm, and the wall-clock they take, before a candidate shifted by
delta achievements per episode over the incumbent is told apart from it.

Assumption, stated in every report: a candidate's per-episode utility is distributed as the incumbent's shifted by
delta. The incumbent's distribution is uncertain; its posterior is the Bayesian bootstrap over the pilot's per-episode
utilities (Dirichlet(1, ..., 1) weights on the observed episodes). An experiment of m episodes per arm draws one
distribution from that posterior, m incumbent episodes from it and m candidate episodes from it shifted by delta; its
posterior on the difference in mean utility is the Bayesian bootstrap of each arm. Its mass on the correct sign is the
fraction of posterior draws with candidate mean above incumbent mean (a tie is not the correct sign). The detection
measure at m is that mass averaged over experiments: the preposterior probability that the sign the posterior favours
is right. m* is the smallest m whose measure reaches `mass`, searched up to the episodes per arm the budget affords.
"""

from __future__ import annotations

import math
import tomllib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np

CONFIG = Path(__file__).resolve().parent / "config.toml"
CHUNK = 100  # experiments drawn at once; bounds memory, not results


@dataclass(frozen=True)
class Row:
    delta: float
    episodes_per_arm: int | None  # None: not detected within the budget
    measure: float | None
    wall_s: float | None


def config(path: Path = CONFIG) -> dict:
    with path.open("rb") as f:
        return tomllib.load(f)


def _means(rng: np.random.Generator, counts: np.ndarray, values: np.ndarray, draws: int) -> np.ndarray:
    """Bayesian-bootstrap draws of each experiment's mean: Dirichlet(1, ..., 1) over its episodes, which grouped by
    value is a Gamma(count) weight per value. Shape (experiments, draws)."""
    g = rng.standard_gamma(np.broadcast_to(counts[:, None, :], (counts.shape[0], draws, counts.shape[1])))
    return (g @ values) / g.sum(axis=2)


def measure(utilities: Sequence[float], delta: float, m: int, cfg: dict) -> float:
    """Mean over simulated experiments of m episodes per arm of the posterior mass on candidate mean > incumbent mean."""
    tally = Counter(utilities)
    values = np.array(sorted(tally), dtype=float)
    observed = np.array([tally[v] for v in sorted(tally)], dtype=float)
    rng = np.random.default_rng([cfg["seed"], m])
    total = cfg["experiments"]

    def chunk(n: int) -> float:
        w = rng.standard_gamma(np.broadcast_to(observed, (n, len(values))))
        w = w / w.sum(axis=1, keepdims=True)
        a = rng.multinomial(m, w)
        b = rng.multinomial(m, w)
        diff = (_means(rng, b, values, cfg["posterior_draws"]) + delta) - _means(rng, a, values, cfg["posterior_draws"])
        return float((diff > 0).mean(axis=1).sum())

    return math.fsum(chunk(min(CHUNK, total - i)) for i in range(0, total, CHUNK)) / total


def affordable(throughput: float, cfg: dict) -> int:
    """Episodes per arm the budget affords at `throughput` episodes per wall-clock second: both arms are run."""
    return math.floor(cfg["budget_s"] * throughput / 2)


def episodes_per_arm(utilities: Sequence[float], delta: float, cap: int, cfg: dict) -> tuple[int, float] | None:
    """The smallest m <= cap whose measure reaches cfg['mass'], with that measure, by doubling then bisection."""
    if cap < 1:
        return None
    hit = lambda m: (lambda x: (x >= cfg["mass"], x))(measure(utilities, delta, m, cfg))

    def double(lo: int, m: int) -> tuple[int, int, float] | None:
        ok, x = hit(m)
        if ok:
            return lo, m, x
        return None if m == cap else double(m, min(2 * m, cap))

    def bisect(lo: int, hi: int, x_hi: float) -> tuple[int, float]:
        if hi - lo <= 1:
            return hi, x_hi
        mid = (lo + hi) // 2
        ok, x = hit(mid)
        return bisect(lo, mid, x) if ok else bisect(mid, hi, x_hi)

    found = double(0, 1)
    return None if found is None else bisect(*found)


def table(utilities: Sequence[float], throughput: float, cfg: dict) -> list[Row]:
    """One row per configured delta: episodes per arm, the measure there, and the wall-clock both arms take."""
    cap = affordable(throughput, cfg)

    def row(delta: float) -> Row:
        found = episodes_per_arm(utilities, delta, cap, cfg)
        if found is None:
            return Row(delta, None, None, None)
        m, x = found
        return Row(delta, m, x, 2 * m / throughput)

    return [row(d) for d in cfg["deltas"]]


def verdict(rows: Sequence[Row], cfg: dict) -> str:
    """FIT if fit_delta is detectable within the budget, MARGINAL if only marginal_delta is, UNFIT otherwise."""
    detected = {r.delta for r in rows if r.episodes_per_arm is not None}
    if cfg["fit_delta"] in detected:
        return "FIT"
    return "MARGINAL" if cfg["marginal_delta"] in detected else "UNFIT"
