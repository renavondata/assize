"""The pilot (brief 1 section 5): the incumbent's episodes through `evaluate()`, its throughput, and the report.

`play` asks for the pilot's episodes in requests of `[requests] episodes`, each under its own request_id, until every
episode is recorded or the wall-clock cap passes, whichever binds first. The cap is checked before each request; an
episode under way when it passes is finished and recorded, never cut. Reaching the cap first, a request refused, or a
request returning other than the episodes it asked for, stops the pilot: a stop-and-report boundary, never a smaller
pilot, so a stopped report carries no verdict. A pilot whose wall-clock passed the cap during its last request is
stopped the same way by `report`: every episode is recorded, but not within the cap.

`report` reads everything off the judge's records, every recorded episode included whatever its termination, and states
each denominator:
- the incumbent's per-episode utilities, their termination codes and achievement sets, and Hafner's (2022) score beside
  them (never as the utility);
- per declared target, the predictive floor's log-loss per scored step (+inf if any step was, never clipped), its
  missing steps, and its calibration: the reliability tables and entropies summed over episodes (A4 item 3);
- compute per episode, measured by the judge, and its price;
- throughput: recorded episodes per wall-clock second of the whole pilot, container starts, seed issuance and ledger
  writes included, since that is what evaluating a candidate costs on this host;
- the time-to-learn table at that throughput (`timetolearn.py`), its stated assumption, the note that a random agent's
  variance is a weak proxy for a competent agent's, and the verdict FIT, MARGINAL or UNFIT;
- the proposer every record carries, which the judge took from the registering credential (A4 item 2). Records
  carrying more than one proposer, judge hash or image are not one pilot: the report says so and gives no verdict."""

from __future__ import annotations

import functools
import json
import math
import time
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from pilot import timetolearn

ASSUMPTION = ("a candidate's per-episode utility is distributed as the incumbent's shifted by delta achievements per "
              "episode")
PROXY = "a random agent's variance is a weak proxy for that of a competent agent"
INFINITE = "+inf"


@dataclass(frozen=True)
class Played:
    records: tuple[dict, ...]
    requests: tuple[dict, ...]  # per request: request_id, episodes asked, records returned, wall_s
    wall_s: float
    stopped: str | None  # why the pilot stopped before every episode was recorded; None if it did not


def sizes(total: int, per: int) -> list[int]:
    """The episodes of each request: `per` each, the last taking what remains."""
    return [min(per, total - i) for i in range(0, total, per)]


def play(ask: Callable[[str, int], Sequence[dict]], pilot_id: str, cfg: Mapping, *,
         refusals: tuple[type[BaseException], ...] = (), clock: Callable[[], float] = time.monotonic,
         progress: Callable[[Sequence[dict]], None] = lambda records: None) -> Played:
    """Ask `ask(request_id, n)` for the pilot's episodes, request by request, until all are recorded or the cap
    passes. `progress` receives each request's records as they arrive."""
    total, cap = cfg["pilot"]["episodes"], cfg["pilot"]["cap_s"]
    start = clock()
    records: list[dict] = []
    requests: list[dict] = []
    stopped = None
    for k, n in enumerate(sizes(total, cfg["requests"]["episodes"])):
        if clock() - start >= cap:
            stopped = f"cap: {cap} s reached with {len(records)} of {total} episodes recorded"
            break
        rid = f"pilot-{pilot_id}-{k}"
        began = clock()
        try:
            got = list(ask(rid, n))
        except refusals as e:
            stopped = f"refused: request {rid}: {e}"
            break
        records += got
        requests.append({"request_id": rid, "episodes": n, "records": len(got), "wall_s": clock() - began})
        progress(got)
        if len(got) != n:
            stopped = f"request {rid} asked for {n} episodes and returned {len(got)} records"
            break
    return Played(tuple(records), tuple(requests), clock() - start, stopped)


def _distinct(records: Sequence[dict], key: str) -> list:
    return [json.loads(s) for s in sorted({json.dumps(r.get(key), sort_keys=True) for r in records})]


def _add(a: list, b: list) -> list:
    """Elementwise sum of two equally shaped nested lists of numbers."""
    return [_add(x, y) for x, y in zip(a, b, strict=True)] if isinstance(a, list) else a + b


def prediction(records: Sequence[dict], name: str) -> dict:
    """Target `name`'s log-loss over every scored step of every episode: the finite sum over the scored steps, or +inf
    if any step was infinite; with the counts of scored, missing and infinite steps."""
    rows = [r["prediction"][name] for r in records]
    scored, infinite = sum(x["scored"] for x in rows), sum(x["infinite"] for x in rows)
    finite = math.fsum(x["finite_sum"] for x in rows)
    return {"scored": scored, "missing": sum(x["missing"] for x in rows), "infinite": infinite,
            "finite_sum": finite,
            "log_loss_per_step": INFINITE if infinite else (finite / scored if scored else None)}


def calibration(records: Sequence[dict], name: str, scored: int) -> dict:
    """Target `name`'s reliability table and predicted entropy, summed over episodes (they add, `scoring.py`)."""
    rows = [r["calibration"][name] for r in records]
    tables = [x["reliability"] for x in rows]
    if len({t["bins"] for t in tables}) > 1:
        raise ValueError(f"{name}: reliability tables of differing bins")
    entropy = math.fsum(x["entropy_sum"] for x in rows)
    summed = {k: functools.reduce(_add, (t[k] for t in tables)) for k in ("n", "hits", "p_sum")} if tables else {}
    return {"entropy_sum": entropy, "mean_entropy": entropy / scored if scored else None,
            "reliability": {"bins": tables[0]["bins"], **summed} if tables else None}


