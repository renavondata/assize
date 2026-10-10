"""Checkers for the court's own claims (brief 1 A4 item 7): forecast ledgers (7a), CI claims bound to the head they
describe (7b), and commit proposers (7c, with A5 F2). Each checker is a pure function returning findings; an empty
list means accepted. Readers of git and of committed files are kept apart from the rules."""

from __future__ import annotations

import argparse
import fnmatch
import functools
import hashlib
import json
import os
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class Finding:
    where: str
    code: str
    detail: str

    def __str__(self) -> str:
        return f"{self.where}: {self.code}: {self.detail}"


# ------------------------------------------------------- 7a: forecast ledgers (CLAUDE.md A1.6)

FORECAST_KEYS = ("id", "ts", "proposer", "sha_before", "claim", "p", "resolves_by")
RESOLUTION_KEYS = ("id", "ts", "proposer", "outcome")
# auditor: CLAUDE.md Amendment 2; vizier: Amendment 3; mechanism: `python -m harness.ledger resolve` (instruction #54)
PROPOSER_KINDS = frozenset({"builder", "reviewer", "guy", "counsel", "auditor", "vizier", "mechanism"})
RESOLVER_KINDS = frozenset({"reviewer", "mechanism"})
MECHANISM = "mechanism"


def forecast_id(claim: str, ts: str) -> str:
    return hashlib.sha256((claim + ts).encode()).hexdigest()[:12]


def _proposer_findings(where: str, p: object) -> list[Finding]:
    if not isinstance(p, dict) or p.get("kind") not in PROPOSER_KINDS:
        return [Finding(where, "bad_proposer", f"proposer {p!r} lacks a kind in {sorted(PROPOSER_KINDS)}")]
    lacking = [k for k in ("model", "session") if p["kind"] != "guy" and not (isinstance(p.get(k), str) and p[k])]
    return [Finding(where, "bad_proposer", f"proposer lacks {k}") for k in lacking]


def _forecast_findings(where: str, r: dict) -> list[Finding]:
    missing = [Finding(where, "missing_key", f"forecast lacks {k}") for k in FORECAST_KEYS if k not in r]
    if missing:
        return missing
    wrong_id = ([Finding(where, "bad_id", f"id {r['id']!r} is not sha256(claim + ts)[:12]")]
                if r["id"] != forecast_id(str(r["claim"]), str(r["ts"])) else [])
    bad_p = ([Finding(where, "bad_p", f"p {r['p']!r} not in (0, 1)")]
             if not (isinstance(r["p"], (int, float)) and 0 < r["p"] < 1) else [])
    return wrong_id + bad_p + _proposer_findings(where, r["proposer"])


def _self_judged(r: dict, forecaster: object) -> bool:
    """Rule 4 of the ground (instruction #54): a resolution's proposer differs from its forecast's in `session`; a
    mechanism's row always differs."""
    resolver = r.get("proposer")
    return (isinstance(resolver, dict) and resolver.get("kind") != MECHANISM and isinstance(forecaster, dict)
            and resolver.get("session") == forecaster.get("session"))


def _resolution_findings(where: str, r: dict, earlier: Mapping[str, object]) -> list[Finding]:
    """`earlier` maps each earlier forecast's id to its proposer."""
    missing = [Finding(where, "missing_key", f"resolution lacks {k}") for k in RESOLUTION_KEYS if k not in r]
    proposer = (_proposer_findings(where, r["proposer"])
                + ([Finding(where, "not_reviewer", "A1.6 assigns resolutions to the Reviewer or the resolver")]
                   if isinstance(r["proposer"], dict) and r["proposer"].get("kind") not in RESOLVER_KINDS else [])
                if "proposer" in r else [])
    orphan = ([Finding(where, "orphan", f"id {r['id']!r} matches no earlier forecast")]
              if "id" in r and r["id"] not in earlier else [])
    judged = ([Finding(where, "self_resolution", f"resolved by its forecaster's session {r['proposer']['session']!r}")]
              if "id" in r and r["id"] in earlier and _self_judged(r, earlier[r["id"]]) else [])
    outcome = ([Finding(where, "bad_outcome", f"outcome {r['outcome']!r} is not a boolean")]
               if "outcome" in r and not isinstance(r["outcome"], bool) else [])
    return missing + proposer + orphan + judged + outcome


