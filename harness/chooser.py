"""The chooser (instruction #111 Parts B and C): the next item as the forecast of Guy's pick.

Every sovereign entrant forecasts, before the chooser acts, a distribution over the declared candidates (a `guy_picks`
row of the forecast ledger, sealed by its SHA-256). The elected mixture is Fixed Share over the entrants' log-loss on the
rounds Guy has resolved (by the labels `next` and `later`, or by silence after a declared exposure); the chooser takes
its argmax. `fixed-order` is always an entrant and is the choice until a sovereign act follows the last change-point.
Pure functions below; the git readers and the command line follow them."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from harness import claims, ledger
from harness.claims import Finding

SOVEREIGN = "sovereign"  # the key of harness/entrants.toml
FIXED, PRIORITIES, MIXTURE = "fixed-order", "priorities-literal", "mixture"
REGIMES = (FIXED, "chooser")  # Part C: the two regimes of the switchback
SEED_PATH = "reports/switchback-seed.txt"

Dist = Mapping[str, float]
Pick = tuple[str, str]  # ("item", X): Guy picks X; ("not", X): Guy puts X later, picking none in particular


def point(candidates: Sequence[str], at: str) -> dict[str, float]:
    return {c: 1.0 if c == at else 0.0 for c in candidates}


def fixed_order(candidates: Sequence[str]) -> dict[str, float]:
    """A1.5's order, as the caller lists the candidates: all the mass on the first."""
    return point(candidates, candidates[0])


def ordering_of(body: str) -> list[str]:
    """A `priorities` issue read as an ordering: its list items (`1.`, `-` or `*`), in order, each trimmed."""
    return [m.group(1).strip() for m in re.finditer(r"^\s*(?:\d+[.)]|[-*])\s+(\S.*)$", body, re.M)]


def priorities_literal(candidates: Sequence[str], ordering: Sequence[str]) -> dict[str, float] | None:
    """All the mass on the first candidate the ordering names, in the ordering's order; None (it abstains) when there
    is no ordering or it names no candidate."""
    named = [c for o in ordering for c in candidates if o == c or o.startswith(c + " ") or o.startswith(c + ":")]
    return point(candidates, named[0]) if named else None


def likelihood(dist: Dist, pick: Pick) -> float:
    kind, x = pick
    m = dist.get(x, 0.0)
    return m if kind == "item" else 1.0 - m


def loss(dist: Dist, pick: Pick) -> float:
    """Log-loss of the distribution at the pick; +inf, counted and never clipped, when it gave the pick no mass."""
    got = likelihood(dist, pick)
    return math.inf if got <= 0 else -math.log(got)


@dataclass(frozen=True)
class Round:
    """One resolved choice: each entrant's forecast, Guy's pick, when, and whether it was a sovereign act (a label he
    applied) rather than silence."""
    ts: str
    dists: Mapping[str, Dist]
    pick: Pick
    act: bool


def derived_alpha(switches: int, rounds: int) -> float:
    """Fixed Share's share parameter, derived from its switching-regret bound and not tuned: the bound (Herbster and
    Warmuth 1998, Theorem 1 in the log-loss form of Vovk 1999, for K experts, T rounds and a comparator with s
    switches) is smallest at alpha = s / (T - 1), the comparator's switching rate. s is the number of declared
    change-points, at least 1, because the election begins at one; T - 1 is at least 1. Capped at 1."""
    return min(1.0, max(1, switches) / max(1, rounds - 1))


def weights(entrants: Sequence[str], rounds: Sequence[Round], alpha: float) -> dict[str, float]:
    """Fixed Share over `entrants` (weights sum to 1): per round, every entrant's weight is multiplied by exp(-loss of
    its forecast at Guy's pick), renormalised, then (1 - alpha) of it kept and alpha / K shared equally. An entrant
    that abstained takes the loss of the mixture of those that did not; a round on which every entrant gave the pick
    no mass leaves the weights alone before the share."""
    k = len(entrants)
    w = {e: 1.0 / k for e in entrants}
    for r in rounds:
        live = [e for e in entrants if e in r.dists]
        if not live:
            continue
        z = sum(w[e] for e in live) or 1.0
        mix = sum(w[e] / z * likelihood(r.dists[e], r.pick) for e in live)
        mixed = math.inf if mix <= 0 else -math.log(mix)
        v = {e: w[e] * math.exp(-(loss(r.dists[e], r.pick) if e in r.dists else mixed)) for e in entrants}
        total = sum(v.values())
        v = v if total > 0 else w
        total = sum(v.values())
        w = {e: (1 - alpha) * v[e] / total + alpha / k for e in entrants}
    return w


