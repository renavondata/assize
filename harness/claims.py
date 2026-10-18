"""Checkers for the court's own claims (brief 1 A4 item 7): forecast ledgers (7a), CI claims bound to the head they
describe (7b), and commit proposers (7c, with A5 F2). Each checker is a pure function returning findings; an empty
list means accepted. Readers of git and of committed files are kept apart from the rules."""

from __future__ import annotations

import argparse
import fnmatch
import functools
import hashlib
import itertools
import json
import os
import re
import subprocess
import sys
import tempfile
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
    closed = r.get("type") == "guy_picks"  # a deterministic entrant's pick has mass 0 or 1 (instruction #111)
    bad_p = ([Finding(where, "bad_p", f"p {r['p']!r} not in {'[0, 1]' if closed else '(0, 1)'}")]
             if not (isinstance(r["p"], (int, float)) and (0 <= r["p"] <= 1 if closed else 0 < r["p"] < 1)) else [])
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
# The files a pull request writes are its own (instruction #135): a session appends to `forecasts/<session id>.jsonl` and
# writes `status/<branch>.md`; the single files are frozen and still read.
LEDGER_GLOBS = ("reports/L*/forecasts.jsonl", "reports/L*/forecasts/*.jsonl")
STATUS_GLOBS = ("reports/L*/STATUS.md", "reports/L*/status/*.md")


def session_files(layer: int, session: str, branch: str) -> dict[str, str]:
    """The three files one Builder session writes, each a path no other session writes (instruction #135)."""
    return {"forecasts": f"reports/L{layer}/forecasts/{session}.jsonl", "status": f"reports/L{layer}/status/{branch}.md",
            "proposer": f"harness/proposer.d/{branch}.toml"}


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


OBLIGATION_ROW = re.compile(r"^(\d+)\. (.*)$")
OBLIGATION_DISCHARGED = re.compile(r"\bdischarged by (P\w+)\b")
OBLIGATION_CARRIED = "carried to the agent repository as a design input"
OBLIGATION_MUTANT = re.compile(r"\bmutant (P\w+/\w+)\b")


def obligation_findings(where: str, text: str, registry: Mapping[str, frozenset[str]], first: int, last: int
                        ) -> list[Finding]:
    """`reports/L2/obligations-44-55.md` (Wish #179, instruction #181): each obligation number first..last has exactly
    one row `<n>. <disposition>: <reason>` with exactly one disposition, `carried to the agent repository as a design
    input` or `discharged by <pin> ...; mutant <pin>/<mutant>; pins CI run <id> on <sha>`; a discharged row names a pin
    and a mutant of it that `registry` (pin name to its `pin/mutant` labels) holds."""
    rows = [(n, m) for n, line in enumerate(text.splitlines(), 1) if (m := OBLIGATION_ROW.match(line))]
    seen = [int(m.group(1)) for _, m in rows]

    def row(n: int, m: re.Match) -> list[Finding]:
        at, body = f"{where}:{n}", m.group(2)
        pin, mutant = OBLIGATION_DISCHARGED.search(body), OBLIGATION_MUTANT.search(body)
        carried = OBLIGATION_CARRIED in body
        if bool(pin) == carried:
            return [Finding(at, "disposition", f"obligation {m.group(1)}: both or neither of discharged/carried")]
        if carried:
            return []
        return ([] if mutant and CITATION.search(body) else
                [Finding(at, "discharge_uncited", f"obligation {m.group(1)}: no `mutant <pin>/<mutant>` or no "
                                                  f"`pins CI run <id> on <sha>`")]) + (
            [] if pin.group(1) in registry and mutant and mutant.group(1) in registry[pin.group(1)] else
            [Finding(at, "not_in_registry", f"obligation {m.group(1)}: pin {pin.group(1)} or its mutant "
                                            f"{mutant and mutant.group(1)} is not in the registry")])

    return ([Finding(where, "missing", f"obligation {i} has no row") for i in range(first, last + 1) if i not in seen]
            + [Finding(where, "duplicate", f"obligation {i} has {seen.count(i)} rows")
               for i in sorted(set(seen)) if seen.count(i) > 1 or not first <= i <= last]
            + [f for n, m in rows for f in row(n, m)])