def _parse(n: int, line: str) -> dict | Finding:
    try:
        row = json.loads(line)
    except json.JSONDecodeError as e:
        return Finding(f"row {n}", "bad_json", str(e))
    return row if isinstance(row, dict) else Finding(f"row {n}", "bad_json", "row is not an object")


def ledger_findings(lines: Sequence[str]) -> list[Finding]:
    """A row carrying `claim` is a forecast; every other row is a resolution. Rows are numbered from 1."""
    rows = [(n, _parse(n, line)) for n, line in enumerate(lines, 1) if line.strip()]
    forecast_rows = [(n, r["id"], r.get("proposer")) for n, r in rows if isinstance(r, dict) and "claim" in r
                     and "id" in r]

    def findings(n: int, r: dict | Finding) -> list[Finding]:
        if isinstance(r, Finding):
            return [r]
        if "claim" in r:
            return _forecast_findings(f"row {n}", r)
        return _resolution_findings(f"row {n}", r, {i: p for m, i, p in forecast_rows if m < n})

    return [f for n, r in rows for f in findings(n, r)]


# ------------------------------------------- 7b: CI claims bound to the head they describe (A4 item 7b)

STATUS_HEADER = re.compile(r"^# STATUS — L(\d+) — \S+ — ([0-9a-f]{7,40}) — PR #\d+", re.M)
STATUS_VERDICT = re.compile(r"^VERDICT: (.*)$", re.M)
CITATION = re.compile(r"\bpins CI run (\d+) on ([0-9a-f]{7,40})\b")
VERDICT_LINE = re.compile(r"^- L(\d+) — ", re.M)
PINS_WORKFLOW = ".github/workflows/pins.yml"


def _citation_findings(where: str, run_id: int, cited_sha: str, named_sha: str, runs: Mapping[int, dict],
                       need_success: bool) -> list[Finding]:
    run = runs.get(run_id)
    if run is None:
        return [Finding(where, "unrecorded", f"run {run_id} has no committed record (reports/L<n>/ci/{run_id}.json)")]
    head = str(run.get("head_sha", ""))
    rules = (
        (run.get("id") != run_id, "bad_record", f"record of run {run_id} carries id {run.get('id')!r}"),
        (run.get("path") != PINS_WORKFLOW, "not_pins", f"run {run_id} is workflow {run.get('path')!r}"),
        (not head.startswith(cited_sha), "citation_mismatch", f"cites run {run_id} on {cited_sha}; head_sha {head}"),
        (not head.startswith(named_sha), "head_mismatch", f"run {run_id} ran on {head}; the verdict names {named_sha}"),
        (need_success and run.get("conclusion") != "success", "not_success",
         f"run {run_id} concluded {run.get('conclusion')!r}"),
    )
    return [Finding(where, code, detail) for broken, code, detail in rules if broken]


def status_findings(where: str, text: str, runs: Mapping[int, dict]) -> list[Finding]:
    """A STATUS names its sha in the header and cites `pins CI run <id> on <sha>`; every cited run is a recorded
    `pins` run on the named sha, concluded success unless the verdict is STOPPED."""
    header = STATUS_HEADER.search(text)
    if header is None:
        return [Finding(where, "no_header", "no `# STATUS — L<n> — <date> — <sha> — PR #<k>` header")]
    verdict = STATUS_VERDICT.search(text)
    need_success = not (verdict and verdict.group(1).startswith("STOPPED"))
    cited = [(int(i), s) for i, s in CITATION.findall(text)]
    if not cited:
        return [Finding(where, "uncited", "no `pins CI run <id> on <sha>` citation")]
    return [f for i, s in cited for f in _citation_findings(where, i, s, header.group(2), runs, need_success)]


