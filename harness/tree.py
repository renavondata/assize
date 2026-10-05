"""Disposable copies of the repository tree (brief 0 A2, trusted base)."""

from __future__ import annotations

import hashlib
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from harness.pin import ROOT

# Excluded from copies, at the top level only.
TOP_LEVEL_EXCLUDE = frozenset({".git", ".venv", "out", "reports",
                               "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache"})


@contextmanager
def disposable_copy(root: Path = ROOT) -> Iterator[Path]:
    """Copy `root` (the tree of the running code, so edits compose) into a temporary directory; delete it on exit."""
    tmp = Path(tempfile.mkdtemp(prefix="assize-copy-"))
    copy = tmp / "repo"
    shutil.copytree(root, copy, symlinks=True,
                    ignore=lambda d, names: set(names) & TOP_LEVEL_EXCLUDE if Path(d) == root else set())
    try:
        yield copy
    finally:
        shutil.rmtree(tmp)


def digest(root: Path, sub: str = "harness") -> str:
    """SHA-256 over relative paths and contents of `root/sub`, ignoring bytecode caches."""
    h = hashlib.sha256()
    for f in sorted(p for p in (root / sub).rglob("*") if p.is_file() and "__pycache__" not in p.parts):
        h.update(str(f.relative_to(root)).encode() + b"\0" + f.read_bytes() + b"\0")
    return h.hexdigest()
