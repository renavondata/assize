"""`python -m harness.ledger surprise --since <sha>`: the pull requests merged into master since <sha>, ranked by the
Builder's cumulative log-loss on the forecasts each added (instruction #46 item 5). A pull request's forecasts are the
forecast rows its merge adds to any `reports/L*/forecasts.jsonl`, read from git; a forecast's outcome is the last
resolution of its id in the ledgers at the head. Unresolved forecasts add no loss and are counted, never dropped.

`python -m harness.ledger proposer <kind>`: that proposer's record per class (instruction #49 §4). The Vizier's forecast
rows carry `class` and `mode`: `recommend` forecasts Guy's answer, `act` forecasts that Guy does not overturn the act;
either is correct when it resolves true, and an `act` resolved false is an overturn.

`python -m harness.ledger resolve`: rule 3 of the ground (instruction #54 item 3). A forecast carries `type` and
`args`; for every open forecast of a type in OUTCOMES whose outcome is observable, the resolver appends a resolution
proposed by the mechanism. A forecast without `type` is `free`, and the mechanism never resolves a `free` one.

`python -m harness.ledger price --since <sha>`: rule 6 of the ground (instruction #54 item 6), the price of the court:
what reached Guy and how long he took, sessions run and runner-minutes.

`python -m harness.ledger elect <procedure> --seed <run id>`: rule 7 of the ground (instruction #54 item 7), a model
drawn by EXP3 over the entrants of `harness/entrants.toml` (instruction #64): bandit feedback, only the drawn entrant is
scored, and its probability is the one recorded in `reports/draws.jsonl` when it was drawn; with `--publish <remote>`
that ledger is the one on the remote's `ledger/draws` branch, onto which the draw is committed."""

from __future__ import annotations

import argparse
import datetime
import json
import math
import os
import re
import statistics
import subprocess
import sys
import tomllib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from harness.claims import MECHANISM, PINS_WORKFLOW, _git

MERGE_SUBJECT = re.compile(r"^Merge pull request #(\d+) ")
LEDGER = "reports/*/forecasts.jsonl"


@dataclass(frozen=True)
class Merged:
    number: int
    sha: str
    forecasts: tuple[dict, ...]  # the Builder's forecast rows the merge added


@dataclass(frozen=True)
class Surprise:
    number: int
    sha: str
    loss: float
    resolved: int
    made: int
    sessions: tuple[str, ...]

    def __str__(self) -> str:
        return (f"#{self.number} {self.sha[:12]} loss={self.loss:.4f} resolved={self.resolved}/{self.made} "
                f"builders={','.join(self.sessions) or 'none'}")


def log_loss(p: float, outcome: bool) -> float:
    return -math.log(p if outcome else 1 - p)


def _rows(lines: Sequence[str]) -> list[dict]:
    def parse(line: str) -> dict | None:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            return None
        return row if isinstance(row, dict) else None

    return [r for r in map(parse, lines) if r is not None]


def _builder_forecast(r: dict) -> bool:
    return ("claim" in r and isinstance(r.get("p"), (int, float)) and isinstance(r.get("proposer"), dict)
            and r["proposer"].get("kind") == "builder")


def outcomes(rows: Sequence[dict]) -> dict[str, bool]:
    """The last resolution of each forecast id, in ledger order (A1.6: a later record answers an earlier one). The two
    L0 resolutions written before A1.6 was enforced name their forecast by `resolves` (claims.L0_PRE_RULE's rows)."""
    return {r.get("id", r.get("resolves")): r["outcome"] for r in rows
            if "claim" not in r and isinstance(r.get("outcome"), bool) and ("id" in r or "resolves" in r)}


def surprise(merged: Sequence[Merged], resolved: Mapping[str, bool]) -> list[Surprise]:
    """Each merged pull request with the Builder's cumulative log-loss on its resolved forecasts, largest first."""
    def score(m: Merged) -> Surprise:
        known = [(f["p"], resolved[f["id"]]) for f in m.forecasts if f.get("id") in resolved]
        sessions = tuple(sorted({str(f["proposer"].get("session", "")) for f in m.forecasts}))
        return Surprise(m.number, m.sha, sum(log_loss(p, o) for p, o in known), len(known), len(m.forecasts),
                        sessions)

    return sorted(map(score, merged), key=lambda s: (-s.loss, s.number))


@dataclass(frozen=True)
class Record:
    cls: str
    made: int
    resolved: int
    correct: int
    overturned: int
    loss: float

    @property
    def unbroken(self) -> bool:
        """Correct on every resolved case: a recommended class the next audit proposes for the act-alone list."""
        return self.resolved > 0 and self.correct == self.resolved

    def __str__(self) -> str:
        return (f"{self.cls} made={self.made} resolved={self.resolved} correct={self.correct}/{self.resolved} "
                f"overturned={self.overturned} loss={self.loss:.4f} unbroken={'yes' if self.unbroken else 'no'}")


def record(rows: Sequence[dict], kind: str, since: str = "") -> list[Record]:
    """`kind`'s forecasts with `ts` at or after `since`, per class (`class`, else `unclassed`), with each class's
    resolved and correct counts, its overturned acts and its cumulative log-loss, classes in name order."""
    resolved = outcomes(rows)
    mine = [r for r in rows if "claim" in r and isinstance(r.get("p"), (int, float))
            and isinstance(r.get("proposer"), dict) and r["proposer"].get("kind") == kind
            and str(r.get("ts", "")) >= since]

    def tally(cls: str) -> Record:
        rs = [r for r in mine if str(r.get("class", "unclassed")) == cls]
        known = [(r, resolved[r["id"]]) for r in rs if r.get("id") in resolved]
        return Record(cls, len(rs), len(known), sum(1 for _, o in known if o),
                      sum(1 for r, o in known if r.get("mode") == "act" and not o),
                      sum(log_loss(r["p"], o) for r, o in known))

    return [tally(c) for c in sorted({str(r.get("class", "unclassed")) for r in mine})]


