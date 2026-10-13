"""Checks on a session's own log (`claude -p ... --output-format stream-json`), instruction #110 Part D: files under
`.github/` or `harness/` are changed with the Edit and Write tools, never through a Bash call; and a session that ends on
master has opened a pull request or filed an issue. Each checker is a pure function returning findings.

Instruction #112 Parts A and D: a session's first act is its declaration comment; a session on a pull-request branch
appends no forecast row; a session that writes no STATUS, review or audit file posts its stop comment. Those two
comments are the two a session makes about itself. `python -m harness.sessions tokens <log>` prints the tokens a
session used, for its declaration's end; `python -m harness.sessions limit <log>` exits 1 when the session ended with
`usage_limit_reached`, the step the price counts (`ledger.LIMIT_STEP`)."""

from __future__ import annotations

import functools
import itertools
import json
import re
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from harness.claims import Finding


@dataclass(frozen=True)
class Call:
    """One tool call of the session, with whether the harness answered it with an error (a denial included)."""
    id: str
    tool: str
    input: Mapping
    error: bool


def calls(events: Iterable[Mapping]) -> list[Call]:
    """The session's tool calls in order, each joined to its result."""
    events = list(events)

    def content(e: Mapping, kind: str) -> list[Mapping]:
        message = e.get("message") or {}
        return [c for c in message.get("content") or [] if isinstance(c, dict) and c.get("type") == kind] \
            if e.get("type") in ("assistant", "user") else []

    errors = {c.get("tool_use_id"): bool(c.get("is_error")) for e in events for c in content(e, "tool_result")}
    return [Call(str(c.get("id")), str(c.get("name")), c.get("input") or {}, errors.get(c.get("id"), False))
            for e in events for c in content(e, "tool_use")]


def parse(text: str) -> list[dict]:
    """The JSON objects of a stream-json log, one per line; other lines (stderr interleaved) are skipped."""
    def row(line: str) -> dict | None:
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            return None
        return r if isinstance(r, dict) else None

    return [r for line in text.splitlines() if line.strip().startswith("{") and (r := row(line)) is not None]


# A Bash command changes a guarded file if it redirects or tees into one, edits one in place, copies or moves onto one,
# or runs an inline script or heredoc that names one (the build run 38152587119 class: `python3 - <<EOF`).
GUARDED = r"""['"]?(?:\./)?(?:\.github|harness)/"""
SHELL_WRITES = tuple(re.compile(p, re.S) for p in (
    rf">>?\s*{GUARDED}",
    rf"\btee\s+(?:-a\s+)?{GUARDED}",
    rf"\b(?:sed|perl)\s+(?:-\w+\s+)*-\w*i\b.*{GUARDED}",
    rf"\b(?:cp|mv|install)\b[^|;&\n]*\s{GUARDED}\S*\s*(?:$|[|;&\n])",
    rf"(?:\bpython3?\s+-c?\s|<<).*{GUARDED}",
))


def shell_edits(cs: Sequence[Call]) -> list[Finding]:
    """A Bash call that changes a file under `.github/` or `harness/`."""
    return [Finding(f"call {c.id}", "shell_edit", f"Bash changes a guarded file: {str(c.input.get('command'))[:120]!r}")
            for c in cs if c.tool == "Bash" and any(p.search(str(c.input.get("command", ""))) for p in SHELL_WRITES)]


BRANCH_TO = re.compile(r"\bgit\s+(?:checkout|switch)\s+(?:-q\s+)?-[bBcC]\s+(\S+)")
BRANCH_PR = re.compile(r"\bgh\s+pr\s+checkout\s+(\S+)")
BRANCH_BACK = re.compile(r"\bgit\s+(?:checkout|switch)\s+(?:-q\s+)?(\S+)")
OPENED = re.compile(r"\bgh\s+(?:pr|issue)\s+create\b")


