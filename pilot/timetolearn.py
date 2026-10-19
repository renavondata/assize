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

Both readings are Monte Carlo means over `experiments`, drawn on a stream of their own per m, so neither is monotone in
m (review 0d5e9ec F2): m* is found by reading every m from 1 in turn, and each row carries the standard error of the
reading at m*, at m* - 1 and at the episodes per arm the budget affords. A delta's detection is settled only if the
reading at the budget lies more than one standard error from `mass` on the side of the detection; a verdict that reads
an unsettled delta is reported as within Monte Carlo error, not read off one draw.
"""

from __future__ import annotations

import functools
import json
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
    # Monte Carlo standard errors (review 0d5e9ec F2): of the reading at m*; the reading and its error at m* - 1 (None
    # when m* is 1 or not found); and at the episodes per arm the budget affords (None when it affords none).
    se: float | None = None
    below: float | None = None
    below_se: float | None = None
    at_budget: float | None = None
    at_budget_se: float | None = None
    assured_se: float | None = None
    assured_below: float | None = None
    assured_below_se: float | None = None
    assured_at_budget: float | None = None
    assured_at_budget_se: float | None = None


def config(path: Path = CONFIG) -> dict:
    with path.open("rb") as f:
        return tomllib.load(f)


def _means(rng: np.random.Generator, counts: np.ndarray, values: np.ndarray, draws: int) -> np.ndarray:
    """Bayesian-bootstrap draws of each experiment's mean: Dirichlet(1, ..., 1) over its episodes, which grouped by
    value is a Gamma(count) weight per value. Shape (experiments, draws)."""
    g = rng.standard_gamma(np.broadcast_to(counts[:, None, :], (counts.shape[0], draws, counts.shape[1])))
    return (g @ values) / g.sum(axis=2)


def masses(utilities: Sequence[float], delta: float, m: int, cfg: dict) -> np.ndarray:
    """Per simulated experiment of m episodes per arm, the posterior mass on candidate mean > incumbent mean. A pure
    function of its arguments, so it is computed once per argument set: the search reads every m, and both readings
    and the standard errors read the same masses."""
    return _masses(tuple(sorted(Counter(utilities).items())), delta, m, json.dumps(cfg, sort_keys=True))


@functools.lru_cache(maxsize=None)
def _masses(counted: tuple[tuple[float, int], ...], delta: float, m: int, frozen: str) -> np.ndarray:
    cfg = json.loads(frozen)
    tally = dict(counted)
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

    out = np.concatenate([chunk(min(CHUNK, total - i)) for i in range(0, total, CHUNK)])
    out.setflags(write=False)  # shared by every caller of the cache
    return out


def measure(utilities: Sequence[float], delta: float, m: int, cfg: dict) -> float:
    """The expected reading: the posterior mass on the correct sign, averaged over simulated experiments."""
    return math.fsum(masses(utilities, delta, m, cfg).tolist()) / cfg["experiments"]


def assurance(utilities: Sequence[float], delta: float, m: int, cfg: dict) -> float:
    """The assurance reading: the fraction of simulated experiments whose posterior mass on the correct sign reaches
    cfg['mass'] (an experiment at the mass exactly counts)."""
    return int((masses(utilities, delta, m, cfg) >= cfg["mass"]).sum()) / cfg["experiments"]


def standard_error(utilities: Sequence[float], delta: float, m: int, cfg: dict,
                   reading: Callable[[Sequence[float], float, int, dict], float] = measure) -> float:
    """The Monte Carlo standard error of `reading` (`measure` or `assurance`) at m: the sample standard deviation over
    experiments of the quantity it averages (an experiment's mass, or whether that mass reaches cfg['mass']), over the
    square root of their number. Infinite when one experiment leaves it unestimated."""
    x = masses(utilities, delta, m, cfg)
    per = {measure: x, assurance: (x >= cfg["mass"]).astype(float)}[reading]
    n = cfg["experiments"]
    return float(np.std(per, ddof=1)) / math.sqrt(n) if n > 1 else math.inf


def affordable(throughput: float, cfg: dict) -> int:
    """Episodes per arm the budget affords at `throughput` episodes per wall-clock second: both arms are run."""
    return math.floor(cfg["budget_s"] * throughput / 2)


def episodes_per_arm(utilities: Sequence[float], delta: float, cap: int, cfg: dict,
                     reading: Callable[[Sequence[float], float, int, dict], float] = measure) -> tuple[int, float] | None:
    """The smallest m <= cap whose reading (`measure`, the committed one, or `assurance`) reaches cfg['mass'], with that
    reading's value there. The reading is not monotone in m (each m draws its own stream), so every m from 1 is read in
    turn until one reaches the mass: a doubling or bisection search returns some crossing, not the smallest."""
    readings = ((m, reading(utilities, delta, m, cfg)) for m in range(1, cap + 1))
    return next(((m, x) for m, x in readings if x >= cfg["mass"]), None)


def table(utilities: Sequence[float], throughput: float, cfg: dict) -> list[Row]:
    """One row per configured delta: episodes per arm, the reading there, and the wall-clock both arms take, under the
    expected reading (committed) and, beside it, the assurance reading; then each reading's standard errors."""
    cap = affordable(throughput, cfg)

    def read(delta: float, reading) -> tuple[int | None, float | None, float | None]:
        found = episodes_per_arm(utilities, delta, cap, cfg, reading)
        return (None, None, None) if found is None else (found[0], found[1], 2 * found[0] / throughput)

    def errors(delta: float, m: int | None, reading) -> tuple[float | None, ...]:
        """The standard error at m*; the reading and its error at m* - 1; the same at the budget."""
        at = lambda k: (reading(utilities, delta, k, cfg), standard_error(utilities, delta, k, cfg, reading))
        return (None if m is None else standard_error(utilities, delta, m, cfg, reading),
                *(at(m - 1) if m is not None and m > 1 else (None, None)),
                *(at(cap) if cap >= 1 else (None, None)))

    def row(delta: float) -> Row:
        expected, assured = read(delta, measure), read(delta, assurance)
        return Row(delta, *expected, *assured, *errors(delta, expected[0], measure), *errors(delta, assured[0], assurance))

    return [row(d) for d in cfg["deltas"]]


def _reading(r: Row, assured: bool) -> tuple[int | None, float | None, float | None]:
    """A row's episodes per arm and its reading and standard error at the budget, under the reading `assured` names."""
    if assured:
        return r.assured_episodes_per_arm, r.assured_at_budget, r.assured_at_budget_se
    return r.episodes_per_arm, r.at_budget, r.at_budget_se


def verdict(rows: Sequence[Row], cfg: dict, assured: bool = False) -> str:
    """FIT if fit_delta is detectable within the budget, MARGINAL if only marginal_delta is, UNFIT otherwise. Detected is
    read under the expected reading, which is the committed verdict; `assured` reads the assurance reading instead."""
    detected = {r.delta for r in rows if _reading(r, assured)[0] is not None}
    if cfg["fit_delta"] in detected:
        return "FIT"
    return "MARGINAL" if cfg["marginal_delta"] in detected else "UNFIT"


def settled(r: Row, cfg: dict, assured: bool = False) -> bool:
    """Whether a row's detection stands outside the Monte Carlo error at the budget (review 0d5e9ec F2): detected and
    the reading at the budget more than one standard error above cfg['mass'], or not detected and more than one below.
    A budget affording no episode detects nothing and has no error."""
    m, x, se = _reading(r, assured)
    if x is None:
        return m is None
    return x - se > cfg["mass"] if m is not None else x + se < cfg["mass"]


def within_error(rows: Sequence[Row], cfg: dict, assured: bool = False) -> tuple[float, ...]:
    """The deltas the verdict reads whose detection is not `settled`: fit_delta, and marginal_delta unless fit_delta is
    settled as detected. Empty if and only if the verdict is not within Monte Carlo error."""
    by = {r.delta: r for r in rows}
    fit = by[cfg["fit_delta"]]
    fit_stands = settled(fit, cfg, assured) and _reading(fit, assured)[0] is not None
    read = (fit,) if fit_stands else (fit, by[cfg["marginal_delta"]])
    return tuple(r.delta for r in read if not settled(r, cfg, assured))