def merged_since(repo: Path, since: str, head: str = "HEAD") -> list[Merged]:
    """Merges of pull requests on head's first-parent line after `since`, oldest first, each with the Builder's
    forecast rows it added to a ledger (the lines its diff against its first parent adds)."""
    log = _git(repo, "log", "--first-parent", "--merges", "--reverse", "--format=%H%x1f%P%x1f%s", f"{since}..{head}")

    def merged(line: str) -> Merged | None:
        sha, parents, subject = line.split("\x1f", 2)
        m = MERGE_SUBJECT.match(subject)
        if m is None:
            return None
        diff = _git(repo, "diff", "-U0", "--no-color", parents.split()[0], sha, "--", LEDGER).splitlines()
        added = [line[1:] for line in diff if line.startswith("+") and not line.startswith("+++")]
        return Merged(int(m.group(1)), sha, tuple(r for r in _rows(added) if _builder_forecast(r)))

    return [m for m in map(merged, log.splitlines()) if m is not None]


def ledger_rows(repo: Path, head: str = "HEAD") -> list[dict]:
    """Every row of every ledger at `head`, ledgers in path order."""
    paths = sorted(p for p in _git(repo, "ls-tree", "-r", "--name-only", head, "reports/").splitlines()
                   if Path(p).match(LEDGER))
    return [r for p in paths for r in _rows(_git(repo, "show", f"{head}:{p}").splitlines())]


# ------------------------------------------------------------------ rule 3: outcomes by code (instruction #54)

# An observer answers a query about the world: ("pins_runs", pr), ("run_attempt", run id), ("pr", pr), ("prs",),
# ("review_files", pr), ("report",), ("timeline", item), ("audit", sha), ("price", layer). The real one reads the
# GitHub API and the working tree; P0s's reads fixture answers. A query it cannot answer raises Unreadable.
Observe = Callable[..., object]
Outcome = tuple[bool, str]  # the outcome and its witness


class Unreadable(Exception):
    pass


def _t(iso: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))


def _at_or_after(a: str | None, b: str) -> bool:
    return a is not None and _t(a) >= _t(b)


def _pr_of(args: Mapping, f: Mapping, observe: Observe, now: str) -> tuple[int | None, Outcome | None]:
    """The pull request a forecast binds to: `pr`, or else the first opened whose head ref is `branch` and which was
    not closed before the forecast (instruction #66). With no such pull request once `resolves_by` has passed, the
    outcome is false: no pull request is an outcome, not a drop."""
    if "pr" in args:
        return int(args["pr"]), None
    branch = str(args["branch"])

    def live(p: Mapping) -> bool:
        return p.get("head_ref") == branch and (p.get("closed_at") is None or _at_or_after(p["closed_at"], f["ts"]))

    prs = sorted(filter(live, observe("prs")), key=lambda p: (_t(p["created_at"]), int(p["number"])))
    if prs:
        return int(prs[0]["number"]), None
    return None, ((False, f"no pull request from {branch} by {f['resolves_by']}")
                  if _at_or_after(now, str(f["resolves_by"])) else None)


def _bound(rule: Callable[[int, Mapping, Observe, str], Outcome | None]) -> Callable[..., Outcome | None]:
    """A rule on a pull request, read from a forecast whose args name it by `pr` or by `branch`."""
    def on(args: Mapping, f: Mapping, observe: Observe, now: str) -> Outcome | None:
        pr, settled = _pr_of(args, f, observe, now)
        return settled if pr is None else rule(pr, f, observe, now)
    return on


def _pins_green(pr: int, f: Mapping, observe: Observe, now: str) -> Outcome | None:
    """The first `pins` run on the pull request created at or after the forecast concluded success at attempt 1."""
    runs = [r for r in observe("pins_runs", pr) if _at_or_after(r.get("created_at"), f["ts"])]
    if not runs:
        return None
    first = min(runs, key=lambda r: (_t(r["created_at"]), int(r["id"])))
    attempt = observe("run_attempt", int(first["id"]))
    if attempt.get("status") != "completed":
        return None
    return (attempt.get("conclusion") == "success",
            f"pins run {first['id']} attempt 1 on {str(first.get('head_sha', ''))[:12]}: {attempt.get('conclusion')}")


REVIEW_VERDICT = re.compile(r"^VERDICT: (ACCEPT WITH OBLIGATIONS|ACCEPT|BLOCK)\s*$", re.M)


def _review_accept(pr: int, f: Mapping, observe: Observe, now: str) -> Outcome | None:
    """The first review file the pull request's commits add at or after the forecast says `VERDICT: ACCEPT` or
    `ACCEPT WITH OBLIGATIONS` and carries no `severity: BLOCK`."""
    files = [x for x in observe("review_files", pr) if _at_or_after(x.get("date"), f["ts"])]
    if not files:
        return None
    first = files[0]
    verdict = REVIEW_VERDICT.search(first["text"])
    accept = verdict is not None and verdict.group(1) != "BLOCK" and "severity: BLOCK" not in first["text"]
    return accept, f"{first['path']} at {str(first['sha'])[:12]}: {verdict.group(1) if verdict else 'no VERDICT'}"


def _merged(pr: int, f: Mapping, observe: Observe, now: str) -> Outcome | None:
    got = observe("pr", pr)
    if got.get("merged"):
        return True, f"PR #{pr} merged at {got.get('merged_at')}"
    return (False, f"PR #{pr} closed unmerged at {got.get('closed_at')}") if got.get("state") == "closed" else None