def mixture(candidates: Sequence[str], dists: Mapping[str, Dist], w: Mapping[str, float]) -> dict[str, float]:
    """The weighted mixture of the entrants that forecast this round, weights renormalised over them."""
    live = list(dists)
    z = sum(w.get(e, 0.0) for e in live)
    share = {e: w.get(e, 0.0) / z if z > 0 else 1.0 / len(live) for e in live}
    return {c: sum(share[e] * dists[e].get(c, 0.0) for e in live) for c in candidates}


def argmax(dist: Dist, candidates: Sequence[str]) -> str:
    """The candidate with most mass; ties go to the earlier in the caller's order (A1.5's)."""
    return max(candidates, key=lambda c: (dist.get(c, 0.0), -candidates.index(c)))


@dataclass(frozen=True)
class Choice:
    chose: str
    dist: Mapping[str, float]
    weights: Mapping[str, float]
    via: str  # FIXED or MIXTURE


def choose(candidates: Sequence[str], dists: Mapping[str, Dist], rounds: Sequence[Round], change_points: Sequence[str],
           regime: str) -> Choice:
    """Under the fixed-order regime, or when no sovereign act has been recorded since the last declared change-point
    (a layer boundary or a signed instruction), the choice is `fixed-order`'s; otherwise the argmax of the Fixed Share
    mixture of the entrants. `dists` are this round's forecasts, one per entrant that made one; it holds FIXED."""
    entrants = sorted({e for r in rounds for e in r.dists} | set(dists))
    w = weights(entrants, rounds, derived_alpha(len(change_points), len(rounds)))
    mix = mixture(candidates, dists, w)
    last = max(change_points, default="")
    acts = [r for r in rounds if r.act and r.ts > last]
    if regime == FIXED or not acts:
        return Choice(argmax(dists[FIXED], candidates), mix, w, FIXED)
    return Choice(argmax(mix, candidates), mix, w, MIXTURE)


# ------------------------------------------------------------------------------ the sealed forecast and the STATUS line

