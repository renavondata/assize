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
import statistics
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


def item_number(chose: str, pr: int) -> int:
    """The issue an act-alone choice is overturned on: an instruction `#<n>` is its own issue; a brief item has none,
    so it is the pull request that carries it."""
    m = ledger.ITEM.fullmatch(chose)
    return int(m.group(1)) if m else pr


def act_rows(chose: str, pr: int, until: str, rid: str, ts: str, sha_before: str, proposer: Mapping, p_kept: float,
             p_merged: float) -> list[dict]:
    """What the chooser files for the item it acts on (instruction #111 Part B item 3): `not_overturned {item: <chose>,
    until: <next audit>}` under the exposure regime (silence counts only after gfrmin's `seen`), and #77's `merged {pr}`
    for the pull request that carries it. The probabilities are the acting Builder's, its proposer named."""
    kept = f"Guy does not overturn the chooser's pick {chose} (round {rid}) before {until}"
    merged = f"PR #{pr}, which carries the chooser's pick {chose} (round {rid}), is merged"

    def row(claim: str, p: float, ftype: str, args: dict) -> dict:
        return {"id": claims.forecast_id(claim, ts), "ts": ts, "proposer": dict(proposer), "sha_before": sha_before,
                "claim": claim, "p": p, "resolves_by": until, "type": ftype, "args": args}

    return [row(kept, p_kept, "not_overturned", {"item": item_number(chose, pr), "until": until, "exposure": "seen",
                                                 "chose": chose, "round": rid}),
            row(merged, p_merged, "merged", {"pr": pr, "chose": chose, "round": rid})]


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


def regime_choices(lines: Sequence[Mapping], rows: Sequence[dict]) -> list[dict]:
    """Each parsed `chose:` line, in the order the choices were made, as {regime, chose, round}: the round is the one
    of the `guy_picks` row its hash names, None (counted as unfiled, never dropped) when no row carries it."""
    by_hash = {(r.get("args") or {}).get("hash"): r for r in rows if r.get("type") == "guy_picks" and "claim" in r}
    return [{"regime": line["regime"], "chose": line["chose"],
             "round": (by_hash.get(line["hash"]) or {}).get("args", {}).get("round")} for line in lines]


STATES = ("true", "false", "void", "open", "unfiled")  # a forecast's state at the report: every one is counted


def evidence_bound(k: int, t: int, alpha: float) -> float:
    """How far, in nats, the Fixed Share mixture can trail any single entrant -- `fixed-order` among them -- in summed
    log-likelihood over t rounds: Herbster and Warmuth's bound for a comparator with no switch, ln K + (t - 1) ln(1 /
    (1 - alpha)). With alpha 1 and more than one round there is no bound (+inf), and the report says so."""
    if t <= 0:
        return 0.0
    if alpha >= 1:
        return math.inf if t > 1 else math.log(max(1, k))
    return math.log(max(1, k)) + (t - 1) * -math.log(1 - alpha)


@dataclass(frozen=True)
class RegimeReport:
    """The four outcomes of one regime of the switchback, each with its denominator (Wish #80's amendment)."""
    regime: str
    choices: int
    merged: Mapping[str, int]  # the act's `merged {pr}` forecasts by state
    guy_items: int  # distinct items reached on the choices' issues and pull requests, merged or not
    kept: Mapping[str, int]  # the act's `not_overturned` forecasts by state: false is an overturn, void unexposed
    latencies_h: tuple[float, ...]  # wish-to-merge, one per merged choice whose item cites a wish
    no_wish: int  # merged choices whose item cites no wish: counted, never dropped
    picks: Mapping[str, int]  # the round's mixture `guy_picks` forecast by state
    llr: float  # sum over resolved rounds of ln L(mixture) - ln L(fixed-order) at Guy's pick; +-inf never clipped

    def lines(self) -> list[str]:
        m, k, p = self.merged, self.kept, self.picks
        merged = m["true"]
        lat = sorted(self.latencies_h)
        seen = k["true"] + k["false"]
        resolved = p["true"] + p["false"]
        return [f"regime {self.regime}: choices {self.choices}"
                + ("; no resolved outcome" if not (merged or seen or resolved or m["false"]) else ""),
                f"  guy-items per merged item: {self.guy_items}/{merged}"
                + (f" = {self.guy_items / merged:.3f}" if merged else " (none merged)")
                + f"; merged {' '.join(f'{s} {m[s]}' for s in STATES)}",
                f"  overturn rate, seen: {k['false']}/{seen}" + (f" = {k['false'] / seen:.3f}" if seen else "")
                + f"; unexposed (void) {k['void']}; open {k['open']}; unfiled {k['unfiled']}",
                f"  wish-to-merge latency: n {len(lat)}"
                + (f" median {statistics.median(lat):.1f}h max {lat[-1]:.1f}h" if lat else "")
                + f"; merged citing no wish {self.no_wish}",
                f"  LLR mixture vs {FIXED}: {self.llr:.4f} nats over {resolved} resolved rounds; "
                + " ".join(f"{s} {p[s]}" for s in STATES)]