def report_findings(where: str, text: str, runs: Mapping[int, dict], from_layer: int) -> list[Finding]:
    """Every layer verdict line of layer >= `from_layer` cites a recorded, successful `pins` run on the sha it
    cites."""
    lines = [(n, line) for n, line in enumerate(text.splitlines(), 1)
             if (m := VERDICT_LINE.match(line)) and int(m.group(1)) >= from_layer]

    def findings(n: int, line: str) -> list[Finding]:
        cited = [(int(i), s) for i, s in CITATION.findall(line)]
        if not cited:
            return [Finding(f"{where}:{n}", "uncited", "verdict line cites no `pins CI run <id> on <sha>`")]
        return [f for i, s in cited for f in _citation_findings(f"{where}:{n}", i, s, s, runs, True)]

    return [f for n, line in lines for f in findings(n, line)]


def load_runs(root: Path) -> dict[int, dict]:
    """Committed run records, `reports/L<n>/ci/<run id>.json`, each a projection of the Actions API run object."""
    return {int(p.stem): json.loads(p.read_text()) for p in sorted(root.glob("reports/L*/ci/*.json"))}


# ------------------------------------------------------ 7c: commit proposers (A1.7, A4 item 7c, A5 F2)

PARTY = re.compile(r"^(?:guy|(?:builder|reviewer|counsel|auditor|vizier) \S+ \S+)$")
TRAILER_SEP = "\x1e"


@dataclass(frozen=True)
class Commit:
    sha: str
    parties: tuple[str, ...]
    paths: tuple[str, ...]
    merge: bool = False
    author: str = ""
    instructions: tuple[int, ...] = ()


def parties(trailer_values: str) -> tuple[str, ...]:
    """Every `Proposer:` trailer value of a commit, one party per line, in order."""
    return tuple(v.strip() for v in trailer_values.split(TRAILER_SEP) if v.strip())


# A commit whose `Proposer:` line git does not parse as a trailer, read from its message body instead. Keyed by full
# sha, so the exemption covers that commit only; it names the one party the body must carry, so it cannot supply a
# party the commit does not state. Each entry cites the review that found it.
PROPOSER_EXEMPTIONS: Mapping[str, str] = {
    # Instruction #54 item 5: an entry reachable from master is inert (P0m reads base..HEAD only) and was removed:
    # bb7b387 (review aa993f4 F1), b7eafee and 0a4f2b8 (make pins at 0a4f2b8). The one left is not on master.
    # P0m clean on instr-49-vizier (stacked on PR #48): the same blank line, in the review commit of PR #48; pushed,
    # and the head of a pull request awaiting Guy, so it is exempted rather than reworded.
    "e37357ed2d398cc3c1e16d65576d688e57c040c2": "reviewer claude-sonnet-5-5 a5caecbb-729c-4885-b5bf-40f1f55e76cc",
}


INSTRUCTION = re.compile(r"^#(\d+)$")


def instructions(trailer_values: str) -> tuple[int, ...]:
    """Every issue number an `Instruction: #<n>` trailer of a commit cites; a value of any other form cites none."""
    return tuple(int(m.group(1)) for v in trailer_values.split(TRAILER_SEP) if (m := INSTRUCTION.match(v.strip())))


# CLAUDE.md A1.5: Guy's instructions enter the court as issues labelled `instruction`, authored by gfrmin. A commit
# citing one by `Instruction: #<n>` carries Guy's authority on an entrenched path as `Proposer: guy` does (instruction
# #38). The issue is read through the GitHub API; a closed issue still counts. Amendment 3: Guy also signs a `draft`
# the Vizier posted by applying `instruction`, and the label counts only if its timeline shows gfrmin applied it.
# Instruction #54 item 5: the signature binds its text, so no account but gfrmin may have edited the body after it.
INSTRUCTION_AUTHOR = "gfrmin"
INSTRUCTION_LABEL = "instruction"
DRAFT_LABEL = "draft"


@dataclass(frozen=True)
class Edit:
    editor: str | None  # None: a deleted account
    at: str  # ISO-8601 UTC, as the API gives it