def load_runs(root: Path) -> dict[int, dict]:
    """Committed run records, `reports/L<n>/ci/<run id>.json`, each a projection of the Actions API run object."""
    return {int(p.stem): json.loads(p.read_text()) for p in sorted(root.glob("reports/L*/ci/*.json"))}


def status_check(root: Path, paths: Sequence[Path]) -> list[Finding]:
    """`status_findings` on each STATUS file against the run records committed under `root` (instruction #211 item
    2): what P0l would say of them, said before they are pushed."""
    runs = load_runs(root)
    return [f for p in paths for f in status_findings(str(p), p.read_text(), runs)]


# ------------------------------------------------------ 7c: commit proposers (A1.7, A4 item 7c, A5 F2)

# Instruction #239 item 1: `mechanism <tool> <run id>`, the resolver's party (Amendment 4 rule 3), with `<tool>` a
# dotted module name and `<run id>` digits or `local`. It carries no one's authority: `needs_guy` reads only `guy`.
PARTY = re.compile(r"^(?:guy|(?:builder|reviewer|counsel|auditor|vizier) \S+ \S+"
                   r"|mechanism [A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+ (?:\d+|local))$")
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


def malformed_parties(where: str, ps: Sequence[str], merge: bool = False) -> list[Finding]:
    """A `bad_party` finding per party outside PARTY's grammar; a merge may also name its author's MERGE_AUTHORS party.
    The one reader of that grammar, for P0m (`commit_findings`) and the pre-push hook (`trailer_findings`) alike
    (instruction #239 item 2)."""
    return [Finding(where, "bad_party", f"{p!r} is not `guy`, `<kind> <model> <session>` or "
                                        f"`mechanism <tool> <run id>`")
            for p in ps if not (PARTY.match(p) or merge and p in MERGE_AUTHORS.values())]