def switchback_report(choices: Sequence[Mapping], rows: Sequence[dict], reached: Sequence[Mapping],
                      merged_at: Mapping[int, str], wish_at: Mapping[str, str]) -> list[RegimeReport]:
    """Every regime of REGIMES, in that order, whether or not it has a choice. `choices` from `regime_choices`;
    `reached`: events {item, route, at} by which an item reached Guy (as `ledger.price` reads them); `merged_at`: pull
    request -> merge time; `wish_at`: chosen item -> creation time of the wish it cites."""
    resolved, void = ledger.outcomes(rows), ledger.voided(rows)
    picks_of = {r["id"]: r["pick"] for r in rows if "claim" not in r and "id" in r and "pick" in r and not r.get("void")}
    filed = [r for r in rows if "claim" in r and r.get("type") in ("not_overturned", "merged", "guy_picks")]
    guyed = {int(e["item"]) for e in reached if e.get("route") in ledger.ROUTES}

    def state(row: Mapping | None) -> str:
        if row is None:
            return "unfiled"
        if row["id"] in void:
            return "void"
        return {True: "true", False: "false"}.get(resolved.get(row["id"]), "open")

    def one(c: Mapping, ftype: str, entrant: str | None = None) -> Mapping | None:
        return next((r for r in filed if r["type"] == ftype and c["round"] is not None
                     and r["args"].get("round") == c["round"]
                     and (entrant is None or r["args"].get("entrant") == entrant)), None)

    def llr(c: Mapping) -> float:
        mix, fixed = one(c, "guy_picks", MIXTURE), one(c, "guy_picks", FIXED)
        pick = picks_of.get(mix["id"]) if mix else None
        if pick is None or fixed is None:
            return 0.0
        at = (pick["kind"], pick["item"])
        a, b = likelihood(mix["args"]["dist"], at), likelihood(fixed["args"]["dist"], at)
        if a <= 0 and b <= 0:
            return 0.0  # neither gave the pick mass: no evidence either way
        return (math.log(a) if a > 0 else -math.inf) - (math.log(b) if b > 0 else -math.inf)

    def report(regime: str) -> RegimeReport:
        mine = [c for c in choices if c["regime"] == regime]
        merged = {s: 0 for s in STATES}
        kept = {s: 0 for s in STATES}
        picks = {s: 0 for s in STATES}
        items: set[int] = set()
        lat: list[float] = []
        no_wish = 0
        total = 0.0
        for c in mine:
            m = one(c, "merged")
            merged[state(m)] += 1
            kept[state(one(c, "not_overturned"))] += 1
            mix = one(c, "guy_picks", MIXTURE)
            picks[state(mix)] += 1
            pr = int(m["args"]["pr"]) if m else None
            issue = ledger.ITEM.fullmatch(c["chose"])
            items |= {n for n in (pr, int(issue.group(1)) if issue else None) if n is not None}
            if state(m) == "true":
                if c["chose"] in wish_at and pr in merged_at:
                    lat.append((ledger._t(merged_at[pr]) - ledger._t(wish_at[c["chose"]])).total_seconds() / 3600)
                else:
                    no_wish += 1
            total += llr(c)
        return RegimeReport(regime, len(mine), merged, len(items & guyed), kept, tuple(lat), no_wish, picks, total)

    return [report(r) for r in REGIMES]