def _layer_line(report: str, layer: int) -> str | None:
    """The last verdict line of `layer` in REPORT.md (a later line answers an earlier one), or None."""
    lines = [line for line in report.splitlines() if line.startswith(f"- L{layer} — ")]
    return lines[-1] if lines else None


def _host_verdict(args: Mapping, f: Mapping, observe: Observe, now: str) -> Outcome | None:
    """The layer's last verdict line in REPORT.md carries `verdict` as a word in its bold verdict (the line if none)."""
    line = _layer_line(str(observe("report")), int(args["layer"]))
    if line is None:
        return None
    bold = re.search(r"\*\*(.+?)\*\*", line)
    said = bold.group(1) if bold else line
    return re.search(rf"\b{re.escape(str(args['verdict']))}\b", said) is not None, f"REPORT.md: {said}"


GUY = "gfrmin"


def _actor(e: Mapping) -> str | None:
    return (e.get("actor") or e.get("user") or {}).get("login")


def _when(e: Mapping) -> str | None:
    return e.get("created_at") or e.get("submitted_at")


def answer(e: Mapping) -> str | None:
    """An answer an item's timeline event gives: a review state (`approved`, `changes_requested`), `merged`, `closed`,
    or `labeled:<name>`; None for any other event."""
    kind = e.get("event")
    if kind == "reviewed":
        return str(e.get("state", "")).lower() if str(e.get("state", "")).lower() != "commented" else None
    if kind in ("merged", "closed"):
        return kind
    return f"labeled:{(e.get('label') or {}).get('name')}" if kind == "labeled" else None


def _guy_answers(args: Mapping, f: Mapping, observe: Observe, now: str) -> Outcome | None:
    """True once gfrmin gives `answer` on the item at or after the forecast; false once the item is closed without
    his giving it; open otherwise."""
    events = [e for e in observe("timeline", int(args["item"])) if _at_or_after(_when(e), f["ts"])]
    given = [e for e in events if _actor(e) == GUY and answer(e) == args["answer"]]
    if given:
        return True, f"#{args['item']}: gfrmin {args['answer']} at {_when(given[0])}"
    closed = [e for e in events if e.get("event") == "closed"]
    return (False, f"#{args['item']}: closed at {_when(closed[-1])} without gfrmin {args['answer']}") if closed else None


def reverses(e: Mapping, events: Sequence[Mapping]) -> bool:
    """gfrmin reopens, unlabels, or closes the item other than by merging it."""
    if _actor(e) != GUY:
        return False
    merged = {_when(m) for m in events if m.get("event") == "merged"}
    return e.get("event") in ("reopened", "unlabeled") or (e.get("event") == "closed" and _when(e) not in merged)


def _not_overturned(args: Mapping, f: Mapping, observe: Observe, now: str) -> Outcome | None:
    """True once `until` passes with no gfrmin reversal of the item at or after the forecast; false at a reversal."""
    events = list(observe("timeline", int(args["item"])))
    before = [e for e in events if _at_or_after(_when(e), f["ts"]) and not _at_or_after(_when(e), args["until"])]
    rev = [e for e in before if reverses(e, events)]
    if rev:
        return False, f"#{args['item']}: gfrmin {rev[0].get('event')} at {_when(rev[0])}"
    return (True, f"#{args['item']}: no gfrmin reversal before {args['until']}") if _at_or_after(now, args["until"]) \
        else None


FINDING_LINE = re.compile(r"^F\d+: ", re.M)


def in_bin(n: int, b: str) -> bool:
    """A finding-count bin: `k`, `a-b` (or `a–b`), or `k+`."""
    b = b.replace("–", "-")
    if b.endswith("+"):
        return n >= int(b[:-1])
    lo, _, hi = b.partition("-")
    return int(lo) <= n <= int(hi or lo)


def _finding_count(args: Mapping, f: Mapping, observe: Observe, now: str) -> Outcome | None:
    """The count of `F<i>:` lines in the audit file of `sha` is in `bin`."""
    found = observe("audit", str(args["sha"]))
    if found is None:
        return None
    path, text = found
    n = len(FINDING_LINE.findall(text))
    return in_bin(n, str(args["bin"])), f"{path}: {n} findings"


def _price(args: Mapping, f: Mapping, observe: Observe, now: str) -> Outcome | None:
    """At the layer's boundary, the layer's price `quantity` is at most `bound`."""
    price = observe("price", int(args["layer"]))
    if price is None:
        return None
    got = price[str(args["quantity"])]
    return got <= float(args["bound"]), f"price of L{args['layer']}: {args['quantity']} {got}"


FREE = "free"
OUTCOMES: Mapping[str, Callable[..., Outcome | None] | None] = {
    "pins_green": _bound(_pins_green), "review_accept": _bound(_review_accept), "merged": _bound(_merged), "host_verdict": _host_verdict,
    "guy_answers": _guy_answers, "not_overturned": _not_overturned, "finding_count": _finding_count,
    "price": _price,
    FREE: None,  # never resolved by the mechanism; the Reviewer resolves it by hand, with its witness
}


def forecast_type(f: Mapping) -> str:
    """A forecast's type; one written before instruction #54 carries none and is `free`."""
    return str(f.get("type", FREE))


def open_forecasts(rows: Sequence[dict]) -> list[dict]:
    resolved = outcomes(rows)
    return [r for r in rows if "claim" in r and r.get("id") not in resolved]