# A commit whose `Proposer:` line git does not parse as a trailer, read from its message body instead. Keyed by full
# sha, so the exemption covers that commit only; it names the one party the body must carry, so it cannot supply a
# party the commit does not state. Each entry cites the review that found it.
PROPOSER_EXEMPTIONS: Mapping[str, str] = {
    # Instruction #54 item 5: an entry reachable from master is inert (P0m reads base..HEAD only) and was removed:
    # bb7b387 (review aa993f4 F1), b7eafee and 0a4f2b8 (make pins at 0a4f2b8).
    # Instruction #110 Part C item 4: 29dabe2 (PR #114 round 2) was inert once #114 merged and is removed. No entry is
    # added: a pushed commit must parse (`python -m harness.claims trailers`, the pre-push hook in harness/hooks/).
    # L2a obligation 32: e37357e (review commit of PR #48) lies on no branch this table is read against, so it is
    # removed; P0m now fails an entry outside base..HEAD, and the table is empty.
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
    body: str = ""


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
    malformed = malformed_parties(where, c.parties, c.merge)
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


def stale_exemptions(repo: Path, base: str, exemptions: Mapping[str, str] = PROPOSER_EXEMPTIONS) -> list[Finding]:
    """An exemption whose commit is not in `base..HEAD` is dead config: P0m reads only that range, so the entry can
    never apply to the branch being checked (L2a obligation 32; review 576fe9632eab F2). A sha this clone does not
    hold is not in the range."""
    in_range = set(_git(repo, "rev-list", f"{base}..HEAD").split())
    return [Finding(f"exemption {sha[:12]}", "stale_exemption", f"not in {base[:12]}..HEAD; P0m never applies it")
            for sha in exemptions if sha not in in_range]


# Instruction #110 Part C: sessions cannot push what the court cannot read. A non-merge commit must carry a `Proposer:`
# trailer as git parses it, and no `Proposer:` or `Instruction:` line outside its trailer block (a blank line before
# `Co-Authored-By:` splits the block, and git then parses neither). `harness/hooks/pre-push` runs this on every push.
TRAILER_KEYS = ("Proposer", "Instruction")


def trailer_findings(repo: Path, revisions: str) -> list[Finding]:
    """Findings on every non-merge commit in `revisions` (e.g. `<base>..HEAD`) whose trailers git does not parse."""
    fmt = ("%H%x1f%P%x1f%(trailers:key=Proposer,valueonly,separator=%x1e)%x1f"
           "%(trailers:key=Instruction,valueonly,separator=%x1e)%x1f%B%x1d")
    records = [r.strip("\n") for r in _git(repo, "log", "--reverse", f"--format={fmt}", revisions).split("\x1d")
               if r.strip()]

    def findings(record: str) -> list[Finding]:
        sha, parents, proposers, cited, message = record.split("\x1f", 4)
        if len(parents.split()) > 1:
            return []
        where = f"commit {sha[:12]}"
        parsed = {"Proposer": parties(proposers), "Instruction": parties(cited)}
        written = {k: [line for line in message.splitlines() if line.startswith(f"{k}:")] for k in TRAILER_KEYS}
        unparsed = [Finding(where, "no_proposer", "git parses no `Proposer:` trailer")] if not parsed["Proposer"] else []
        outside = [Finding(where, "outside_trailer_block", f"{len(written[k])} `{k}:` lines, {len(parsed[k])} parsed "
                                                           f"by git as trailers")
                   for k in TRAILER_KEYS if len(written[k]) > len(parsed[k])]
        return unparsed + outside + malformed_parties(where, parsed["Proposer"])

    return [f for r in records for f in findings(r)]


# Instruction #110 Part A item 2: on master, an item an open pull request already holds is not a candidate. A pull
# request holds the instructions its commits cite by `Instruction: #<n>` trailers, and any brief item its own STATUS
# header names; the Builder takes the next candidate and names the skipped item and its pull request in STATUS `did:`.
@dataclass(frozen=True)
class OpenPR:
    number: int
    instructions: tuple[int, ...]
    headers: tuple[str, ...]  # the `# STATUS` header lines of the STATUS files the pull request itself changes


def holder(item: str, prs: Sequence[OpenPR]) -> int | None:
    """The open pull request holding `item` (`#<n>` for an instruction, else a brief item's name), or None."""
    m = INSTRUCTION.match(item)
    return next((p.number for p in prs if (int(m.group(1)) in p.instructions if m else
                                           any(item in h for h in p.headers))), None)


def next_item(candidates: Sequence[str], prs: Sequence[OpenPR]) -> tuple[str | None, tuple[tuple[str, int], ...]]:
    """The first of `candidates`, in order, that no open pull request holds, and the held ones skipped before it."""
    held = [(c, holder(c, prs)) for c in candidates]
    skipped = tuple((c, n) for c, n in itertools.takewhile(lambda x: x[1] is not None, held))
    return (held[len(skipped)][0] if len(skipped) < len(held) else None), skipped


def open_pr(repo: Path, n: int, ref: str) -> OpenPR:
    """Pull request `n` as its branch `origin/<ref>` shows it against `origin/master`: the instructions its commits
    cite, and the STATUS headers of the STATUS files it changes."""
    cited = _git(repo, "log", "--format=%(trailers:key=Instruction,valueonly,separator=%x1e)%x1d",
                 f"origin/master..origin/{ref}")
    statuses = _git(repo, "diff", "--name-only", f"origin/master...origin/{ref}", "--",
                    *(f":(glob){g}" for g in STATUS_GLOBS)).split()
    headers = tuple(line for p in statuses for line in _git(repo, "show", f"origin/{ref}:{p}").splitlines()
                    if STATUS_HEADER.match(line))
    return OpenPR(n, tuple(i for r in cited.split("\x1d") for i in instructions(r.strip())), headers)


def load_open_prs(repo: Path) -> list[OpenPR]:
    """Every open pull request, listed through `gh`, its branch read from `repo`'s `origin` (fetched first). Raises if
    any cannot be read: an unread pull request could hold the item."""
    # The fetch keeps the user's configuration, which holds the credential helper (`gh auth setup-git`).
    subprocess.run(["git", "-C", str(repo), "fetch", "-q", "origin"], check=True, capture_output=True, timeout=120)
    listed = json.loads(subprocess.run(["gh", "pr", "list", "--state", "open", "--json", "number,headRefName"],
                                       cwd=repo, check=True, capture_output=True, text=True, timeout=60).stdout)
    return [open_pr(repo, int(p["number"]), str(p["headRefName"])) for p in listed]


# ------------------------------------------------------ the ground, rules 1 and 2 (instruction #54 items 1 and 2)

APPEND_ONLY = (*LEDGER_GLOBS, "reports/L*/review-*.md", "reports/L*/audit-*.md", "REPORT.md",
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
                *(f":(glob){g}" for g in LEDGER_GLOBS))

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
                     "{author: .user.login, labels: [.labels[].name], state: .state, body: (.body // \"\")}")
            timeline = gh(f"repos/{{owner}}/{{repo}}/issues/{n}/timeline?per_page=100", "--paginate", "--jq", ".[]")
        except (OSError, subprocess.SubprocessError) as e:
            print(f"    issue #{n}: not read ({e})")
            return None
        row = json.loads(out)
        events = [json.loads(line) for line in timeline.splitlines() if line.strip()]
        return Issue(str(row["author"]), tuple(row["labels"]), str(row["state"]), instruction_labeler(events),
                     instruction_labeled_at(events), edits(n), str(row["body"]))

    read_ = {n: read(n) for n in sorted(set(numbers))}
    return {n: i for n, i in read_.items() if i is not None}


