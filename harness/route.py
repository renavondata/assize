"""Where a red pins run or a conflicted pull request goes (instruction #126).

`decide` is the whole rule; `.github/workflows/failed.yml` calls it and acts on what it prints. It is stdlib-only, so
the workflow runs it with the runner's `python3` from a checkout of master.
"""
from __future__ import annotations

import sys

# A1.5: three review rounds on one branch without approval hand the branch to Guy. A `blocked` label is a round.
ROUNDS = 3

EVENTS = ("pins_red", "pushed")  # a red pins run on a pull request; a push to master, for each open pull request


def decide(event: str, rounds: int, mergeable: str) -> str:
    """`label` (apply `blocked`, restarting the pull request's Builder), `issue` (file the issue assigned to gfrmin)
    or `nothing`, from the event, the `labeled blocked` events already on the pull request's timeline, and its
    `mergeable` state (`MERGEABLE`, `CONFLICTING` or `UNKNOWN`)."""
    if event not in EVENTS:
        raise ValueError(f"unknown event {event!r}; known: {EVENTS}")
    if event == "pushed" and mergeable != "CONFLICTING":
        return "nothing"
    return "label" if rounds < ROUNDS else "issue"


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: python3 -m harness.route <pins_red|pushed> <prior blocked rounds> <mergeable>", file=sys.stderr)
        return 2
    print(decide(argv[0], int(argv[1]), argv[2]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