def resolve(rows: Sequence[dict], observe: Observe, now: str, session: str) -> tuple[list[dict], list[str]]:
    """Resolutions for every open typed forecast whose outcome is observable, and a line for every one that could not
    be read or whose type no outcome function names (never dropped silently)."""
    proposer = {"kind": MECHANISM, "model": "harness.ledger", "session": session}

    def one(f: dict) -> tuple[dict | None, str | None]:
        rule = OUTCOMES.get(forecast_type(f), "unknown")
        if rule is None:
            return None, None
        if rule == "unknown":
            return None, f"{f['id']}: type {forecast_type(f)!r} has no outcome function"
        try:
            got = rule(f.get("args") or {}, f, observe, now)
        except (Unreadable, KeyError, TypeError, ValueError) as e:
            return None, f"{f['id']}: {forecast_type(f)} {f.get('args')}: not read ({type(e).__name__}: {e})"
        if got is None:
            return None, None
        o, witness = got
        return {"id": f["id"], "ts": now, "proposer": proposer, "outcome": o, "witness": witness}, None

    done = [one(f) for f in open_forecasts(rows)]
    return [r for r, _ in done if r is not None], [e for _, e in done if e is not None]


def _gh(repo: Path, path: str, *args: str) -> str:
    try:
        return subprocess.run(["gh", "api", path, *args], cwd=repo, check=True, capture_output=True, text=True,
                              timeout=120).stdout
    except (OSError, subprocess.SubprocessError) as e:
        raise Unreadable(f"gh api {path}: {getattr(e, 'stderr', '') or e}") from e


def _gh_lines(repo: Path, path: str, jq: str) -> list[dict]:
    return [json.loads(line) for line in _gh(repo, path, "--paginate", "--jq", jq).splitlines() if line.strip()]


REVIEW_FILE = re.compile(r"^reports/L\d+/review-[0-9a-f]+\.md$")


def github_observer(repo: Path, price_of: Callable[[int], Mapping | None]) -> Observe:
    """Answers from the GitHub API (`gh api`, from `repo`'s remote) and from `repo`'s working tree."""
    def pr_branch(pr: int) -> str:
        return json.loads(_gh(repo, f"repos/{{owner}}/{{repo}}/pulls/{pr}", "--jq", "{ref: .head.ref}"))["ref"]

    def review_files(pr: int) -> list[dict]:
        commits = _gh_lines(repo, f"repos/{{owner}}/{{repo}}/pulls/{pr}/commits?per_page=100",
                            ".[] | {sha, date: .commit.committer.date}")

        def added(c: dict) -> list[dict]:
            files = _gh_lines(repo, f"repos/{{owner}}/{{repo}}/commits/{c['sha']}?per_page=100",
                              ".files[] | select(.status == \"added\") | {filename}")
            return [c | {"path": x["filename"],
                         "text": _gh(repo, f"repos/{{owner}}/{{repo}}/contents/{x['filename']}?ref={c['sha']}",
                                     "-H", "Accept: application/vnd.github.raw")}
                    for x in files if REVIEW_FILE.match(x["filename"])]

        return [x for c in commits for x in added(c)]

    def audit(sha: str) -> tuple[str, str] | None:
        found = sorted(p for p in repo.glob("reports/L*/audit-*.md")
                       if p.stem[len("audit-"):].startswith(sha) or sha.startswith(p.stem[len("audit-"):]))
        return (str(found[0].relative_to(repo)), found[0].read_text()) if found else None

    def observe(kind: str, *key: object) -> object:
        if kind == "pins_runs":
            return _gh_lines(repo, f"repos/{{owner}}/{{repo}}/actions/workflows/pins.yml/runs?event=pull_request"
                                   f"&branch={pr_branch(int(key[0]))}&per_page=100",
                             ".workflow_runs[] | {id, created_at, head_sha, path, event}")
        if kind == "run_attempt":
            return json.loads(_gh(repo, f"repos/{{owner}}/{{repo}}/actions/runs/{key[0]}/attempts/1", "--jq",
                                  "{status, conclusion}"))
        if kind == "pr":
            return json.loads(_gh(repo, f"repos/{{owner}}/{{repo}}/pulls/{key[0]}", "--jq",
                                  "{state, merged, merged_at, closed_at}"))
        if kind == "prs":
            return _gh_lines(repo, "repos/{owner}/{repo}/pulls?state=all&per_page=100",
                             ".[] | {number, head_ref: .head.ref, created_at, closed_at}")
        if kind == "review_files":
            return review_files(int(key[0]))
        if kind == "report":
            return (repo / "REPORT.md").read_text()
        if kind == "timeline":
            return _gh_lines(repo, f"repos/{{owner}}/{{repo}}/issues/{key[0]}/timeline?per_page=100", ".[]")
        if kind == "audit":
            return audit(str(key[0]))
        if kind == "price":
            return price_of(int(key[0]))
        raise Unreadable(f"no query {kind}")

    return observe


def ledger_paths(repo: Path) -> list[Path]:
    return sorted(repo.glob(LEDGER))