# Instruction #70: a change to how work is done names the quantity of `python -m harness.ledger price` it moves, in what
# direction and by what bound, before the run; one that cannot says `Price: none (recording-only)` and changes no
# workflow. Every `instruction` issue signed after the rule merged carries exactly one such line, or one per `## Part`
# of a batch. "After" is the committer time of the first commit on master's first-parent line whose tree has the rule
# (`price_from`), read from git: never an issue number, an enumerated set or a committed time. Before that merge exists
# it is None and the check covers no issue.
PRICE_MARK = "def price_findings("
PRICE_PATH = "harness/claims.py"
PRICE_QUANTITIES = ("guy-items", "guy-latency", "sessions", "runner-min", "wish-latency")
PRICE_NONE = "none (recording-only)"
PRICE_LINE = re.compile(r"^Price: (.*?)\s*$", re.M)
PRICE_PART = re.compile(r"^## Part\b", re.M)
PRICE_DECLARED = re.compile(r"(\S+); (down|up); -?\d+(?:\.\d+)?")
WORKFLOWS = ".github/workflows/"


def price_from(repo: Path, base: str, mark: str = PRICE_MARK, path: str = PRICE_PATH) -> str | None:
    """The committer time of the first commit on `base`'s first-parent line that adds `mark` to `path` (a merge is read
    against its first parent), or None if there is none: the merge of instruction #70's rule (by default), or of any
    rule that dates itself the same way, read from git."""
    out = _git(repo, "log", "--first-parent", "--diff-merges=first-parent", "--reverse", "--format=%cI",
               f"-S{mark}", base, "--", path).split()
    return out[0] if out else None


def price_findings(n: int, body: str, labeled_at: str | None, since: str | None,
                   commits: Sequence[Commit] = ()) -> list[Finding]:
    """Findings on instruction issue `n` (body `body`, signed at `labeled_at`), if the rule merged at `since` and the
    issue was signed after it: exactly one `Price:` line, or in a batch exactly one in each `## Part` and none before
    the first, of the form `<quantity>; down|up; <bound>` or `none (recording-only)`; and, if every line is the second
    form, no commit citing the issue touches a workflow."""
    where = f"issue #{n}"
    if since is None or labeled_at is None or not _after(labeled_at, since):
        return []
    starts = [m.start() for m in PRICE_PART.finditer(body)]
    sections = ([("before the first `## Part`", body[:starts[0]], 0)]
                + [(f"`## Part` {i + 1}", body[a:b], 1) for i, (a, b) in enumerate(zip(starts, starts[1:] + [len(body)]))]
                if starts else [("the instruction", body, 1)])
    counted = [(name, PRICE_LINE.findall(text), want) for name, text, want in sections]
    wrong = [f"{name}: {len(lines)}, want {want}" for name, lines, want in counted if len(lines) != want]
    if wrong:
        return [Finding(where, "price_line", f"`Price:` lines {'; '.join(wrong)}")]
    lines = [line for _, found, _ in counted for line in found]
    bad = [line for line in lines if line != PRICE_NONE and not (
        (declared := PRICE_DECLARED.fullmatch(line)) and declared.group(1) in PRICE_QUANTITIES)]
    if bad:
        return [Finding(where, "price_form", f"`Price: {bad[0]}` is neither `<quantity>; down|up; <bound>` with a "
                                             f"quantity of {PRICE_QUANTITIES} nor `{PRICE_NONE}`")]
    touching = [c.sha[:12] for c in commits if n in c.instructions and any(p.startswith(WORKFLOWS) for p in c.paths)]
    return ([Finding(where, "price_none_on_workflow", f"`Price: {PRICE_NONE}` but commits {touching} touch {WORKFLOWS}")]
            if all(line == PRICE_NONE for line in lines) and touching else [])