def forecast_hash(args: Mapping) -> str:
    """The SHA-256 of a `guy_picks` forecast's arguments (all but `hash`), as sorted compact JSON."""
    body = {k: v for k, v in args.items() if k != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def round_id(candidates: Sequence[str], ts: str) -> str:
    return hashlib.sha256(("|".join(candidates) + "@" + ts).encode()).hexdigest()[:12]


def pick_row(entrant: str, candidates: Sequence[str], dist: Dist, chose: str, shown: str, until: str, rid: str,
             ts: str, sha_before: str, proposer: Mapping) -> dict:
    """A `guy_picks` forecast row: `chose` is the entrant's own argmax, `shown` the item the chooser acted on (what
    Guy's silence confirms). `p` is the mass the entrant gives `chose` (0 to 1, ends included: a fixed order is
    certain; claims._forecast_findings admits that for this type)."""
    args = {"candidates": list(candidates), "dist": {c: dist.get(c, 0.0) for c in candidates}, "entrant": entrant,
            "chose": chose, "shown": shown, "until": until, "round": rid, "exposure": "seen"}
    args["hash"] = forecast_hash(args)
    claim = f"Guy's next pick among {', '.join(candidates)} (round {rid}, entrant {entrant})"
    return {"id": claims.forecast_id(claim, ts), "ts": ts, "proposer": dict(proposer), "sha_before": sha_before,
            "claim": claim, "p": dist.get(chose, 0.0), "resolves_by": until, "type": "guy_picks", "args": args}


CHOSE = re.compile(r"^chose: (?P<chose>.+?) over (?P<over>.+?) — entrants (?P<entrants>.+?) — forecast "
                   r"(?P<hash>[0-9a-f]{64}) — regime (?P<regime>\S+)\s*$", re.M)


def chose_line(chose: str, candidates: Sequence[str], w: Mapping[str, float], hash_: str, regime: str) -> str:
    named = ", ".join(f"{e}={w[e]:.3f}" for e in sorted(w))
    return f"chose: {chose} over {', '.join(candidates)} — entrants {named} — forecast {hash_} — regime {regime}"


# ---------------------------------------------------------------------------------------------- Part C: the switchback

def regime_at(seed: str, i: int) -> str:
    """The i-th scored choice's regime: the seed fixes the first (the parity of its SHA-256) and the rest alternate."""
    first = int(hashlib.sha256(seed.encode()).hexdigest(), 16) % 2
    return REGIMES[(first + i) % 2]


def switchback_findings(seed: str | None, lines: Sequence[Mapping]) -> list[Finding]:
    """Each parsed `chose:` line (in the order the choices were made) names the regime the committed seed assigns its
    index; a choice with no committed seed is unseeded."""
    if not lines:
        return []
    if seed is None:
        return [Finding("chose:", "unseeded", "a choice was made with no committed switchback seed")]
    return [Finding(f"chose #{i + 1}", "regime", f"names regime {line['regime']!r}; the seed assigns {regime_at(seed, i)!r}")
            for i, line in enumerate(lines) if line["regime"] != regime_at(seed, i)]


# ------------------------------------------------------------------------------------------------------- git readers

def _log(repo: Path, head: str, needle: str, glob: str) -> list[str]:
    """Commits reachable from `head`, oldest first, whose diff adds or removes `needle` under `glob`."""
    return claims._git(repo, "log", "--reverse", "--topo-order", "--format=%H", f"-S{needle}", head, "--",
                       glob).split()


def sealed_before(repo: Path, row_commit: str | None, act_commit: str | None) -> bool:
    """The forecast row is first present in a strict ancestor of the commit where the chooser's act first appears."""
    if row_commit is None or act_commit is None or row_commit == act_commit:
        return False
    return subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", row_commit, act_commit],
                          capture_output=True).returncode == 0


def chose_history(repo: Path, head: str = "HEAD") -> list[tuple[str, dict]]:
    """Every distinct `chose:` line in any STATUS in history, in the order of the commit that first has it: (commit,
    parsed line)."""
    seen: dict[str, tuple[str, dict]] = {}
    commits = claims._git(repo, "log", "--reverse", "--topo-order", "--format=%H", head, "--",
                          "reports/L*/STATUS.md").split()
    for c in commits:
        for path in claims._git(repo, "diff-tree", "--root", "--no-commit-id", "--name-only", "-r", "-m", "--first-parent", c,
                                "--", "reports/L*/STATUS.md").split():
            for m in CHOSE.finditer(claims._git(repo, "show", f"{c}:{path}")):
                seen.setdefault(m["hash"], (c, m.groupdict()))
    return list(seen.values())


def chose_findings(repo: Path, head: str = "HEAD") -> list[Finding]:
    """For every `chose:` line in history: its forecast row exists, was committed before the line did (the seal), and
    lists exactly the candidates the line does; the line names one of them."""
    rows = {r.get("args", {}).get("hash"): r for r in ledger.ledger_rows(repo, head)
            if r.get("type") == "guy_picks" and "claim" in r}
    found: list[Finding] = []
    for act_commit, line in chose_history(repo, head):
        where = f"chose {line['hash'][:12]} at {act_commit[:12]}"
        over = [c.strip() for c in line["over"].split(",")]
        row = rows.get(line["hash"])
        first = _log(repo, head, line["hash"], "reports/L*/forecasts.jsonl")
        if row is None or not first:
            found.append(Finding(where, "no_forecast", "no `guy_picks` row carries the cited hash"))
            continue
        if not sealed_before(repo, first[0], act_commit):
            found.append(Finding(where, "late", f"the forecast is first present at {first[0][:12]}, not before the act"))
        if over != row["args"]["candidates"]:
            found.append(Finding(where, "candidates", f"lists {over}; the forecast declares {row['args']['candidates']}"))
        if line["chose"] not in over:
            found.append(Finding(where, "not_a_candidate", f"chose {line['chose']!r}, outside {over}"))
    return found


