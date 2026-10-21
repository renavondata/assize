"""Brief 2's zero-diff check (§1, §Pins "P1 Zero diff", A1 item 4 as A2 amends it): `judge/` and `worlds/spec/`
are those of the L2a baseline, recorded in `harness/baseline.toml`. Copies carry no `.git`, so a tree is hashed as
git hashes it, in Python; the recorded ids are bound to the baseline commit in the invocation tree's repository."""

from __future__ import annotations

import hashlib
import stat
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path

BASELINE = "harness/baseline.toml"
# Never tracked: a bytecode cache is not part of a tree (tree.EVERY_DEPTH_EXCLUDE).
UNTRACKED = frozenset({"__pycache__"})


@dataclass(frozen=True)
class Finding:
    where: str
    code: str
    detail: str

    def __str__(self) -> str:
        return f"{self.where}: {self.code}: {self.detail}"


def _object_id(kind: str, body: bytes) -> str:
    return hashlib.sha1(f"{kind} {len(body)}\0".encode() + body).hexdigest()


def _entry(path: Path) -> tuple[str, str] | None:
    """(git mode, object id) of `path`, or None for a directory holding no file (git records no empty tree)."""
    if path.is_symlink():
        return "120000", _object_id("blob", str(path.readlink()).encode())
    if path.is_dir():
        tid = tree_id(path)
        return None if tid is None else ("40000", tid)
    mode = "100755" if path.stat().st_mode & stat.S_IXUSR else "100644"
    return mode, _object_id("blob", path.read_bytes())


def tree_id(directory: Path) -> str | None:
    """The id git gives `directory` as a tree object, bytecode caches excluded; None if it holds no file."""
    entries = [(p.name, e) for p in directory.iterdir() if p.name not in UNTRACKED and (e := _entry(p)) is not None]
    # git orders a tree's entries by name, a subtree's name compared as if it ended in "/"
    ordered = sorted(entries, key=lambda ne: ne[0].encode() + (b"/" if ne[1][0] == "40000" else b""))
    body = b"".join(f"{mode} {name}\0".encode() + bytes.fromhex(oid) for name, (mode, oid) in ordered)
    return _object_id("tree", body) if ordered else None


def load(root: Path) -> dict:
    return tomllib.loads((root / BASELINE).read_text())


def tree_findings(root: Path, baseline: dict) -> list[Finding]:
    """Each recorded directory of `root` hashes to its recorded tree id."""
    return [Finding(d, "tree_changed", f"tree {got} differs from the baseline's {want}")
            for d, want in sorted(baseline["trees"].items())
            if (got := tree_id(root / d) if (root / d).is_dir() else None) != want]


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def binding_findings(repo: Path, baseline: dict, head: str = "HEAD", base: str | None = None) -> list[Finding]:
    """The baseline commit is in `head`'s history, is in the history of `base` (the merged branch, which a pull
    request cannot move: a baseline only a branch carries is a moved baseline), and carries every recorded tree id,
    read by git in `repo`; and `base` itself carries every recorded tree id, so an older commit of master's history,
    whose trees master has since left, is a rewound baseline. A `base` that is None or unreadable is named, never
    passed."""
    sha = baseline["sha"]
    reached = _git(repo, "merge-base", "--is-ancestor", sha, head).returncode == 0
    base_ok = base is not None and _git(repo, "rev-parse", "--verify", "-q", base).returncode == 0
    merged = base_ok and _git(repo, "merge-base", "--is-ancestor", sha, base).returncode == 0
    return ([] if reached else [Finding(sha[:12], "baseline_unreachable", f"not an ancestor of {head}")]) + (
        [] if merged else [Finding(sha[:12], "baseline_moved" if base_ok else "base_unreadable",
                                   f"not an ancestor of {base}" if base_ok else f"no ref {base} to read it against")]
    ) + [
        Finding(d, "tree_unbound", f"recorded {want}, the baseline commit has {got or 'no such tree'}")
        for d, want in sorted(baseline["trees"].items())
        if (got := _git(repo, "rev-parse", "--verify", "-q", f"{sha}:{d}").stdout.strip()) != want] + [
        Finding(d, "baseline_rewound", f"recorded {want}, {base} has {got or 'no such tree'}")
        for d, want in sorted(baseline["trees"].items())
        if base_ok and (got := _git(repo, "rev-parse", "--verify", "-q", f"{base}:{d}").stdout.strip()) != want]