@dataclass(frozen=True)
class Issue:
    author: str
    labels: tuple[str, ...]
    state: str = ""
    labeled_by: str | None = None  # the account that applied the standing `instruction` label, from the timeline
    labeled_at: str | None = None  # when it applied it
    edits: tuple[Edit, ...] | None = None  # the body's edits (GraphQL `userContentEdits`); None: not read


def _standing(events: Sequence[Mapping]) -> Mapping | None:
    """The `labeled instruction` event standing at the end of an issue timeline: the last such event with no
    `unlabeled instruction` after it, or None."""
    def step(standing: Mapping | None, e: Mapping) -> Mapping | None:
        if (e.get("label") or {}).get("name") != INSTRUCTION_LABEL:
            return standing
        return {"labeled": e, "unlabeled": None}.get(e.get("event"), standing)

    return functools.reduce(step, events, None)


def instruction_labeler(events: Sequence[Mapping]) -> str | None:
    """The account whose `labeled instruction` event stands at the end of an issue timeline, or None."""
    e = _standing(events)
    return (e.get("actor") or {}).get("login") if e is not None else None


def instruction_labeled_at(events: Sequence[Mapping]) -> str | None:
    """When the standing `labeled instruction` event was made, or None."""
    e = _standing(events)
    return e.get("created_at") if e is not None else None


def _after(a: str, b: str) -> bool:
    def t(x: str) -> datetime:
        return datetime.fromisoformat(x.replace("Z", "+00:00"))
    return t(a) > t(b)


def refusing_edit(issue: Issue) -> Edit | None:
    """The first edit of the body by an account other than gfrmin after gfrmin's signature, or None."""
    return next((e for e in issue.edits or () if e.editor != INSTRUCTION_AUTHOR and issue.labeled_at is not None
                 and _after(e.at, issue.labeled_at)), None)


def authorises(issue: Issue | None) -> bool:
    """An issue carries Guy's authority if it is labelled `instruction`, gfrmin applied that label, and gfrmin authored
    it or it is a `draft` (Amendment 3), open or closed; and its body's edits were read and none after the signature
    was by another account (instruction #54 item 5)."""
    return (issue is not None and INSTRUCTION_LABEL in issue.labels and issue.labeled_by == INSTRUCTION_AUTHOR
            and (issue.author == INSTRUCTION_AUTHOR or DRAFT_LABEL in issue.labels)
            and issue.labeled_at is not None and issue.edits is not None and refusing_edit(issue) is None)


def exempt_parties(sha: str, message: str, exemptions: Mapping[str, str]) -> tuple[str, ...]:
    """The exempted party of `sha`, if `exemptions` lists it and its message carries that exact `Proposer:` line."""
    party = exemptions.get(sha)
    return (party,) if party is not None and f"Proposer: {party}" in message.splitlines() else ()


# Brief 1 A9: a commit with more than one parent is a GitHub merge, whose proposer is its author account and which needs
# no trailer. GitHub sets a merge's author from the merging account: its noreply address `<id>+<login>@users.noreply.
# github.com`, or an address the account's owner commits under (ACCOUNT_EMAILS; Guy's two stated on 2026-10-08). Any
# other author on a merge has no party.
MERGE_AUTHORS: Mapping[str, str] = {"gfrmin": "guy", "assize-builder": "builder", "assize-reviewer": "reviewer"}
ACCOUNT_EMAILS: Mapping[str, str] = {"guy@publicdatamarket.com": "gfrmin", "git@gfrm.in": "gfrmin",
                                     "assize-builder@gfrm.in": "assize-builder",
                                     "assize-reviewer@gfrm.in": "assize-reviewer"}
NOREPLY = re.compile(r"^(?:\d+\+)?([A-Za-z0-9-]+)@users\.noreply\.github\.com$")


def account(email: str) -> str | None:
    """The GitHub account an author address names: a noreply address's login, or a listed bot address's account."""
    m = NOREPLY.match(email)
    return m.group(1) if m else ACCOUNT_EMAILS.get(email)


def merge_parties(email: str) -> tuple[str, ...]:
    """The one party of a merge authored by `email`, from MERGE_AUTHORS; none for any other author."""
    party = MERGE_AUTHORS.get(account(email))
    return (party,) if party is not None else ()


