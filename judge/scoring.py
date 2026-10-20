"""Prediction validation and log-loss scoring (brief 1 section 2).

A step reply's `prediction` maps declared targets to probability lists aligned with each target's declared support.
One that names an undeclared target, has the wrong length, puts a negative probability on a value, or does not sum to one
is not a prediction: the reply is invalid and the episode ends `invalid_reply` (brief 2, audit 8aae43c8c792 finding 5:
[1.5, -0.5] sums to one, the log of its second entry is undefined and its first scores a loss of -ln 1.5). No upper bound
is checked apart from the sum: entries that are all non-negative and sum to within the tolerance below are each at most
1 + len(support) machine epsilons, so a loss is never below -ln of that, the rounding P27 admits. The sum is checked to within `len(support)` machine epsilons, the
rounding a candidate normalising in double precision can accumulate; the bound is derived, not tuned.

Each declared target is scored at every completed step against the World's next observation of its field, as the
negative natural logarithm of the probability put on the realised value. Zero probability scores +inf, counted, never
clipped. A target the reply omits is recorded missing, never imputed. Per episode and target, `scored + missing` is the
episode's step count.

Beside log-loss, each declared target is calibrated per episode (brief 1 A4 item 3) from the distributions the
candidate predicted: the sum and mean of their entropies in nats, and a reliability table over the declared support.
Each support value's row counts, per bin of predicted probability, the scored steps that put a probability in that bin
on the value, how many of them realised it, and the sum of those probabilities. Every scored step enters every row once,
an infinite-loss step included, so each row's counts sum to `scored`; a missing step enters nothing, and a target with
no scored step has no mean entropy, never an imputed one. Tables, counts and sums add across episodes; nothing is
pooled across targets.

Two candidates' log-losses on a target are compared per step over every completed step, `scored + missing`, never
over the scored steps alone (brief 2 A2, L2a obligation 11; review c2a87f6478ad F4). The record still holds a missing
step as missing; the comparison prices it at +inf, the loss of a prediction putting nothing on the realised value. That
price is derived, not chosen: it is the supremum of the log-loss, so omitting is never better than any prediction, and
any finite price c would pay a candidate to omit wherever its expected loss exceeds c. One candidate beats another only
if its per-step log-loss is strictly lower; two infinite ones tie, and a target with no step compares with nothing."""

from __future__ import annotations

import bisect
import math
import sys
from collections.abc import Mapping, Sequence

# JSON has no infinity; a log-loss that is infinite is recorded as this string, beside its count of infinite steps.
INFINITE = "+inf"


def tolerance(n: int) -> float:
    return n * sys.float_info.epsilon


def invalid(prediction: Mapping[str, Sequence[float]], targets: Sequence[Mapping]) -> str | None:
    """Why `prediction` is not a distribution over the declared support of every target it names, or None."""
    declared = {t["name"]: t for t in targets}
    for name, p in prediction.items():
        if name not in declared:
            return f"undeclared target {name!r}"
        n = len(declared[name]["support"])
        if len(p) != n:
            return f"{name}: {len(p)} probabilities for a support of {n}"
        if not all(x >= 0 for x in p):
            return f"{name}: a negative probability: {list(p)!r}"
        if not abs(math.fsum(p) - 1) <= tolerance(n):
            return f"{name}: probabilities sum to {math.fsum(p)!r}"
    return None


def loss(p: Sequence[float], support: Sequence, realised) -> float:
    """-ln of the probability `p` puts on `realised`: +inf when that is zero."""
    q = p[support.index(realised)]
    return math.inf if q == 0 else -math.log(q)


def step_losses(prediction: Mapping[str, Sequence[float]], targets: Sequence[Mapping],
                observation: Mapping) -> dict[str, float | None]:
    """Each declared target's log-loss against `observation`, the World's next one; None where the target is missing."""
    return {t["name"]: (loss(prediction[t["name"]], t["support"], observation[t["field"]])
                        if t["name"] in prediction else None)
            for t in targets}


