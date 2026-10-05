"""Static scan for mutant switches (P0b, brief 0 A2 item 3).

Patterns are assembled from fragments so this file does not match itself.
"""

from __future__ import annotations

import re
from pathlib import Path

from harness.tree import TOP_LEVEL_EXCLUDE

_PREFIX = "ASSIZE" + "_"
TOKEN = re.compile(re.escape(_PREFIX) + r"(?:MUTANT|TEST\w*)")
SWITCH_IMPORT = re.compile(r"^\s*(?:from\s+harness\s+import\s+.*\b" + "mutants" + r"\b"
                           r"|from\s+harness\." + "mutants" + r"\b"
                           r"|import\s+harness\." + "mutants" + r"\b)")
CODE_SUFFIXES = frozenset({".py", ".sh", ".yml", ".yaml"})
CODE_NAMES = frozenset({"Makefile", "Dockerfile", "Containerfile"})


def code_files(root: Path) -> list[Path]:
    return sorted(
        p for p in root.rglob("*")
        if p.is_file()
        and p.relative_to(root).parts[0] not in TOP_LEVEL_EXCLUDE
        and "__pycache__" not in p.parts
        and (p.suffix in CODE_SUFFIXES or p.name in CODE_NAMES)
    )


def violations(root: Path) -> tuple[list[str], int]:
    files = code_files(root)
    found = [
        f"{f.relative_to(root)}:{n}: {line.strip()}"
        for f in files
        for n, line in enumerate(f.read_text(errors="replace").splitlines(), 1)
        if TOKEN.search(line) or SWITCH_IMPORT.search(line)
    ]
    found += [f"{p.relative_to(root)}: mutant-switch module exists"
              for p in (root / "harness" / ("mutants" + ".py"), root / "harness" / "mutants")
              if p.exists()]
    return found, len(files)