def codeowners_patterns(text: str) -> tuple[str, ...]:
    return tuple(line.split()[0].lstrip("/") for line in text.splitlines()
                 if line.strip() and not line.lstrip().startswith("#"))


def entrenched(path: str, patterns: Sequence[str]) -> bool:
    return any(path.startswith(p) if p.endswith("/") else path == p for p in patterns)


def needs_guy(c: Commit, patterns: Sequence[str]) -> list[str]:
    """The entrenched paths `c` touches without a `guy` party."""
    return sorted(p for p in c.paths if entrenched(p, patterns)) if "guy" not in c.parties else []


def commit_findings(c: Commit, patterns: Sequence[str], issues: Mapping[int, Issue] = {}) -> list[Finding]:
    """Findings on one commit; `issues` holds the issues its `Instruction:` trailers cite, as read (a missing one
    could not be read, so it authorises nothing)."""
    where = f"commit {c.sha[:12]}"
    if c.merge and not c.parties:
        return [Finding(where, "unknown_merge_author",
                        f"merge authored by {c.author!r}, no account of {sorted(MERGE_AUTHORS)}")]
    if not c.parties:
        return [Finding(where, "no_proposer", "no `Proposer:` trailer")]
    malformed = [Finding(where, "bad_party", f"{p!r} is not `guy` or `<kind> <model> <session>`")
                 for p in c.parties if not (PARTY.match(p) or c.merge and p in MERGE_AUTHORS.values())]
    touched = needs_guy(c, patterns)
    instructed = any(authorises(issues.get(n)) for n in c.instructions)
    unsigned = ([Finding(where, "entrenched_without_guy",
                         f"touches {touched}; parties {list(c.parties)}; instructions "
                         f"{[(n, issues.get(n)) for n in c.instructions]}")]
                if touched and not instructed else [])
    return malformed + unsigned


# Git reads no user or system configuration here, so no local setting (e.g. log.showSignature) can alter what is parsed.
GIT_ENV = {"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True,
                          env=os.environ | GIT_ENV).stdout


def branch_commits(repo: Path, base: str, head: str = "HEAD",
                   exemptions: Mapping[str, str] = PROPOSER_EXEMPTIONS) -> list[Commit]:
    """Commits in base..head, oldest first, with their `Proposer:` parties (parsed by git; for a commit with none,
    its exempted party, if any; for a merge, its author account's party only, brief 1 A9) and the paths each changes
    itself: for a merge, only paths differing from every parent (`-c`), so content a merge brings in from its other parent is attributed to the commit that authored it."""
    fmt = ("%H%x1f%P%x1f%ae%x1f%(trailers:key=Proposer,valueonly,separator=%x1e)%x1f"
           "%(trailers:key=Instruction,valueonly,separator=%x1e)%x1f%B%x1d")
    records = [r.strip("\n") for r in _git(repo, "log", "--reverse", f"--format={fmt}", f"{base}..{head}")
               .split("\x1d") if r.strip()]

    def commit(record: str) -> Commit:
        sha, parents, email, values, cited, message = record.split("\x1f", 5)
        paths = _git(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", "--root", "-c", sha).splitlines()
        if len(parents.split()) > 1:
            return Commit(sha, merge_parties(email), tuple(paths), merge=True, author=email)
        return Commit(sha, parties(values) or exempt_parties(sha, message, exemptions), tuple(paths), author=email,
                      instructions=instructions(cited))

    return [commit(r) for r in records]


EDITS_QUERY = """query($owner: String!, $repo: String!, $n: Int!, $endCursor: String) {
  repository(owner: $owner, name: $repo) { issue(number: $n) {
    userContentEdits(first: 100, after: $endCursor) { nodes { editor { login } editedAt }
                                                      pageInfo { hasNextPage endCursor } } } } }"""


def inert_exemptions(repo: Path, base: str,
                     exemptions: Mapping[str, str] = PROPOSER_EXEMPTIONS) -> list[Finding]:
    """An exemption whose commit is reachable from `base` (master) is inert: P0m reads only base..HEAD, so it can
    never apply, and it is a finding (instruction #54 item 5). A sha this clone does not hold is not reachable."""
    def reachable(sha: str) -> bool:
        return subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", sha, base], capture_output=True,
                              env=os.environ | GIT_ENV).returncode == 0

    return [Finding(f"exemption {sha[:12]}", "inert_exemption", f"reachable from {base[:12]}; P0m never reads it")
            for sha in exemptions if reachable(sha)]


