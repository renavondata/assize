"""Checks on a session's own log (`claude -p ... --output-format stream-json`), instruction #110 Part D: files under
`.github/` or `harness/` are changed with the Edit and Write tools, never through a Bash call; and a session that ends on
master has opened a pull request or filed an issue. Each checker is a pure function returning findings."""

from __future__ import annotations

import functools
import json
import re
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


def final_branch(cs: Sequence[Call], start: str = "master") -> str:
    """The branch the session's successful Bash calls leave it on, starting from `start`."""
    def step(branch: str, c: Call) -> str:
        command = str(c.input.get("command", ""))
        if c.tool != "Bash" or c.error:
            return branch
        moves = sorted([(m.start(), m.group(1)) for p in (BRANCH_TO, BRANCH_BACK) for m in p.finditer(command)
                        if not m.group(1).startswith("-")]
                       + [(m.start(), f"pr-{m.group(1)}") for m in BRANCH_PR.finditer(command)])
        return moves[-1][1] if moves else branch

    return functools.reduce(step, cs, start)


def silent_master_stop(cs: Sequence[Call]) -> list[Finding]:
    """A session that ends on master having opened no pull request and filed no issue."""
    opened = any(c.tool == "Bash" and not c.error and OPENED.search(str(c.input.get("command", ""))) for c in cs)
    return ([Finding("session", "silent_master_stop", "ends on master with no pull request and no issue")]
            if final_branch(cs) == "master" and not opened else [])


def session_findings(events: Iterable[Mapping]) -> list[Finding]:
    cs = calls(events)
    return shell_edits(cs) + silent_master_stop(cs)