def report_text(reports: Sequence[RegimeReport], k: int, switches: int) -> str:
    """The report, and the evidence bound on the pooled LLR, from the alpha the chooser derives for the resolved rounds
    and the declared change-points."""
    t = sum(r.picks["true"] + r.picks["false"] for r in reports)
    alpha = derived_alpha(switches, t)
    bound = evidence_bound(k, t, alpha)
    pooled = sum(r.llr for r in reports)
    return "\n".join([line for r in reports for line in r.lines()]
                     + [f"pooled LLR mixture vs {FIXED}: {pooled:.4f} nats over {t} resolved rounds; evidence bound: "
                        f"the mixture trails {FIXED} by at most {bound:.4f} nats (K {k}, alpha {alpha:.4f} from "
                        f"{max(1, switches)} change-points)"])


# ------------------------------------------------------------------------------------------------------- git readers

def _log(repo: Path, head: str, needle: str, globs: Sequence[str]) -> list[str]:
    """Commits reachable from `head`, oldest first, whose diff adds or removes `needle` under `globs`."""
    return claims._git(repo, "log", "--reverse", "--topo-order", "--format=%H", f"-S{needle}", head, "--",
                       *globs).split()


def sealed_before(repo: Path, row_commit: str | None, act_commit: str | None) -> bool:
    """The forecast row is first present in a strict ancestor of the commit where the chooser's act first appears."""
    if row_commit is None or act_commit is None or row_commit == act_commit:
        return False
    return subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", row_commit, act_commit],
                          capture_output=True).returncode == 0


def chose_history(repo: Path, head: str = "HEAD") -> list[tuple[str, dict]]:
    """Every distinct `chose:` line in any STATUS in history, in the order of the commit that first has it: (commit,
    parsed line). A commit that deletes a STATUS has no text of it to read (`--diff-filter=d`)."""
    seen: dict[str, tuple[str, dict]] = {}
    commits = claims._git(repo, "log", "--reverse", "--topo-order", "--format=%H", head, "--",
                          *claims.STATUS_GLOBS).split()
    for c in commits:
        for path in claims._git(repo, "diff-tree", "--root", "--no-commit-id", "--name-only", "-r", "-m", "--first-parent",
                                "--diff-filter=d", c, "--", *claims.STATUS_GLOBS).split():
            for m in CHOSE.finditer(claims._git(repo, "show", f"{c}:{path}")):
                seen.setdefault(m["hash"], (c, m.groupdict()))
    return list(seen.values())


def chose_findings(repo: Path, head: str = "HEAD") -> list[Finding]:
    """For every `chose:` line in history: its forecast row exists, was committed before the line did (the seal), and
    lists exactly the candidates the line does; the line names one of them. A line that departs from the fixed order
    (chooses a candidate other than its first, A1.5's) also needs `fixed-order`'s forecast of the same round sealed
    before it, so the departure is scored against the default it left (instruction #284)."""
    picks = [r for r in ledger.ledger_rows(repo, head) if r.get("type") == "guy_picks" and "claim" in r]
    rows = {r.get("args", {}).get("hash"): r for r in picks}
    fixed = [r.get("args", {}) for r in picks if r.get("args", {}).get("entrant") == FIXED]
    found: list[Finding] = []
    for act_commit, line in chose_history(repo, head):
        where = f"chose {line['hash'][:12]} at {act_commit[:12]}"
        over = [c.strip() for c in line["over"].split(",")]
        row = rows.get(line["hash"])
        first = _log(repo, head, line["hash"], claims.LEDGER_GLOBS)
        if row is None or not first:
            found.append(Finding(where, "no_forecast", "no `guy_picks` row carries the cited hash"))
            continue
        if not sealed_before(repo, first[0], act_commit):
            found.append(Finding(where, "late", f"the forecast is first present at {first[0][:12]}, not before the act"))
        if over != row["args"]["candidates"]:
            found.append(Finding(where, "candidates", f"lists {over}; the forecast declares {row['args']['candidates']}"))
        if line["chose"] not in over:
            found.append(Finding(where, "not_a_candidate", f"chose {line['chose']!r}, outside {over}"))
        rid = row["args"].get("round")
        if line["chose"] in over[1:] and not any(
                sealed_before(repo, next(iter(_log(repo, head, a["hash"], claims.LEDGER_GLOBS)), None), act_commit)
                for a in fixed if a.get("round") == rid):
            found.append(Finding(where, "unscored_departure", f"departs from {FIXED}'s {over[0]} with no {FIXED} "
                                                              f"forecast of round {rid} sealed before the act"))
    return found


