"""The trusted base (CLAUDE.md Amendment 2, audit criterion 7; audit 8aae43c8c792 finding 4): the set of things outside
every loop, listed in `harness/trusted_base.toml` and compared with the set the tree declares.

The declared set is read from the tree alone: the workflow files under `.github/workflows/`, the runner labels their
`runs-on` names, the repository secrets their expressions read (`secrets.<NAME>`; a bare `secrets`, `secrets[...]` or
`secrets: inherit` reaches every secret and is declared as `*`), the tokens each workflow binds (`<workflow>
github.token` and `<workflow> secrets.<NAME>`), and the CODEOWNERS lines. The list must equal it, kind by kind, and every
entry names the audit-dated amendment that admitted it: a heading `Audit findings at <sha>` present in a brief under
`docs/briefs/`. Growth without such an amendment fails.

`python -m harness.trusted check`: the findings at the tree, one per line; exit 1 if any.
`python -m harness.trusted grown <sha>`: the entries listed now and absent from the list at <sha> (every entry, if the
list did not exist there), for the Auditor to compare with the last audit's sha."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tomllib
from pathlib import Path

from harness.pin import ROOT

LIST_PATH = "harness/trusted_base.toml"
WORKFLOWS = ".github/workflows"
KINDS = ("workflow", "runner_label", "secret", "token", "codeowners")
ADMISSION = re.compile(r"^#+ +(Audit findings at [0-9a-f]{12,40})[ \t]*$", re.M)
EXPRESSION = re.compile(r"\$\{\{(.*?)\}\}", re.S)
SECRET = re.compile(r"\bsecrets\b(?:\.([A-Za-z_]\w*))?")
INHERIT = re.compile(r"^\s*secrets:\s*inherit\b", re.M)
RUNS_ON = re.compile(r"^\s*runs-on:[ \t]*(.+?)[ \t]*$", re.M)


def _secret_refs(text: str) -> frozenset[str]:
    """Every secret a workflow's expressions read; `*` for one reaching them all."""
    inside = [m.group(1) or "*" for e in EXPRESSION.findall(text) for m in SECRET.finditer(e)]
    return frozenset(inside + (["*"] if INHERIT.search(text) else []))


def _runner_labels(text: str) -> frozenset[str]:
    return frozenset(label.strip().strip("'\"") for value in RUNS_ON.findall(text)
                     for label in value.strip("[]").split(",") if label.strip())


def _tokens(name: str, text: str) -> frozenset[str]:
    github = ["github.token"] if any(re.search(r"\bgithub\.token\b", e) for e in EXPRESSION.findall(text)) else []
    return frozenset(f"{name} {t}" for t in github + [f"secrets.{s}" for s in _secret_refs(text)])


def declared_from(workflows: dict[str, str], codeowners: str) -> dict[str, frozenset[str]]:
    """The declared trusted base of a tree whose workflow files (name to text) and CODEOWNERS text are given."""
    return {
        "workflow": frozenset(workflows),
        "runner_label": frozenset().union(*map(_runner_labels, workflows.values())),
        "secret": frozenset().union(*map(_secret_refs, workflows.values())),
        "token": frozenset().union(*(_tokens(n, t) for n, t in workflows.items())),
        "codeowners": frozenset(" ".join(line.split()) for line in codeowners.splitlines()
                                if line.strip() and not line.lstrip().startswith("#")),
    }


def declared(root: Path = ROOT) -> dict[str, frozenset[str]]:
    flows = sorted(p for p in (root / WORKFLOWS).glob("*") if p.suffix in (".yml", ".yaml"))
    owners = root / "CODEOWNERS"
    return declared_from({p.name: p.read_text() for p in flows}, owners.read_text() if owners.exists() else "")


def parse(text: str) -> dict[str, dict[str, str]]:
    """The list: one table per kind, each entry's name mapped to the amendment that admitted it."""
    return {kind: dict(entries) for kind, entries in tomllib.loads(text).items()}


def admissions(root: Path = ROOT) -> frozenset[str]:
    """The audit-dated amendments present in the briefs: each `Audit findings at <sha>` heading."""
    return frozenset(h for p in sorted((root / "docs" / "briefs").glob("*.md")) for h in ADMISSION.findall(p.read_text()))


def findings(listed: dict[str, dict[str, str]], decl: dict[str, frozenset[str]], admitted: frozenset[str]) -> list[str]:
    """Every way the list fails: a kind it does not know, a declared entry it omits, an entry the tree no longer
    declares, and an entry no audit-dated amendment present in the briefs admits."""
    return ([f"unknown kind {k}" for k in sorted(set(listed) - set(KINDS))]
            + [f"unlisted {k} {n}" for k in KINDS for n in sorted(decl.get(k, frozenset()) - set(listed.get(k, {})))]
            + [f"stale {k} {n}" for k in KINDS for n in sorted(set(listed.get(k, {})) - decl.get(k, frozenset()))]
            + [f"unadmitted {k} {n}: {a!r}" for k in KINDS for n, a in sorted(listed.get(k, {}).items())
               if a not in admitted])


def grown(old: dict[str, dict[str, str]], new: dict[str, dict[str, str]]) -> list[str]:
    """The entries of `new` absent from `old`, each with the amendment it cites."""
    return [f"{k} {n}: {a}" for k in sorted(new) for n, a in sorted(new[k].items()) if n not in old.get(k, {})]


def check(root: Path = ROOT) -> list[str]:
    path = root / LIST_PATH
    if not path.exists():
        return [f"no list at {LIST_PATH}"]
    return findings(parse(path.read_text()), declared(root), admissions(root))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m harness.trusted")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    g = sub.add_parser("grown")
    g.add_argument("sha")
    a = ap.parse_args(argv)
    if a.cmd == "check":
        found = check()
        print("\n".join(found) if found else f"{LIST_PATH}: equals the declared trusted base; every entry admitted")
        return 1 if found else 0
    git = lambda *args: subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)  # noqa: E731
    if git("cat-file", "-e", f"{a.sha}^{{commit}}").returncode != 0:
        print(f"{a.sha}: no such commit", file=sys.stderr)
        return 2
    listed_then = git("cat-file", "-e", f"{a.sha}:{LIST_PATH}").returncode == 0
    old = parse(git("show", f"{a.sha}:{LIST_PATH}").stdout) if listed_then else {}
    print("\n".join(grown(old, parse((ROOT / LIST_PATH).read_text()))) or f"no growth since {a.sha}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