def seed_findings(repo: Path, head: str = "HEAD") -> list[Finding]:
    """The switchback of the real history: the seed file, if committed before the first `chose:` line, assigns each
    line its regime."""
    history = chose_history(repo, head)
    present = claims._git(repo, "ls-tree", "--name-only", head, SEED_PATH).strip()
    seed = claims._git(repo, "show", f"{head}:{SEED_PATH}").strip() if present else None
    found = switchback_findings(seed, [line for _, line in history])
    if seed is not None and history:
        first = _log(repo, head, seed, SEED_PATH)
        if not sealed_before(repo, first[0] if first else None, history[0][0]):
            found.append(Finding("seed", "late", "the seed was not committed before the first choice"))
    return found


# ------------------------------------------------------------------------------------------------------ command line

def rounds_of(rows: Sequence[dict], sovereign: Sequence[str]) -> list[Round]:
    """The resolved rounds in the ledger, oldest first: sovereign entrants' `guy_picks` rows grouped by `round`, with
    the pick their resolutions carry. A void resolution is no round (it is counted by the report, never scored)."""
    return ledger.pick_rounds(rows, sovereign)


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m harness.chooser")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("choose", help="print the sovereign entrants' forecast rows, the mixture's, and the STATUS line")
    c.add_argument("candidates", nargs="+", help="the open candidates, in A1.5's order")
    c.add_argument("--until", required=True, help="ISO time of the next audit: when silence starts to count")
    c.add_argument("--ts", required=True)
    c.add_argument("--session", required=True)
    c.add_argument("--change-point", action="append", default=[], help="ISO time of a layer boundary or signed instruction")
    c.add_argument("--ordering", type=Path, default=None, help="file with the latest `priorities` issue body")
    c.add_argument("--repo", type=Path, default=Path("."))
    f = sub.add_parser("check", help="findings on every chose: line in history and on the switchback seed")
    f.add_argument("--repo", type=Path, default=Path("."))
    f.add_argument("--head", default="HEAD")
    a = ap.parse_args(argv)
    if a.cmd == "check":
        found = chose_findings(a.repo, a.head) + seed_findings(a.repo, a.head)
        for x in found:
            print(x)
        print(f"{len(chose_history(a.repo, a.head))} chose lines, {len(found)} findings", file=sys.stderr)
        return 1 if found else 0
    sovereign = tomllib.loads((a.repo / ledger.ENTRANTS).read_text())[SOVEREIGN]
    if FIXED not in sovereign:
        print(f"{ledger.ENTRANTS}: {FIXED} is not a sovereign entrant", file=sys.stderr)
        return 2
    seed_file = a.repo / SEED_PATH
    if not seed_file.is_file():
        print(f"no committed switchback seed ({SEED_PATH}): the chooser has not begun; take A1.5's order", file=sys.stderr)
        return 2
    rows = ledger.ledger_rows(a.repo)
    index = len({r["args"]["hash"] for r in rows if r.get("type") == "guy_picks" and r["args"].get("entrant") == MIXTURE})
    regime = regime_at(seed_file.read_text().strip(), index)
    dists: dict[str, Dist] = {FIXED: fixed_order(a.candidates)}
    ordering = ordering_of(a.ordering.read_text()) if a.ordering else []
    if (p := priorities_literal(a.candidates, ordering)) is not None and PRIORITIES in sovereign:
        dists[PRIORITIES] = p
    got = choose(a.candidates, dists, rounds_of(rows, sovereign), a.change_point, regime)
    rid = round_id(a.candidates, a.ts)
    sha = claims._git(a.repo, "rev-parse", "HEAD").strip()
    made = {e: pick_row(e, a.candidates, d, argmax(d, a.candidates), got.chose, a.until, rid, a.ts, sha,
                        {"kind": "mechanism", "model": f"chooser:{e}", "session": a.session}) for e, d in dists.items()}
    made[MIXTURE] = pick_row(MIXTURE, a.candidates, got.dist, got.chose, got.chose, a.until, rid, a.ts, sha,
                             {"kind": "mechanism", "model": f"chooser:{MIXTURE}", "session": a.session})
    for row in made.values():
        print(json.dumps(row))
    print(chose_line(got.chose, a.candidates, got.weights, made[MIXTURE]["args"]["hash"], regime))
    return 0


if __name__ == "__main__":
    sys.exit(main())