def summary(steps: Sequence[Mapping[str, float | None]], targets: Sequence[Mapping]) -> dict[str, dict]:
    """Per declared target over an episode's steps: how many were scored, missing and infinite, the sum of the
    finite losses, and the log-loss, which is that sum unless any step was infinite."""

    def one(name: str) -> dict:
        losses = [s[name] for s in steps]
        scored = [x for x in losses if x is not None]
        finite = [x for x in scored if x != math.inf]
        infinite = len(scored) - len(finite)
        return {"scored": len(scored), "missing": len(losses) - len(scored), "infinite": infinite,
                "finite_sum": math.fsum(finite), "log_loss": INFINITE if infinite else math.fsum(finite)}

    return {t["name"]: one(t["name"]) for t in targets}


def per_step(row: Mapping) -> float | None:
    """The log-loss per completed step of a `summary` row, or of rows added across episodes: +inf if any step was
    infinite or missing, else the finite sum over `scored + missing`; None if there was no step."""
    steps = row["scored"] + row["missing"]
    if not steps:
        return None
    return math.inf if row["infinite"] or row["missing"] else row["finite_sum"] / steps


def beats(a: Mapping, b: Mapping) -> bool:
    """Whether row `a`'s log-loss per completed step is strictly below row `b`'s, on the same target."""
    pa, pb = per_step(a), per_step(b)
    return pa is not None and pb is not None and pa < pb


def step_predictions(prediction: Mapping[str, Sequence[float]], targets: Sequence[Mapping],
                     observation: Mapping) -> dict[str, tuple[Sequence[float], int] | None]:
    """Each declared target's predicted distribution and the index in its support of the value `observation`, the
    World's next one, realised; None where the target is missing."""
    return {t["name"]: None if t["name"] not in prediction
            else (prediction[t["name"]], t["support"].index(observation[t["field"]]))
            for t in targets}


def entropy(p: Sequence[float]) -> float:
    """The entropy of `p` in nats, with 0 ln 0 = 0."""
    return -math.fsum(x * math.log(x) for x in p if x > 0)


def bin_of(q: float, bins: int) -> int:
    """The bin of probability `q` among `bins` equal bins of [0, 1]: bin b covers [b/bins, (b+1)/bins), the last
    includes 1, each edge the double `b / bins`. So `q` is compared with the edges themselves, never rounded first:
    `int(q * bins)` puts 0.3*3 = 0.8999999999999999 at 9 (brief 2 A2, L2a obligation 14; review 7e18816c626e F2)."""
    return bisect.bisect_right([b / bins for b in range(1, bins)], q)


def calibration(steps: Sequence[Mapping[str, tuple[Sequence[float], int] | None]], targets: Sequence[Mapping],
                bins: int) -> dict[str, dict]:
    """Per declared target over an episode's steps: the sum and mean of the predicted entropies over its scored steps,
    and its reliability table, `n`, `hits` and `p_sum` each indexed by support value, then by bin."""

    def one(t: Mapping) -> dict:
        scored = [s[t["name"]] for s in steps if s[t["name"]] is not None]
        cells = [[[] for _ in range(bins)] for _ in t["support"]]
        for p, realised in scored:
            for v, q in enumerate(p):
                cells[v][bin_of(q, bins)].append((q, v == realised))
        entropy_sum = math.fsum(entropy(p) for p, _ in scored)
        return {"entropy_sum": entropy_sum, "mean_entropy": entropy_sum / len(scored) if scored else None,
                "reliability": {"bins": bins,
                                "n": [[len(c) for c in row] for row in cells],
                                "hits": [[sum(hit for _, hit in c) for c in row] for row in cells],
                                "p_sum": [[math.fsum(q for q, _ in c) for c in row] for row in cells]}}

    return {t["name"]: one(t) for t in targets}