def _stats(xs: Sequence[float]) -> dict:
    n = len(xs)
    mean = math.fsum(xs) / n if n else None
    return {"n": n, "sum": math.fsum(xs), "mean": mean, "min": min(xs, default=None), "max": max(xs, default=None)}


def compute(records: Sequence[dict]) -> dict:
    """The judge's measured compute and its price, per episode, over every record."""
    c = [r["compute"] for r in records]
    return {"cpu_s": _stats([x["cpu_s"] for x in c]), "wall_s": _stats([x["wall_s"] for x in c]),
            "unmeasured_s": _stats([x["unmeasured_s"] for x in c]),
            "peak_memory_bytes": _stats([x["peak_memory_bytes"] for x in c]),
            "peak_memory_scope": sorted({x["peak_memory_scope"] for x in c}),
            "price_total": _stats([r["price"]["total"] for r in records])}


def report(played: Played, cfg: Mapping, targets: Sequence[str], components: Sequence[str],
           hafner: Callable[[Sequence[Sequence[str]], Sequence[str]], float], *, evidence: bool) -> dict:
    """The pilot report of `played`: see the module docstring. `evidence` is False for a smoke run, whose report is
    never evidence for a verdict."""
    rs = played.records
    n = len(rs)
    utilities = [r["utility"] for r in rs]
    one = {k: _distinct(rs, k) for k in ("proposer", "judge_sha256", "image", "world", "runtime")}
    several = [k for k, v in one.items() if len(v) != 1]
    throughput = n / played.wall_s if played.wall_s > 0 else None
    ttl = cfg["time_to_learn"]
    cap = cfg["pilot"]["cap_s"]
    overrun = f"cap: {cap} s passed during the last request, at {played.wall_s:.1f} s" if played.wall_s > cap else None
    stopped = played.stopped or overrun or (f"records carry {', '.join(f'{len(one[k])} {k}' for k in several)}"
                                            if several else None)
    rows = timetolearn.table(utilities, throughput, ttl) if stopped is None else []
    preds = {t: prediction(rs, t) for t in targets}
    return {
        "verdict": f"STOPPED: {stopped}" if stopped else timetolearn.verdict(rows, ttl),
        "evidence": evidence,
        "episodes": {"requested": cfg["pilot"]["episodes"], "recorded": n, "cap_s": cfg["pilot"]["cap_s"],
                     "terminations": dict(sorted(Counter(r["termination"] for r in rs).items()))},
        **{k: (v[0] if len(v) == 1 else v) for k, v in one.items()},
        "utility": {**_stats(utilities), "counts": {str(u): c for u, c in sorted(Counter(utilities).items())},
                    "per_episode": utilities},
        "achievements": {c: sum(c in r["achievements"] for r in rs) for c in components},
        "hafner_score": hafner([r["achievements"] for r in rs], components) if n else None,
        "prediction": preds,
        "calibration": {t: calibration(rs, t, preds[t]["scored"]) for t in targets},
        "compute": compute(rs),
        "wall_s": played.wall_s,
        "throughput_episodes_per_s": throughput,
        "requests": list(played.requests),
        "time_to_learn": {"assumption": ASSUMPTION, "note": PROXY, "config": dict(ttl),
                          "rows": [{"delta": r.delta, "episodes_per_arm": r.episodes_per_arm, "measure": r.measure,
                                    "wall_s": r.wall_s} for r in rows]},
    }


def render(rep: Mapping) -> str:
    """The report as terse Markdown, verdict first."""
    e, u, c = rep["episodes"], rep["utility"], rep["compute"]
    lines = [
        f"VERDICT: {rep['verdict']}" + ("" if rep["evidence"] else " (smoke: not evidence)"),
        f"proposer: {json.dumps(rep['proposer'], sort_keys=True)}",
        f"world {rep['world']}; runtime {rep['runtime']}; image {rep['image']}; judge_sha256 {rep['judge_sha256']}",
        f"episodes: {e['recorded']} recorded of {e['requested']} requested (cap {e['cap_s']} s); "
        f"terminations {e['terminations']}",
        f"utility over {u['n']} episodes: mean {u['mean']}, min {u['min']}, max {u['max']}; counts {u['counts']}",
        f"Hafner score (reported beside the utility, never as it): {rep['hafner_score']}",
        f"throughput: {rep['throughput_episodes_per_s']} episodes/s over {rep['wall_s']:.1f} s wall-clock, "
        f"{len(rep['requests'])} requests",
        f"compute per episode over {c['cpu_s']['n']}: cpu_s mean {c['cpu_s']['mean']}, wall_s mean "
        f"{c['wall_s']['mean']}, peak_memory_bytes max {c['peak_memory_bytes']['max']}, price mean "
        f"{c['price_total']['mean']}",
        "predictive floor, per declared target: log-loss per scored step (scored, missing, infinite); mean entropy",
        *(f"  {t}: {p['log_loss_per_step']} ({p['scored']}, {p['missing']}, {p['infinite']}); "
          f"{rep['calibration'][t]['mean_entropy']}" for t, p in rep["prediction"].items()),
        f"time-to-learn. Assumption: {rep['time_to_learn']['assumption']}. Note: {rep['time_to_learn']['note']}.",
        "  delta | episodes per arm | measure | wall-clock s (both arms)",
        *(f"  {r['delta']} | {r['episodes_per_arm']} | {r['measure']} | {r['wall_s']}"
          for r in rep["time_to_learn"]["rows"]),
    ]
    return "\n".join(lines) + "\n"