def seed_findings(repo: Path, head: str = "HEAD") -> list[Finding]:
    """The switchback of the real history: the seed file, if committed before the first `chose:` line, assigns each
    line its regime."""
    history = chose_history(repo, head)
    present = claims._git(repo, "ls-tree", "--name-only", head, SEED_PATH).strip()
    seed = claims._git(repo, "show", f"{head}:{SEED_PATH}").strip() if present else None
    found = switchback_findings(seed, [line for _, line in history])
    if seed is not None and history:
        first = _log(repo, head, seed, (SEED_PATH,))
        if not sealed_before(repo, first[0] if first else None, history[0][0]):
            found.append(Finding("seed", "late", "the seed was not committed before the first choice"))
    return found


# ------------------------------------------------------------------------------------------------------ command line

def rounds_of(rows: Sequence[dict], sovereign: Sequence[str]) -> list[Round]:
    """The resolved rounds in the ledger, oldest first: sovereign entrants' `guy_picks` rows grouped by `round`, with
    the pick their resolutions carry. A void resolution is no round (it is counted by the report, never scored)."""
    return ledger.pick_rounds(rows, sovereign)


WISH_IN = re.compile(r"\bWish:? #(\d+)\b")


def github_report_inputs(repo: Path, choices: Sequence[Mapping], rows: Sequence[dict],
                         head: str = "HEAD") -> tuple[list[dict], dict[int, str], dict[str, str]]:
    """`switchback_report`'s GitHub inputs, read only for the items the choices name: how each issue or pull request
    reached Guy (`awaits-guy` label, assignment to gfrmin, a STATUS `NEEDS YOU` since the seed, a probe), each merged
    pull request's merge time, and the creation time of the wish each chosen item cites (in its own text, else in its
    instruction issue's `Wish: #n`)."""
    acts = {(r.get("args") or {}).get("round"): r for r in rows if "claim" in r and r.get("type") == "merged"}
    prs = {int(acts[c["round"]]["args"]["pr"]) for c in choices if c["round"] in acts}
    issues = {int(m.group(1)) for c in choices if (m := ledger.ITEM.fullmatch(c["chose"]))}
    reached = [{"item": n, "route": "awaits-guy" if e["event"] == "labeled" else "assigned", "at": e["created_at"]}
               for n in sorted(prs | issues)
               for e in ledger._gh_lines(repo, f"repos/{{owner}}/{{repo}}/issues/{n}/events?per_page=100",
                                         ".[] | {event, created_at, label: .label.name, assignee: .assignee.login}")
               if (e["event"] == "labeled" and e["label"] == "awaits-guy")
               or (e["event"] == "assigned" and e["assignee"] == ledger.GUY)]
    seeded = _log(repo, head, claims._git(repo, "show", f"{head}:{SEED_PATH}").strip(), (SEED_PATH,)) if choices else []
    reached += (ledger.needs_you(repo, seeded[0], head) if seeded else []) + ledger.probes_reached(rows)
    merged_at = {}
    for pr in sorted(prs):
        at = json.loads(ledger._gh(repo, f"repos/{{owner}}/{{repo}}/pulls/{pr}", "--jq", "{at: .merged_at}"))["at"]
        if at:
            merged_at[pr] = at

    def issue(n: int) -> dict:
        return json.loads(ledger._gh(repo, f"repos/{{owner}}/{{repo}}/issues/{n}", "--jq",
                                     "{body: (.body // \"\"), at: .created_at}"))

    wish_at = {}
    for c in choices:
        m = WISH_IN.search(c["chose"]) or ((n := ledger.ITEM.fullmatch(c["chose"]))
                                           and ledger.WISH_CITE.search(issue(int(n.group(1)))["body"]))
        if m:
            wish_at[c["chose"]] = issue(int(m.group(1)))["at"]
    return reached, merged_at, wish_at


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m harness.chooser")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("choose", help="print the sovereign entrants' forecast rows, the mixture's, the act's "
                                      "not_overturned and merged rows, and the STATUS line")
    c.add_argument("candidates", nargs="+", help="the open candidates, in A1.5's order")
    c.add_argument("--until", required=True, help="ISO time of the next audit: when silence starts to count")
    c.add_argument("--ts", required=True)
    c.add_argument("--session", required=True)
    c.add_argument("--model", required=True, help="the acting Builder's model: the proposer of the act's forecasts")
    c.add_argument("--pr", type=int, required=True, help="the pull request that will carry the chosen item")
    c.add_argument("--p-kept", type=float, required=True, help="the Builder's p that Guy does not overturn the choice")
    c.add_argument("--p-merged", type=float, required=True, help="the Builder's p that the pull request merges")
    c.add_argument("--change-point", action="append", default=[], help="ISO time of a layer boundary or signed instruction")
    c.add_argument("--ordering", type=Path, default=None, help="file with the latest `priorities` issue body")
    c.add_argument("--repo", type=Path, default=Path("."))
    f = sub.add_parser("check", help="findings on every chose: line in history and on the switchback seed")
    f.add_argument("--repo", type=Path, default=Path("."))
    f.add_argument("--head", default="HEAD")
    r = sub.add_parser("report", help="the switchback's four outcomes per regime, with denominators (Wish #80)")
    r.add_argument("--change-point", action="append", default=[], help="ISO time of a layer boundary or signed instruction")
    r.add_argument("--repo", type=Path, default=Path("."))
    r.add_argument("--head", default="HEAD")
    a = ap.parse_args(argv)
    if a.cmd == "report":
        rows = ledger.ledger_rows(a.repo, a.head)
        choices = regime_choices([line for _, line in chose_history(a.repo, a.head)], rows)
        sovereign = tomllib.loads(claims._git(a.repo, "show", f"{a.head}:{ledger.ENTRANTS}"))[SOVEREIGN]
        reports = switchback_report(choices, rows, *github_report_inputs(a.repo, choices, rows, a.head))
        print(report_text(reports, len(sovereign), len(a.change_point)))
        return 0
    if a.cmd == "check":
        found = chose_findings(a.repo, a.head) + seed_findings(a.repo, a.head)
        for x in found:
            print(x)
        print(f"{len(chose_history(a.repo, a.head))} chose lines, {len(found)} findings", file=sys.stderr)
        return 1 if found else 0
    if not (0 < a.p_kept < 1 and 0 < a.p_merged < 1):
        print(f"--p-kept {a.p_kept} and --p-merged {a.p_merged} must lie in (0, 1)", file=sys.stderr)
        return 2
    sovereign =tomllib.loads((a.repo / ledger.ENTRANTS).read_text())[SOVEREIGN]
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
    acted = act_rows(got.chose, a.pr, a.until, rid, a.ts, sha, {"kind": "builder", "model": a.model, "session": a.session},
                     a.p_kept, a.p_merged)
    for row in [*made.values(), *acted]:
        print(json.dumps(row))
    print(chose_line(got.chose, a.candidates, got.weights, made[MIXTURE]["args"]["hash"], regime))
    return 0


if __name__ == "__main__":
    sys.exit(main())