def load_priced(repo: Path, since: str) -> dict[int, tuple[str, str | None]]:
    """Every `instruction` issue, open or closed, updated since `since` (signing updates it): number -> (body, when
    gfrmin's standing label was applied). Raises if the issues or a timeline cannot be read: unread authorises nothing."""
    def gh(path: str, *args: str) -> str:
        return subprocess.run(["gh", "api", path, *args], cwd=repo, check=True, capture_output=True, text=True,
                              timeout=120).stdout

    listed = [json.loads(line) for line in gh(
        "repos/{owner}/{repo}/issues?state=all&labels=instruction&per_page=100", "--paginate", "--jq",
        ".[] | {n: .number, body, updated: .updated_at}").splitlines() if line.strip()]
    return {e["n"]: (e["body"] or "", instruction_labeled_at(
        [json.loads(line) for line in gh(f"repos/{{owner}}/{{repo}}/issues/{e['n']}/timeline?per_page=100",
                                         "--paginate", "--jq", ".[]").splitlines() if line.strip()]))
            for e in listed if _after(e["updated"], since)}


# Instruction #111 Part A: a wish becomes a brief amendment unless the draft says, in one `Instruction because:` line, why
# the wish cannot wait its turn in the brief. A `draft` issue opened after the rule merged (dated as `price_from` dates
# the price rule: `draft_from`) opens `Wish: #<n>` and carries exactly one of the two forms.
DRAFT_MARK = "def draft_findings("
DRAFT_WISH = re.compile(r"Wish: #(\d+)")
DRAFT_BECAUSE = re.compile(r"^Instruction because: \S.*$", re.M)
DRAFT_AMENDMENT = re.compile(r"^Brief amendment to `docs/briefs/brief-\d+-[\w-]+\.md`, titled `Wish #(\d+)`:\s*$", re.M)


def draft_from(repo: Path, base: str) -> str | None:
    """When the draft rule merged onto `base`'s first-parent line, read from git; None before it has."""
    return price_from(repo, base, DRAFT_MARK, PRICE_PATH)


def draft_findings(n: int, body: str, opened_at: str | None, since: str | None) -> list[Finding]:
    """Findings on `draft` issue `n` if the rule merged at `since` and the draft was opened after it: the first line is
    `Wish: #<n>`, and exactly one of an `Instruction because: <sentence>` line and a `Brief amendment to
    docs/briefs/brief-<l>-<name>.md, titled Wish #<n>:` line that names the same wish."""
    where = f"draft #{n}"
    if since is None or opened_at is None or not _after(opened_at, since):
        return []
    lines = body.splitlines()
    wish = DRAFT_WISH.fullmatch(lines[0].strip()) if lines else None
    because, amendments = DRAFT_BECAUSE.findall(body), DRAFT_AMENDMENT.findall(body)
    rules = (
        (wish is None, "no_wish", "the first line is not `Wish: #<n>`"),
        (not because and not amendments, "no_form",
         "neither an `Instruction because:` line nor a brief amendment titled `Wish #<n>`"),
        (bool(because) and bool(amendments), "both_forms", "carries an `Instruction because:` line and a brief amendment"),
        (len(because) > 1 or len(amendments) > 1, "repeated_form", "carries a form more than once"),
        (wish is not None and any(a != wish.group(1) for a in amendments), "wrong_wish",
         "the amendment is titled for another wish than the first line names"),
    )
    return [Finding(where, code, detail) for broken, code, detail in rules if broken]


