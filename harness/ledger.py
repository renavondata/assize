"""`python -m harness.ledger surprise --since <sha>`: the pull requests merged into master since <sha>, ranked by the
Builder's cumulative log-loss on the forecasts each added (instruction #46 item 5). A pull request's forecasts are the
forecast rows its merge adds to any `reports/L*/forecasts.jsonl`, read from git; a forecast's outcome is the last
resolution of its id in the ledgers at the head. Unresolved forecasts add no loss and are counted, never dropped."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from harness.claims import _git

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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m harness.ledger")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("surprise", help="merged PRs since <sha>, ranked by the Builder's cumulative log-loss")
    s.add_argument("--since", required=True)
    s.add_argument("--head", default="HEAD")
    s.add_argument("--repo", type=Path, default=Path("."))
    a = ap.parse_args(argv)
    ranked = surprise(merged_since(a.repo, a.since, a.head), outcomes(ledger_rows(a.repo, a.head)))
    print(f"# {len(ranked)} merged pull requests in {a.since}..{a.head}, by the Builder's cumulative log-loss")
    for r in ranked:
        print(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