# ------------------------------------------------------ the ground, rules 1 and 2 (instruction #54 items 1 and 2)

APPEND_ONLY = ("reports/L*/forecasts.jsonl", "reports/L*/review-*.md", "reports/L*/audit-*.md", "REPORT.md",
               "reports/draws.jsonl")


def append_only_path(path: str) -> bool:
    return any(fnmatch.fnmatchcase(path, g) and path.count("/") == g.count("/") for g in APPEND_ONLY)


def removed_lines(diff: str) -> dict[str, int]:
    """Lines a unified diff removes, per append-only path it touches (a path deleted or renamed away included). A
    `--- ` line is a header only before the file's first hunk, so a removed line beginning `-- ` is still counted."""
    def step(acc: tuple[str | None, bool, dict[str, int]], line: str) -> tuple[str | None, bool, dict[str, int]]:
        path, in_hunk, removed = acc
        if line.startswith("diff --git "):
            return None, False, removed
        if not in_hunk and line.startswith("--- "):
            old = line[4:].strip()
            return (old[2:] if old.startswith("a/") else None), False, removed
        if line.startswith("@@"):
            return path, True, removed
        if in_hunk and line.startswith("-") and path is not None and append_only_path(path):
            return path, True, removed | {path: removed.get(path, 0) + 1}
        return path, in_hunk, removed

    return functools.reduce(step, diff.splitlines(), (None, False, {}))[2]


def append_only(repo: Path, base: str, head: str = "HEAD") -> list[Finding]:
    """Rule 1 of the ground: every commit in base..head only adds lines to the append-only paths; a merge only adds
    lines relative to each of its parents. Each commit is diffed by `git diff-tree` against each parent in turn
    (`-c` would list only paths differing from every parent, hiding a merge that takes one side whole)."""
    shas = _git(repo, "rev-list", "--reverse", "--parents", f"{base}..{head}").splitlines()

    def findings(line: str) -> list[Finding]:
        sha, *parents = line.split()
        diffs = [(p, _git(repo, "diff-tree", "-p", "-U0", "--no-color", "--no-renames", p, sha)) for p in parents]
        return [Finding(f"commit {sha[:12]}", "ledger_rewrite", f"removes {n} lines of {path} relative to {p[:12]}")
                for p, d in diffs for path, n in sorted(removed_lines(d).items())]

    return [f for line in shas for f in findings(line)]


def forecast_rows_added(repo: Path, base: str, head: str = "HEAD") -> dict[str, list[str]]:
    """Per ledger, the forecast rows (rows carrying `claim`) the diff base...head adds, as committed lines."""
    diff = _git(repo, "diff", "-U0", "--no-color", "--no-renames", f"{base}...{head}", "--",
                ":(glob)reports/L*/forecasts.jsonl")

    def step(acc: tuple[str | None, dict[str, list[str]]], line: str) -> tuple[str | None, dict[str, list[str]]]:
        path, added = acc
        if line.startswith("+++ "):
            new = line[4:].strip()
            return (new[2:] if new.startswith("b/") else None), added
        if line.startswith("+") and path is not None and isinstance(row := _parse(0, line[1:]), dict) \
                and "claim" in row:
            return path, added | {path: added.get(path, []) + [line[1:]]}
        return path, added

    return functools.reduce(step, diff.splitlines(), (None, {}))[1]


def first_pins_run(runs: Sequence[Mapping]) -> Mapping | None:
    """The earliest `pins` run with event pull_request among `runs` (Actions API run objects), or None."""
    pins = [r for r in runs if r.get("path") == PINS_WORKFLOW and r.get("event") == "pull_request"]
    return min(pins, key=lambda r: (str(r.get("created_at", "")), int(r.get("id", 0))), default=None)