def load_drafts(repo: Path, since: str) -> dict[int, tuple[str, str]]:
    """Every `draft` issue, open or closed, opened since `since`: number -> (body, opened). Raises if they cannot be
    read: an unread draft authorises nothing."""
    out = subprocess.run(["gh", "api", "repos/{owner}/{repo}/issues?state=all&labels=draft&per_page=100", "--paginate",
                          "--jq", ".[] | {n: .number, body, opened: .created_at}"], cwd=repo, check=True,
                         capture_output=True, text=True, timeout=120).stdout
    return {e["n"]: (e["body"] or "", e["opened"]) for e in map(json.loads, filter(str.strip, out.splitlines()))
            if _after(e["opened"], since)}


def _edits_said(i: Issue) -> str:
    if i.edits is None:
        return "body edits not read"
    e = refusing_edit(i)
    return (f"body edited by {e.editor} at {e.at}, after the signature" if e is not None
            else f"{len(i.edits)} body edits, none by another account after the signature")


# Instruction #176 item 2: pins are monotone. Every pin and mutant of the registry at the base is in the registry at the
# head, unless a head commit cites `Instruction: #<n>` and issue <n>, which carries Guy's authority, has a line
# `Removes: <name>, ...` naming it. A mutant's name is `<pin>/<mutant>`; naming a pin removes its mutants with it.
REGISTRY_PATH = "harness/pins.py"
REMOVES_LINE = re.compile(r"^Removes: (.*?)\s*$", re.M)


REGISTRY_LOADER = (
    "import json, sys\n"
    "sys.path.insert(0, sys.argv[1])\n"
    "from harness import pins\n"
    "print(json.dumps([p.name for p in pins.PINS] + [f'{p.name}/{m.name}' for p in pins.PINS for m in p.mutants]))\n"
)


def registry_names_at(root: Path) -> frozenset[str]:
    """The pins and mutants the registry of the tree at `root` holds once loaded: `<pin>` and `<pin>/<mutant>`, as
    `harness.pins.PINS` evaluates in an isolated interpreter (`python -I`), so no expression that drops a call from the
    value while keeping it in the text registers anything. A tree that does not load registers nothing."""
    done = subprocess.run([sys.executable, "-I", "-c", REGISTRY_LOADER, str(root)], capture_output=True, text=True,
                          timeout=120, check=False)
    try:
        return frozenset(json.loads(done.stdout)) if done.returncode == 0 else frozenset()
    except ValueError:
        return frozenset()


def registry_names(text: str) -> frozenset[str]:
    """`registry_names_at` for a `harness/pins.py` given as text: written to a scratch tree and loaded there."""
    with tempfile.TemporaryDirectory(prefix="assize-registry-") as tmp:
        (Path(tmp) / "harness").mkdir()
        (Path(tmp) / "harness/__init__.py").write_text("")
        (Path(tmp) / REGISTRY_PATH).write_text(text)
        return registry_names_at(Path(tmp))


def registry_names_of(repo: Path, rev: str) -> frozenset[str]:
    """The registry of revision `rev`, loaded from a `git archive` of it."""
    with tempfile.TemporaryDirectory(prefix="assize-registry-") as tmp:
        archive = subprocess.run(["git", "-C", str(repo), "archive", rev], capture_output=True, check=True,
                                 env=os.environ | GIT_ENV).stdout
        subprocess.run(["tar", "-x", "-C", tmp], input=archive, check=True, capture_output=True)
        return registry_names_at(Path(tmp))


def declared_removals(commits: Sequence[Commit], issues: Mapping[int, Issue]) -> frozenset[str]:
    """The names removed by `Removes:` lines of the signed instruction issues the commits cite."""
    cited = {n for c in commits for n in c.instructions}
    return frozenset(name for n in cited if authorises(issues.get(n))
                     for line in REMOVES_LINE.findall(issues[n].body) for name in re.split(r"[,\s]+", line) if name)


