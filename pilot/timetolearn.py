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
That is the expected reading of "90% posterior mass on the correct sign", and the verdict is taken from it. The
assurance reading, beside it in every report, is the fraction of experiments whose posterior mass reaches `mass`;
its m* reaches `mass` too, and is about twice the expected one (review 0d5e9ec F1).
"""

from __future__ import annotations

import math
import tomllib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

import numpy as np

CONFIG = Path(__file__).resolve().parent / "config.toml"
CHUNK = 100  # experiments drawn at once; bounds memory, not results


@dataclass(frozen=True)
class Row:
    delta: float
    episodes_per_arm: int | None  # None: not detected within the budget
    measure: float | None
    wall_s: float | None
    # The same three under the assurance reading, shown beside the committed (expected) one; None as above.
    assured_episodes_per_arm: int | None = None
    assured_measure: float | None = None
    assured_wall_s: float | None = None


def config(path: Path = CONFIG) -> dict:
    with path.open("rb") as f:
        return tomllib.load(f)


def _means(rng: np.random.Generator, counts: np.ndarray, values: np.ndarray, draws: int) -> np.ndarray:
    """Bayesian-bootstrap draws of each experiment's mean: Dirichlet(1, ..., 1) over its episodes, which grouped by
    value is a Gamma(count) weight per value. Shape (experiments, draws)."""
    g = rng.standard_gamma(np.broadcast_to(counts[:, None, :], (counts.shape[0], draws, counts.shape[1])))
    return (g @ values) / g.sum(axis=2)


def masses(utilities: Sequence[float], delta: float, m: int, cfg: dict) -> np.ndarray:
    """Per simulated experiment of m episodes per arm, the posterior mass on candidate mean > incumbent mean."""
    tally = Counter(utilities)
    values = np.array(sorted(tally), dtype=float)
    observed = np.array([tally[v] for v in sorted(tally)], dtype=float)
    rng = np.random.default_rng([cfg["seed"], m])
    total = cfg["experiments"]

    def chunk(n: int) -> np.ndarray:
        w = rng.standard_gamma(np.broadcast_to(observed, (n, len(values))))
        w = w / w.sum(axis=1, keepdims=True)
        a = rng.multinomial(m, w)
        b = rng.multinomial(m, w)
        diff = (_means(rng, b, values, cfg["posterior_draws"]) + delta) - _means(rng, a, values, cfg["posterior_draws"])
        return (diff > 0).mean(axis=1)

    return np.concatenate([chunk(min(CHUNK, total - i)) for i in range(0, total, CHUNK)])


def measure(utilities: Sequence[float], delta: float, m: int, cfg: dict) -> float:
    """The expected reading: the posterior mass on the correct sign, averaged over simulated experiments."""
    return math.fsum(masses(utilities, delta, m, cfg).tolist()) / cfg["experiments"]


def assurance(utilities: Sequence[float], delta: float, m: int, cfg: dict) -> float:
    """The assurance reading: the fraction of simulated experiments whose posterior mass on the correct sign reaches
    cfg['mass'] (an experiment at the mass exactly counts)."""
    return int((masses(utilities, delta, m, cfg) >= cfg["mass"]).sum()) / cfg["experiments"]


def affordable(throughput: float, cfg: dict) -> int:
    """Episodes per arm the budget affords at `throughput` episodes per wall-clock second: both arms are run."""
    return math.floor(cfg["budget_s"] * throughput / 2)


def episodes_per_arm(utilities: Sequence[float], delta: float, cap: int, cfg: dict,
                     reading: Callable[[Sequence[float], float, int, dict], float] = measure) -> tuple[int, float] | None:
    """The smallest m <= cap whose reading (`measure`, the committed one, or `assurance`) reaches cfg['mass'], with that
    reading's value there, by doubling then bisection."""
    if cap < 1:
        return None
    hit = lambda m: (lambda x: (x >= cfg["mass"], x))(reading(utilities, delta, m, cfg))

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
    """One row per configured delta: episodes per arm, the reading there, and the wall-clock both arms take, under the
    expected reading (committed) and, beside it, the assurance reading."""
    cap = affordable(throughput, cfg)

    def read(delta: float, reading) -> tuple[int | None, float | None, float | None]:
        found = episodes_per_arm(utilities, delta, cap, cfg, reading)
        return (None, None, None) if found is None else (found[0], found[1], 2 * found[0] / throughput)

    return [Row(d, *read(d, measure), *read(d, assurance)) for d in cfg["deltas"]]


def verdict(rows: Sequence[Row], cfg: dict, assured: bool = False) -> str:
    """FIT if fit_delta is detectable within the budget, MARGINAL if only marginal_delta is, UNFIT otherwise. Detected is
    read under the expected reading, which is the committed verdict; `assured` reads the assurance reading instead."""
    detected = {r.delta for r in rows if (r.assured_episodes_per_arm if assured else r.episodes_per_arm) is not None}
    if cfg["fit_delta"] in detected:
        return "FIT"
    return "MARGINAL" if cfg["marginal_delta"] in detected else "UNFIT"