def now_utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------- rule 6: the price (instruction #54 item 6)

ROUTES = ("awaits-guy", "assigned", "needs-you")
SESSION_WORKFLOWS = (".github/workflows/build.yml", ".github/workflows/review.yml")


@dataclass(frozen=True)
class Price:
    items: tuple[int, ...]
    latencies_h: tuple[float, ...]  # one per item: to gfrmin's first action, or to the window's end if none yet
    open_items: tuple[int, ...]
    sessions: int
    runner_min: Mapping[str, float]  # per workflow path
    pins_min: float
    wishes: tuple[int, ...] = ()  # filed in the window
    wish_latencies_h: tuple[float, ...] = ()  # one per wish merged by the window's end, from the wish's own creation
    open_wishes: tuple[int, ...] = ()  # no instruction citing it merged yet: counted, never dropped

    def quantities(self) -> dict[str, float]:
        lat = self.latencies_h or (0.0,)
        return {"guy-items": float(len(self.items)), "guy-latency-median": statistics.median(lat),
                "guy-latency-max": max(lat), "sessions": float(self.sessions),
                "runner-min": float(sum(self.runner_min.values()))}

    def status_line(self) -> str:
        q = self.quantities()
        w = self.wish_latencies_h or (0.0,)
        return (f"price: guy-items {len(self.items)}; guy-latency median {q['guy-latency-median']:.1f}h max "
                f"{q['guy-latency-max']:.1f}h; sessions {self.sessions}; runner-min {q['runner-min']:.0f}; "
                f"wish-latency median {statistics.median(w):.1f}h max {max(w):.1f}h open {len(self.open_wishes)}")


def _hours(a: str, b: str) -> float:
    return (_t(b) - _t(a)).total_seconds() / 3600


def price(reached: Sequence[Mapping], actions: Mapping[int, Sequence[str]], runs: Sequence[Mapping], since: str,
          until: str) -> Price:
    """`reached`: events {item, route, at} by which an item reached Guy; `actions`: per item, the times of gfrmin's
    actions on it; `runs`: Actions API runs. Everything is counted in [since, until): each item once, at its first
    arrival, its latency to gfrmin's first action after that, or, with none yet, to `until` (a lower bound, never
    dropped)."""
    inside = [e for e in reached if e["route"] in ROUTES and _at_or_after(e["at"], since)
              and not _at_or_after(e["at"], until)]
    items = sorted({e["item"] for e in inside})
    first = {n: min((e["at"] for e in inside if e["item"] == n), key=_t) for n in items}
    answered = {n: min((a for a in actions.get(n, ()) if _t(a) > _t(first[n]) and _t(a) < _t(until)), key=_t,
                       default=None) for n in items}
    latencies = tuple(_hours(first[n], answered[n] or until) for n in items)
    ran = [r for r in runs if _at_or_after(r.get("created_at"), since) and not _at_or_after(r.get("created_at"), until)
           and r.get("conclusion") != "skipped"]

    def minutes(r: Mapping) -> float:
        start = r.get("run_started_at") or r.get("created_at")
        return max(0.0, _hours(start, r["updated_at"]) * 60) if start and r.get("updated_at") else 0.0

    per = {w: sum(minutes(r) for r in ran if r.get("path") == w) for w in sorted({str(r.get("path")) for r in ran})}
    return Price(tuple(items), latencies, tuple(n for n in items if answered[n] is None),
                 sum(1 for r in ran if r.get("path") in SESSION_WORKFLOWS), per, per.get(PINS_WORKFLOW, 0.0))


def wish_latency(created: Mapping[int, str], wishes: Sequence[int], cited: Mapping[int, int],
                 merged: Mapping[int, str], since: str, until: str) -> tuple[tuple[int, ...], tuple[float, ...], tuple[int, ...]]:
    """`created`: issue number -> `created_at`, for wishes and instructions alike; `wishes`: the wish numbers; `cited`: instruction number -> the wish its draft cites; `merged`:
    instruction number -> merge time of the pull request that closed it. For each wish filed in [since, until), the
    hours from its own creation to the earliest merge before `until` of an instruction citing it; a wish with none is
    open. Returns (wishes, latencies of the merged ones, open wishes)."""
    filed = sorted(n for n in wishes if _at_or_after(created[n], since) and not _at_or_after(created[n], until))
    done = {n: min((merged[i] for i, w in cited.items() if w == n and i in merged and not _at_or_after(merged[i], until)),
                   key=_t, default=None) for n in filed}
    return (tuple(filed), tuple(_hours(created[n], done[n]) for n in filed if done[n]),
            tuple(n for n in filed if not done[n]))


STATUS_PR = re.compile(r"^# STATUS — L\d+ — \S+ — \S+ — PR #(\d+)", re.M)
NEEDS_YOU = re.compile(r"^NEEDS YOU[^:]*:\s*(.*)$", re.M)


def needs_you(repo: Path, since: str, head: str = "HEAD") -> list[dict]:
    """Every STATUS commit in since..head whose `NEEDS YOU` line names an item: the pull request in its header, at
    the commit's committer date."""
    log = _git(repo, "log", "--format=%H%x1f%cI", f"{since}..{head}", "--", "reports/*/STATUS.md").splitlines()

    def asked(line: str) -> list[dict]:
        sha, at = line.split("\x1f")
        paths = _git(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", "--root", sha,
                     "--", "reports/*/STATUS.md").splitlines()
        texts = [_git(repo, "show", f"{sha}:{p}") for p in paths if p]
        return [{"item": int(h.group(1)), "route": "needs-you", "at": at} for t in texts
                if (h := STATUS_PR.search(t)) and (n := NEEDS_YOU.search(t)) and n.group(1).strip().lower() != "none"]

    return [e for line in log if line for e in asked(line)]


def github_price(repo: Path, since_sha: str, until: str | None, head: str = "HEAD") -> tuple[Price, str, str]:
    """The price over [the commit date of `since_sha`, `until` or now), read from the API and the repository."""
    since = _git(repo, "show", "-s", "--format=%cI", since_sha).strip()
    end = until or now_utc()
    events = _gh_lines(repo, "repos/{owner}/{repo}/issues/events?per_page=100",
                       ".[] | {event, created_at, label: .label.name, assignee: .assignee.login, item: .issue.number}")
    reached = [{"item": e["item"], "route": "awaits-guy" if e["event"] == "labeled" else "assigned",
                "at": e["created_at"]} for e in events
               if (e["event"] == "labeled" and e["label"] == "awaits-guy")
               or (e["event"] == "assigned" and e["assignee"] == GUY)] + needs_you(repo, since_sha, head)
    items = sorted({e["item"] for e in reached})
    actions = {n: [str(_when(e)) for e in _gh_lines(repo, f"repos/{{owner}}/{{repo}}/issues/{n}/timeline?per_page=100",
                                                    ".[]") if _actor(e) == GUY and _when(e)] for n in items}
    runs = _gh_lines(repo, f"repos/{{owner}}/{{repo}}/actions/runs?per_page=100&created=>={since[:10]}",
                     ".workflow_runs[] | {id, path, conclusion, created_at, run_started_at, updated_at}")
    return replace(price(reached, actions, runs, since, end), **_wish_fields(repo, since, end)), since, end


WISH_CITE = re.compile(r"^Wish: #(\d+)", re.M)
INSTRUCTION_CITE = re.compile(r"Instruction: #(\d+)")


def _wish_fields(repo: Path, since: str, until: str) -> dict:
    """The wishes filed in the window, the drafts citing them (`Wish: #n`), and the merged pull requests citing an
    instruction (`Instruction: #n` in their body), read from the API."""
    issues = _gh_lines(repo, "repos/{owner}/{repo}/issues?state=all&per_page=100",
                       ".[] | select(.pull_request == null) | {number, created_at, body, labels: [.labels[].name]}")
    cited = {i["number"]: int(m.group(1)) for i in issues if "instruction" in i["labels"]
             and (m := WISH_CITE.search(i["body"] or ""))}
    prs = _gh_lines(repo, "repos/{owner}/{repo}/pulls?state=closed&per_page=100", ".[] | {body, merged_at}")
    merged = {int(m.group(1)): p["merged_at"] for p in prs if p["merged_at"]
              for m in INSTRUCTION_CITE.finditer(p["body"] or "")}
    created = {i["number"]: i["created_at"] for i in issues}
    got = wish_latency(created, [i["number"] for i in issues if "wish" in i["labels"]], cited, merged, since, until)
    return {"wishes": got[0], "wish_latencies_h": got[1], "open_wishes": got[2]}


def boundary_window(repo: Path, layer: int, head: str = "HEAD") -> tuple[str, str] | None:
    """The commit adding the layer's first verdict line, and the last commit before it adding one of the layer
    below (the root commit if none): the layer's window. None before the boundary."""
    def adding(k: int) -> list[tuple[str, str]]:
        log = _git(repo, "log", "--reverse", "--format=%H%x1f%cI", f"-G^- L{k} — ", head, "--", "REPORT.md")
        return [tuple(line.split("\x1f")) for line in log.splitlines() if line]

    ends = adding(layer)
    if not ends:
        return None
    end_sha, end_at = ends[0]
    starts = [s for s, at in adding(layer - 1) if _t(at) <= _t(end_at)] if layer > 0 else []
    return (starts[-1] if starts else _git(repo, "rev-list", "--max-parents=0", head).split()[0]), end_sha


def layer_price(repo: Path, head: str = "HEAD") -> Callable[[int], Mapping | None]:
    def of(layer: int) -> Mapping | None:
        window = boundary_window(repo, layer, head)
        if window is None:
            return None
        until = _git(repo, "show", "-s", "--format=%cI", window[1]).strip()
        return github_price(repo, window[0], until, head)[0].quantities()

    return of


# ------------------------------------------------------------ rule 7: models elected (instruction #54 item 7)

PROCEDURES: Mapping[str, str] = {"build": "builder", "review": "reviewer", "audit": "auditor", "vizier": "vizier"}
ENTRANTS = "harness/entrants.toml"
DRAW_LEDGER = "reports/draws.jsonl"  # append-only (claims.APPEND_ONLY): one row per draw, written when it is made
DRAWS = 1 << 16  # the draw's resolution: a sweep of DRAWS consecutive seeds takes every value of u once
STRIDE = 40503  # odd, so seed -> seed * STRIDE mod DRAWS is a bijection


def draw_rows(repo: Path, head: str = "HEAD") -> list[dict]:
    """Every draw recorded in the draw ledger at `head` (none when the file does not exist there yet)."""
    present = _git(repo, "ls-tree", "--name-only", head, DRAW_LEDGER).strip()
    return _rows(_git(repo, "show", f"{head}:{DRAW_LEDGER}").splitlines()) if present else []


# Review of 22d0279 F1: a row appended to the runner's working tree never reaches a later election, so a published draw
# is committed onto its own branch of the remote, which no pull request merges and every later `--publish` election
# reads. The push is never forced: a rejected push re-reads the branch and appends the same row to its new tip.
DRAW_BRANCH = "ledger/draws"
DRAW_AUTHOR = {"GIT_AUTHOR_NAME": "harness.ledger", "GIT_AUTHOR_EMAIL": "ledger@assize.invalid",
               "GIT_COMMITTER_NAME": "harness.ledger", "GIT_COMMITTER_EMAIL": "ledger@assize.invalid"}
PUBLISH_ATTEMPTS = 5


def _net(repo: Path, *args: str, stdin: str = "", env: Mapping[str, str] = {}) -> str:
    """git under the user's configuration: the remote's credential helper (`gh auth setup-git`) lives there."""
    return subprocess.run(["git", "-C", str(repo), *args], input=stdin, check=True, capture_output=True, text=True,
                          env={**os.environ, **env}).stdout


def draw_tip(repo: Path, remote: str) -> str | None:
    """The remote's draw-branch tip, fetched; None when the branch does not exist yet. An unreachable remote raises."""
    ref = f"refs/heads/{DRAW_BRANCH}"
    if not _net(repo, "ls-remote", remote, ref).strip():
        return None
    _net(repo, "fetch", "-q", remote, f"+{ref}:refs/remotes/{remote}/{DRAW_BRANCH}")
    return _net(repo, "rev-parse", f"refs/remotes/{remote}/{DRAW_BRANCH}").strip()


def publish_draw(repo: Path, remote: str, row: Mapping, tip: str | None) -> str:
    """Commit `row` appended to the draw ledger at `tip` onto the remote's draw branch; returns the pushed commit."""
    for _ in range(PUBLISH_ATTEMPTS):
        text = (_git(repo, "show", f"{tip}:{DRAW_LEDGER}") if tip else "") + json.dumps(row) + "\n"
        blob = _net(repo, "hash-object", "-w", "--stdin", stdin=text).strip()
        sub = _net(repo, "mktree", stdin=f"100644 blob {blob}\t{Path(DRAW_LEDGER).name}\n").strip()
        tree = _net(repo, "mktree", stdin=f"040000 tree {sub}\t{Path(DRAW_LEDGER).parent}\n").strip()
        commit = _net(repo, "commit-tree", tree, *(["-p", tip] if tip else []), "-m",
                      f"draw: {row['procedure']} run {row['run']} drew {row['drawn']}\n\nProposer: mechanism",
                      env=DRAW_AUTHOR).strip()
        try:
            _net(repo, "push", "-q", remote, f"{commit}:refs/heads/{DRAW_BRANCH}")
            return commit
        except subprocess.CalledProcessError:
            tip = draw_tip(repo, remote)
    raise RuntimeError(f"draw not published to {remote} {DRAW_BRANCH} after {PUBLISH_ATTEMPTS} attempts")


@dataclass(frozen=True)
class Election:
    """One draw: the entrant drawn, the distribution it was drawn from, and what the rounds before it showed."""
    model: str
    gamma: float
    probabilities: Mapping[str, float]
    rounds: int  # the procedure's recorded draws; unknown and unobserved ones are among them
    unknown: int  # rounds whose recorded draw names no current entrant or carries no readable probability
    unobserved: int  # rounds with no resolved forecast of the drawn model after the draw: estimate zero, kept
    clipped: int  # rounds whose loss exceeded the bound and was clipped to it

    def report(self) -> str:
        return (f"rounds {self.rounds} (unknown entrant {self.unknown}, unobserved {self.unobserved}, clipped "
                f"{self.clipped}); gamma {self.gamma:.6f}; probabilities "
                + ", ".join(f"{m} {p:.6f}" for m, p in self.probabilities.items()) + f"; drew {self.model}")


def draws_of(rows: Sequence[dict], procedure: str) -> list[dict]:
    """The procedure's recorded draws, in ledger order: rows carrying `drawn`."""
    return [r for r in rows if "drawn" in r and r.get("procedure") == procedure]


def round_loss(draw_row: Mapping, later: Sequence[Mapping], forecasts: Sequence[dict], resolved: Mapping[str, bool],
               kind: str) -> float | None:
    """The mean log-loss of the resolved forecasts the draw's model made after the draw and before that model's next
    draw, or None when there are none. A forecast belongs to the latest draw at or before its ts that drew its model."""
    stop = next((d["ts"] for d in later if d.get("drawn") == draw_row.get("drawn")), "\uffff")
    mine = [r for r in forecasts if r.get("id") in resolved and r["proposer"].get("kind") == kind
            and r["proposer"].get("model") == draw_row.get("drawn") and draw_row["ts"] <= r["ts"] < stop]
    return sum(log_loss(r["p"], resolved[r["id"]]) for r in mine) / len(mine) if mine else None


def gamma(k: int, t: int) -> float:
    """Auer et al. 2002, Cor. 4.2: the exploration rate min(1, sqrt(K ln K / ((e - 1) t))) at round t, for K entrants."""
    return min(1.0, math.sqrt(k * math.log(k) / ((math.e - 1) * t)))


def probabilities(estimate: Mapping[str, float], g: float, bound: float) -> dict[str, float]:
    """EXP3 on losses: p_m = (1 - g) w_m + g / K, w_m proportional to exp(-g L^_m / (K B))."""
    k = len(estimate)
    low = min(estimate.values())
    raw = {m: math.exp(-g * (v - low) / (k * bound)) for m, v in estimate.items()}
    return {m: (1 - g) * w / sum(raw.values()) + g / k for m, w in raw.items()}


def draw(w: Mapping[str, float], seed: int) -> str:
    """The entrant whose cumulative-probability interval holds u = ((seed * STRIDE mod DRAWS) + 1/2) / DRAWS."""
    u = ((seed * STRIDE) % DRAWS + 0.5) / DRAWS
    edges = [(m, sum(list(w.values())[:i + 1])) for i, m in enumerate(w)]
    return next((m for m, c in edges if u < c), edges[-1][0])


def elect(rows: Sequence[dict], procedure: str, entrants: Sequence[str], bound: float, seed: int) -> Election:
    """EXP3 over `entrants` at round (recorded draws + 1). Only the model a round drew is updated, by the clipped loss
    of its resolved forecasts divided by the probability *recorded* with that draw; every other entrant, and a round
    with nothing observed, gets an estimate of zero. A round that cannot be read is counted, not dropped."""
    resolved = outcomes(rows)
    forecasts = [r for r in rows if "claim" in r and isinstance(r.get("p"), (int, float))
                 and isinstance(r.get("proposer"), dict)]
    past = draws_of(rows, procedure)

    def readable(d: Mapping) -> bool:
        pr = d.get("probabilities")
        return (d.get("drawn") in entrants and isinstance(pr, dict) and isinstance(pr.get(d["drawn"]), (int, float))
                and pr[d["drawn"]] > 0 and isinstance(d.get("ts"), str))

    seen = [(d, round_loss(d, past[i + 1:], forecasts, resolved, PROCEDURES[procedure]))
            for i, d in enumerate(past) if readable(d)]
    scored = [(d, l) for d, l in seen if l is not None]
    estimate = {m: sum(min(l, bound) / d["probabilities"][m] for d, l in scored if d["drawn"] == m) for m in entrants}
    g = gamma(len(entrants), len(past) + 1)
    p = probabilities(estimate, g, bound)
    return Election(draw(p, seed), g, p, len(past), len(past) - len(seen), len(seen) - len(scored),
                    sum(1 for _, l in scored if l > bound))


def draw_row(e: Election, procedure: str, seed: int, ts: str) -> dict:
    """The ledger row written when a draw is made: what the drawn model was drawn from."""
    return {"procedure": procedure, "ts": ts, "run": seed, "gamma": e.gamma, "probabilities": dict(e.probabilities),
            "drawn": e.model}


def entrants_of(text: str, procedure: str) -> tuple[list[str], float]:
    """The procedure's entrants and the loss bound B, both pre-stated constants of the checkout's entrants file."""
    table = tomllib.loads(text)
    models, bound = table.get(procedure), table.get("bound", {}).get("loss")
    if not isinstance(models, list) or not models or not all(isinstance(m, str) and m for m in models):
        raise ValueError(f"{ENTRANTS}: no entrants for procedure {procedure!r}")
    if isinstance(bound, bool) or not isinstance(bound, (int, float)) or bound <= 0:
        raise ValueError(f"{ENTRANTS}: no [bound] loss")
    return models, float(bound)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m harness.ledger")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("surprise", help="merged PRs since <sha>, ranked by the Builder's cumulative log-loss")
    s.add_argument("--since", required=True)
    s.add_argument("--head", default="HEAD")
    s.add_argument("--repo", type=Path, default=Path("."))
    k = sub.add_parser("proposer", help="a proposer kind's record per class")
    k.add_argument("kind")
    k.add_argument("--since", default="", help="count forecasts with ts at or after this ISO timestamp")
    k.add_argument("--head", default="HEAD")
    k.add_argument("--repo", type=Path, default=Path("."))
    r = sub.add_parser("resolve", help="append a resolution for every open typed forecast whose outcome is observable")
    r.add_argument("--session", default="local", help="the resolving run's id")
    r.add_argument("--repo", type=Path, default=Path("."))
    q = sub.add_parser("price", help="what reached Guy, his latency, sessions and runner-minutes since <sha>")
    q.add_argument("--since", required=True)
    q.add_argument("--until", default=None, help="ISO timestamp; now if absent")
    q.add_argument("--head", default="HEAD")
    q.add_argument("--repo", type=Path, default=Path("."))
    e = sub.add_parser("elect", help="draw a model for a procedure by EXP3 over its entrants")
    e.add_argument("procedure", choices=sorted(PROCEDURES))
    e.add_argument("--seed", type=int, required=True)
    e.add_argument("--head", default="HEAD")
    e.add_argument("--repo", type=Path, default=Path("."))
    e.add_argument("--publish", metavar="REMOTE", default=None,
                   help=f"read the draws from, and commit this draw onto, REMOTE's {DRAW_BRANCH} branch")
    a = ap.parse_args(argv)
    if a.cmd == "proposer":
        classes = record(ledger_rows(a.repo, a.head), a.kind, a.since)
        print(f"# {a.kind}: {sum(c.made for c in classes)} forecasts in {len(classes)} classes since "
              f"{a.since or 'the first'}, at {a.head}")
        for c in classes:
            print(c)
        return 0
    if a.cmd == "resolve":
        return _resolve_cli(a.repo, a.session)
    if a.cmd == "price":
        got, since, end = github_price(a.repo, a.since, a.until, a.head)
        print(f"# price over [{since}, {end}) since {a.since}")
        for n, h in zip(got.items, got.latencies_h):
            print(f"item #{n} latency {h:.1f}h{' (open: no gfrmin action yet)' if n in got.open_items else ''}")
        for w, m in got.runner_min.items():
            print(f"workflow {w} runner-min {m:.0f}")
        print(f"pins CI minutes {got.pins_min:.0f}")
        print(f"wishes filed {len(got.wishes)}: merged {len(got.wish_latencies_h)}, open {len(got.open_wishes)}")
        print(got.status_line())
        return 0
    if a.cmd == "elect":
        models, bound = entrants_of((a.repo / ENTRANTS).read_text(), a.procedure)
        tip = draw_tip(a.repo, a.publish) if a.publish else None
        draws = (draw_rows(a.repo, tip) if tip else []) if a.publish else draw_rows(a.repo, a.head)
        got = elect(ledger_rows(a.repo, a.head) + draws, a.procedure, models, bound, a.seed)
        row = draw_row(got, a.procedure, a.seed, now_utc())
        if a.publish:
            print(f"draw published as {publish_draw(a.repo, a.publish, row, tip)} on {a.publish} {DRAW_BRANCH}",
                  file=sys.stderr)
        else:
            with (a.repo / DRAW_LEDGER).open("a") as f:
                f.write(json.dumps(row) + "\n")
        print(got.report(), file=sys.stderr)
        print(got.model)
        return 0
    ranked = surprise(merged_since(a.repo, a.since, a.head), outcomes(ledger_rows(a.repo, a.head)))
    print(f"# {len(ranked)} merged pull requests in {a.since}..{a.head}, by the Builder's cumulative log-loss")
    for r in ranked:
        print(r)
    return 0


def _resolve_cli(repo: Path, session: str) -> int:
    """Resolve every ledger in the working tree, appending each resolution to its forecast's ledger."""
    now = now_utc()
    observe = github_observer(repo, layer_price(repo))
    failed = 0
    for path in ledger_paths(repo):
        rows = _rows(path.read_text().splitlines())
        got, unread = resolve(rows, observe, now, session)
        with path.open("a") as f:
            f.writelines(json.dumps(r) + "\n" for r in got)
        typed = [x for x in open_forecasts(rows) if forecast_type(x) != FREE]
        print(f"# {path.relative_to(repo)}: {len(open_forecasts(rows))} open, {len(typed)} typed; "
              f"resolved {len(got)}, unreadable {len(unread)}")
        for r in got:
            print(f"resolved {r['id']} {r['outcome']} — {r['witness']}")
        for u in unread:
            print(f"UNREAD {u}")
        failed += len(unread)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
