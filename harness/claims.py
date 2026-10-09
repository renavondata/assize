"""Checkers for the court's own claims (brief 1 A4 item 7): forecast ledgers (7a), CI claims bound to the head they
describe (7b), and commit proposers (7c, with A5 F2). Each checker is a pure function returning findings; an empty
list means accepted. Readers of git and of committed files are kept apart from the rules."""

from __future__ import annotations

import argparse
import functools
import hashlib
import json
import os
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
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
# auditor: CLAUDE.md Amendment 2; vizier: Amendment 3
PROPOSER_KINDS = frozenset({"builder", "reviewer", "guy", "counsel", "auditor", "vizier"})


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


def _resolution_findings(where: str, r: dict, earlier_ids: frozenset[str]) -> list[Finding]:
    missing = [Finding(where, "missing_key", f"resolution lacks {k}") for k in RESOLUTION_KEYS if k not in r]
    proposer = (_proposer_findings(where, r["proposer"])
                + ([Finding(where, "not_reviewer", "A1.6 assigns resolutions to the Reviewer")]
                   if isinstance(r["proposer"], dict) and r["proposer"].get("kind") != "reviewer" else [])
                if "proposer" in r else [])
    orphan = ([Finding(where, "orphan", f"id {r['id']!r} matches no earlier forecast")]
              if "id" in r and r["id"] not in earlier_ids else [])
    outcome = ([Finding(where, "bad_outcome", f"outcome {r['outcome']!r} is not a boolean")]
               if "outcome" in r and not isinstance(r["outcome"], bool) else [])
    return missing + proposer + orphan + outcome


def _parse(n: int, line: str) -> dict | Finding:
    try:
        row = json.loads(line)
    except json.JSONDecodeError as e:
        return Finding(f"row {n}", "bad_json", str(e))
    return row if isinstance(row, dict) else Finding(f"row {n}", "bad_json", "row is not an object")


def ledger_findings(lines: Sequence[str]) -> list[Finding]:
    """A row carrying `claim` is a forecast; every other row is a resolution. Rows are numbered from 1."""
    rows = [(n, _parse(n, line)) for n, line in enumerate(lines, 1) if line.strip()]
    forecast_rows = [(n, r["id"]) for n, r in rows if isinstance(r, dict) and "claim" in r and "id" in r]

    def findings(n: int, r: dict | Finding) -> list[Finding]:
        if isinstance(r, Finding):
            return [r]
        if "claim" in r:
            return _forecast_findings(f"row {n}", r)
        return _resolution_findings(f"row {n}", r, frozenset(i for m, i in forecast_rows if m < n))

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
    # review aa993f4 F1 (= bb7b387 F1): a blank line separates `Proposer:` from `Co-Authored-By:`, so git reads no
    # trailer. A reviewer commit on PR #19's branch, followed by 11 others; rewording it would rewrite all of them.
    "bb7b3875f8f6b91ee88f89ca964598f5e6c5385b": "reviewer claude-opus-5-5 fa0fb7b4-c85c-4c89-a70a-8f059dc787cc",
    # make pins at 0a4f2b8 (reports/L2/make-pins-0a4f2b8.txt), P0m clean: the same blank line, in the review commit of
    # PR #35 and the Builder's F1 fix after it; both pushed, so they are exempted rather than reworded.
    "b7eafee0ca572971b799cd6899e632fac7a6e30f": "reviewer claude-opus-5-5 cba02c1d-8bbd-4c1d-951f-804edc546db7",
    "0a4f2b8aa612d799b526a458c8f850669e122a98": "builder claude-opus-5-5 1137b45d-2b48-40ec-8896-f3e4cb2a707a",
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
INSTRUCTION_AUTHOR = "gfrmin"
INSTRUCTION_LABEL = "instruction"
DRAFT_LABEL = "draft"


@dataclass(frozen=True)
class Issue:
    author: str
    labels: tuple[str, ...]
    state: str = ""
    labeled_by: str | None = None  # the account that applied the standing `instruction` label, from the timeline


def instruction_labeler(events: Sequence[Mapping]) -> str | None:
    """The account whose `labeled instruction` event stands at the end of an issue timeline: the actor of the last
    such event with no `unlabeled instruction` after it, or None."""
    def step(by: str | None, e: Mapping) -> str | None:
        if (e.get("label") or {}).get("name") != INSTRUCTION_LABEL:
            return by
        return {"labeled": (e.get("actor") or {}).get("login"), "unlabeled": None}.get(e.get("event"), by)

    return functools.reduce(step, events, None)


def authorises(issue: Issue | None) -> bool:
    """An issue carries Guy's authority if it is labelled `instruction`, gfrmin applied that label, and gfrmin authored
    it or it is a `draft` (Amendment 3), open or closed."""
    return (issue is not None and INSTRUCTION_LABEL in issue.labels and issue.labeled_by == INSTRUCTION_AUTHOR
            and (issue.author == INSTRUCTION_AUTHOR or DRAFT_LABEL in issue.labels))


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


def load_issues(repo: Path, numbers: Sequence[int]) -> dict[int, Issue]:
    """The issues `numbers` name, with their timelines, read through the GitHub API (`gh api`, from `repo`'s remote).
    One that cannot be read is left out, so it authorises nothing."""
    def gh(path: str, *args: str) -> str:
        return subprocess.run(["gh", "api", path, *args], cwd=repo, check=True, capture_output=True, text=True,
                              timeout=60).stdout

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
        return Issue(str(row["author"]), tuple(row["labels"]), str(row["state"]), instruction_labeler(events))

    read_ = {n: read(n) for n in sorted(set(numbers))}
    return {n: i for n, i in read_.items() if i is not None}


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
        why = f"author {i.author}, labels {list(i.labels)}, instruction label applied by {i.labeled_by}" if i else ""
        print(f"#{n} {verdict}: {why or 'not read'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