def _step(branch: str, c: Call) -> str:
    """The branch a call leaves the session on, from `branch`."""
    command = str(c.input.get("command", ""))
    if c.tool != "Bash" or c.error:
        return branch
    moves = sorted([(m.start(), m.group(1)) for p in (BRANCH_TO, BRANCH_BACK) for m in p.finditer(command)
                    if not m.group(1).startswith("-")]
                   + [(m.start(), f"pr-{m.group(1)}") for m in BRANCH_PR.finditer(command)])
    return moves[-1][1] if moves else branch


def final_branch(cs: Sequence[Call], start: str = "master") -> str:
    """The branch the session's successful Bash calls leave it on, starting from `start`."""
    return functools.reduce(_step, cs, start)


def silent_master_stop(cs: Sequence[Call]) -> list[Finding]:
    """A session that ends on master having opened no pull request and filed no issue."""
    opened = any(c.tool == "Bash" and not c.error and OPENED.search(str(c.input.get("command", ""))) for c in cs)
    return ([Finding("session", "silent_master_stop", "ends on master with no pull request and no issue")]
            if final_branch(cs) == "master" and not opened else [])


def session_findings(events: Iterable[Mapping]) -> list[Finding]:
    cs = calls(events)
    return shell_edits(cs) + silent_master_stop(cs)


# Instruction #112 Part A item 1 and item 5: `<procedure> run <run id> started <ISO time> on #<n>: expected <m> minutes`,
# naming the model. Part D item 2: `<procedure> run <id> stopped <ISO>:`.
PROCEDURE = r"(?:build|review|audit|vizier)"
DECLARATION = re.compile(rf"\b{PROCEDURE} run \S+ started \S+ on #\d+: expected \d+ minutes; model \S+")
STOPPED = re.compile(rf"\b{PROCEDURE} run \S+ stopped \S+:")
# A call that changes something outside the session: a file, a commit, a push, or a write through the GitHub API.
# Reads (git log, gh pr view, gh api GETs and GraphQL queries) are not acts.
ACTS = tuple(re.compile(p) for p in (
    r"\bgit\s+(?:commit|push|merge|tag|rebase)\b",
    r"\bgh\s+(?:pr|issue|label)\s+(?:create|comment|edit|close|reopen|merge|review|delete)\b",
    r"\bgh\s+api\s+(?!graphql\b)[^|;&\n]*\s(?:-X\s*(?:POST|PATCH|PUT|DELETE)|-[fF]\s|--(?:raw-)?field\b|--input\b)",
))
FILE_TOOLS = ("Edit", "Write", "NotebookEdit")


def _command(c: Call) -> str:
    return str(c.input.get("command", "")) if c.tool == "Bash" else ""


def acts(c: Call) -> bool:
    return c.tool in FILE_TOOLS or (c.tool == "Bash" and not c.error and any(p.search(_command(c)) for p in ACTS))


def undeclared(cs: Sequence[Call]) -> list[Finding]:
    """The session's first act is not its declaration comment (instruction #112 Part A item 1)."""
    first = next((c for c in cs if acts(c)), None)
    return ([] if first is not None and DECLARATION.search(_command(first)) else
            [Finding("session", "undeclared_session", "first act is not the declaration "
                                                      f"({(_command(first) or (first.tool if first else 'none'))[:80]!r})")])


LEDGER_FILE = re.compile(r"(?:^|/)reports/L\d+/forecasts(?:\.jsonl|/[^/]+\.jsonl)$")
LEDGER_APPEND = re.compile(r">>?\s*['\"]?\S*reports/L\d+/forecasts(?:\.jsonl|/\S+\.jsonl)")


def adds_forecast(c: Call) -> bool:
    """A call that adds a forecast row (a row with a `claim`) to a ledger; resolutions carry none."""
    def claims(text: str) -> set[str]:
        return {line for line in text.splitlines() if '"claim"' in line}

    if c.tool in ("Edit", "Write") and LEDGER_FILE.search(str(c.input.get("file_path", ""))):
        new = str(c.input.get("new_string", c.input.get("content", "")))
        return bool(claims(new) - claims(str(c.input.get("old_string", ""))))
    return c.tool == "Bash" and not c.error and bool(LEDGER_APPEND.search(_command(c))) and '"claim"' in _command(c)