def late_forecasts(added: Mapping[str, Sequence[str]], at_first_run: Mapping[str, str | None],
                   first_sha: str) -> list[Finding]:
    """Rule 2 of the ground: every forecast row a pull request adds is present in its ledger's text at the head of
    the first `pins` run on its branch (`at_first_run`: ledger path -> text there, None if the ledger is absent)."""
    def present(path: str, row: str) -> bool:
        return row in (at_first_run.get(path) or "").splitlines()

    return [Finding(f"{path}", "late_forecast", f"row {row[:80]!r}... is not in the tree at {first_sha[:12]}, the "
                                                f"head of the first pins run")
            for path, rows in sorted(added.items()) for row in rows if not present(path, row)]


def load_issues(repo: Path, numbers: Sequence[int]) -> dict[int, Issue]:
    """The issues `numbers` name, with their timelines and body edits, read through the GitHub API (`gh api`, from
    `repo`'s remote). One that cannot be read is left out, so it authorises nothing; edits that cannot be read are
    None, so the issue authorises nothing."""
    def gh(path: str, *args: str) -> str:
        return subprocess.run(["gh", "api", path, *args], cwd=repo, check=True, capture_output=True, text=True,
                              timeout=60).stdout

    def edits(n: int) -> tuple[Edit, ...] | None:
        try:
            out = gh("graphql", "--paginate", "-F", "owner={owner}", "-F", "repo={repo}", "-F", f"n={n}",
                     "-f", f"query={EDITS_QUERY}", "--jq", ".data.repository.issue.userContentEdits.nodes[]")
        except (OSError, subprocess.SubprocessError) as e:
            print(f"    issue #{n}: edits not read ({e})")
            return None
        nodes = [json.loads(line) for line in out.splitlines() if line.strip()]
        return tuple(Edit((e.get("editor") or {}).get("login"), str(e["editedAt"])) for e in nodes)

    def read(n: int) -> Issue | None:
        try:
            out = gh(f"repos/{{owner}}/{{repo}}/issues/{n}", "--jq",
                     "{author: .user.login, labels: [.labels[].name], state: .state}")
            timeline = gh(f"repos/{{owner}}/{{repo}}/issues/{n}/timeline?per_page=100", "--paginate", "--jq", ".[]")
        except (OSError, subprocess.SubprocessError) as e:
            print(f"    issue #{n}: not read ({e})")
            return None
        row = json.loads(out)
        events = [json.loads(line) for line in timeline.splitlines() if line.strip()]
        return Issue(str(row["author"]), tuple(row["labels"]), str(row["state"]), instruction_labeler(events),
                     instruction_labeled_at(events), edits(n))

    read_ = {n: read(n) for n in sorted(set(numbers))}
    return {n: i for n, i in read_.items() if i is not None}


def _edits_said(i: Issue) -> str:
    if i.edits is None:
        return "body edits not read"
    e = refusing_edit(i)
    return (f"body edited by {e.editor} at {e.at}, after the signature" if e is not None
            else f"{len(i.edits)} body edits, none by another account after the signature")


def main(argv: Sequence[str] | None = None) -> int:
    """`python -m harness.claims signed <n>...`: whether each issue carries Guy's authority (Amendment 3). The Builder
    acts only on an issue printed `signed`."""
    ap = argparse.ArgumentParser(prog="python -m harness.claims")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("signed", help="whether each issue is an instruction Guy signed")
    s.add_argument("numbers", type=int, nargs="*")
    s.add_argument("--repo", type=Path, default=Path("."))
    a = ap.parse_args(argv)
    issues = load_issues(a.repo, a.numbers)
    for n in a.numbers:
        i = issues.get(n)
        verdict = "signed" if authorises(i) else "refused"
        why = (f"author {i.author}, labels {list(i.labels)}, instruction label applied by {i.labeled_by} at "
               f"{i.labeled_at}, {_edits_said(i)}" if i else "")
        print(f"#{n} {verdict}: {why or 'not read'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