def monotone_findings(base: frozenset[str], head: frozenset[str], removed: frozenset[str]) -> list[Finding]:
    """Findings for each name of the base registry absent from the head's and not declared removed; an empty head
    registry is one."""
    if not head:
        return [Finding(REGISTRY_PATH, "registry_unreadable", "no pin is registered at the head")]
    return [Finding(name, "pin_removed", "registered at the base, absent at the head, and no signed instruction names it")
            for name in sorted(base - head)
            if name not in removed and name.split("/")[0] not in removed]


def pins_monotone(repo: Path, base: str, head: str = "HEAD") -> list[Finding]:
    """The monotone check between two revisions, on the registries as each loads. Issues are read only when something
    is missing and a head commit cites an instruction."""
    base_names, head_names = registry_names_of(repo, base), registry_names_of(repo, head)
    found = monotone_findings(base_names, head_names, frozenset())
    commits = branch_commits(repo, base, head) if found else []
    cited = sorted({n for c in commits for n in c.instructions})
    if not found or not cited:
        return found
    return monotone_findings(base_names, head_names, declared_removals(commits, load_issues(repo, cited)))


def main(argv: Sequence[str] | None = None) -> int:
    """`python -m harness.claims signed <n>...`: whether each issue carries Guy's authority (Amendment 3). The Builder
    acts only on an issue printed `signed`. `trailers <revisions>`: exits non-zero if a commit's trailers do not parse
    (instruction #110 Part C). `next <item>...`: the first item no open pull request holds (Part A item 2).
    `status-check <path>...`: exits non-zero if P0l would reject a STATUS file (instruction #211 item 2)."""
    ap = argparse.ArgumentParser(prog="python -m harness.claims")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("signed", help="whether each issue is an instruction Guy signed")
    s.add_argument("numbers", type=int, nargs="*")
    s.add_argument("--repo", type=Path, default=Path("."))
    t = sub.add_parser("trailers", help="refuse commits whose Proposer or Instruction trailers git does not parse")
    t.add_argument("revisions")
    t.add_argument("--repo", type=Path, default=Path("."))
    x = sub.add_parser("next", help="the first candidate item, in order, that no open pull request holds")
    x.add_argument("items", nargs="+", help="`#<n>` for an instruction, else a brief item's name")
    x.add_argument("--repo", type=Path, default=Path("."))
    m = sub.add_parser("pins-monotone", help="refuse a head whose registry lacks a pin or mutant of the base's")
    m.add_argument("base")
    m.add_argument("head")
    m.add_argument("--repo", type=Path, default=Path("."))
    c = sub.add_parser("status-check", help="refuse a STATUS whose header or citation P0l would reject")
    c.add_argument("paths", type=Path, nargs="+")
    c.add_argument("--repo", type=Path, default=Path("."), help="the tree whose reports/L*/ci/*.json records are read")
    a = ap.parse_args(argv)
    if a.cmd == "status-check":
        found = status_check(a.repo, a.paths)
        for f in found:
            print(f, file=sys.stderr)
        print(f"status-check {len(a.paths)} files: {len(found)} findings", file=sys.stderr)
        return 1 if found else 0
    if a.cmd == "pins-monotone":
        found = pins_monotone(a.repo, a.base, a.head)
        for f in found:
            print(f, file=sys.stderr)
        print(f"pins-monotone {a.base}..{a.head}: {len(found)} findings", file=sys.stderr)
        return 1 if found else 0
    if a.cmd == "trailers":
        found = trailer_findings(a.repo, a.revisions)
        for f in found:
            print(f, file=sys.stderr)
        print(f"trailers {a.revisions}: {len(found)} findings", file=sys.stderr)
        return 1 if found else 0
    if a.cmd == "next":
        chosen, skipped = next_item(a.items, load_open_prs(a.repo))
        for item, n in skipped:
            print(f"skipped: {item} held by PR #{n}")
        print(f"next: {chosen or 'none'}")
        return 0
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