def pr_branch_forecasts(cs: Sequence[Call], start: str = "master") -> list[Finding]:
    """A forecast row added on a pull-request branch: one the session did not create, master excepted (instruction
    #112 Part D item 1)."""
    before = list(itertools.accumulate(cs, _step, initial=start))[:-1]
    created = list(itertools.accumulate(
        cs, lambda s, c: s | ({m.group(1) for m in BRANCH_TO.finditer(_command(c))} if not c.error else set()),
        initial=frozenset()))[:-1]
    return [Finding(f"call {c.id}", "pr_branch_forecast", f"forecast row added on pull-request branch {b}")
            for c, b, made in zip(cs, before, created) if adds_forecast(c) and b != "master" and b not in made]


ROUTED_FILE = re.compile(r"(?:^|/)reports/L\d+/(?:STATUS|status/[^/]+|review-[^/]+|audit-[^/]+)\.md$")


def silent_stop(cs: Sequence[Call]) -> list[Finding]:
    """A session that ends with no STATUS, review or audit file written and no stop comment: an unrouted exit
    (instruction #112 Part D item 2)."""
    routed = any(c.tool in ("Edit", "Write") and not c.error and ROUTED_FILE.search(str(c.input.get("file_path", "")))
                 for c in cs) or any(acts(c) and STOPPED.search(_command(c)) for c in cs)
    return [] if routed else [Finding("session", "silent_stop", "ends with no STATUS, review or audit file and no "
                                                                "stop comment")]


def declared_findings(events: Iterable[Mapping], start: str = "master") -> list[Finding]:
    """The two comments a session makes about itself, and the rows it may not add (instruction #112 Parts A and D).
    `start`: the branch the workflow checked out before the session began."""
    cs = calls(events)
    return undeclared(cs) + pr_branch_forecasts(cs, start) + silent_stop(cs)


def tokens(events: Iterable[Mapping]) -> int:
    """The tokens a session used: each assistant message's usage, counted once per message id."""
    usage = {str((e.get("message") or {}).get("id")): (e.get("message") or {}).get("usage") or {}
             for e in events if e.get("type") == "assistant"}
    return sum(int(u.get(k) or 0) for u in usage.values()
               for k in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))


LIMIT = "usage_limit_reached"


def limit_reached(events: Sequence[Mapping]) -> bool:
    """The session's last `result` event carries `usage_limit_reached` (instruction #112 Part A item 5)."""
    results = [e for e in events if e.get("type") == "result"]
    return bool(results) and LIMIT in json.dumps(results[-1])


def main(argv: list[str] | None = None) -> int:
    # Instruction #113 Part A: the self-run appends `--dry-run` to every harness call of the session workflows. Both
    # commands only read the log and print, so the flag is accepted and changes nothing.
    args = [a for a in (sys.argv[1:] if argv is None else argv) if a != "--dry-run"]
    if len(args) != 2 or args[0] not in ("tokens", "limit"):
        print("usage: python -m harness.sessions tokens|limit <stream-json log> [--dry-run]", file=sys.stderr)
        return 2
    try:
        with open(args[1]) as f:
            events = parse(f.read())
    except OSError as e:  # no log: the session never ran, so it did not end at the limit; said, not dropped
        print(f"{args[1]}: not read ({e}); counted as not ending with {LIMIT}", file=sys.stderr)
        events = []
    if args[0] == "tokens":
        print(tokens(events))
        return 0
    reached = limit_reached(events)
    print(f"{args[1]}: {'ended with ' + LIMIT if reached else 'did not end with ' + LIMIT}")
    return 1 if reached else 0


if __name__ == "__main__":
    sys.exit(main())
