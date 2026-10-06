"""Prediction validation and log-loss scoring (brief 1 section 2).

A step reply's `prediction` maps declared targets to probability lists aligned with each target's declared support.
One that names an undeclared target, has the wrong length, or does not sum to one is not a prediction: the reply is
invalid and the episode ends `invalid_reply`. The sum is checked to within `len(support)` machine epsilons, the
rounding a candidate normalising in double precision can accumulate; the bound is derived, not tuned.

Each declared target is scored at every completed step against the World's next observation of its field, as the
negative natural logarithm of the probability put on the realised value. Zero probability scores +inf, counted, never
clipped. A target the reply omits is recorded missing, never imputed. Per episode and target, `scored + missing` is the
episode's step count."""

from __future__ import annotations

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
