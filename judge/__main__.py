"""Judge subcommands. `verify LEDGER PRIVATE`: recompute every chain of the ledger and check every signed head
against the judge's private storage (brief 1 A4 item 1); exit 0 if and only if nothing is found."""

from __future__ import annotations

import sys
from pathlib import Path

from judge import ledger


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[0] != "verify":
        print("usage: python -m judge verify LEDGER PRIVATE", file=sys.stderr)
        return 2
    found = ledger.verify(Path(argv[1]), Path(argv[2]))
    for f in found:
        print(f"verify: {f}")
    print(f"verify: {Path(argv[1]).name}: {'FAILED' if found else 'ok'} ({len(found)} findings)")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
