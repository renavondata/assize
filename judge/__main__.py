"""Judge subcommands.
`verify LEDGER PRIVATE`: recompute every chain of the ledger and check every signed head against the judge's private
storage (brief 1 A4 item 1); exit 0 if and only if nothing is found.
`credential PRIVATE KIND MODEL SESSION`: issue a credential to that proposer and print its token once (A4 item 2).
`register PRIVATE IMAGE`: register the image digest under the credential whose token is read from stdin, never from
the command line; print the registration, or exit 1 with the refusal's code."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from judge import ledger, registry

USAGE = ("usage: python -m judge verify LEDGER PRIVATE | credential PRIVATE KIND MODEL SESSION | "
         "register PRIVATE IMAGE (token on stdin)")


def _verify(led: str, private: str) -> int:
    found = ledger.verify(Path(led), Path(private))
    for f in found:
        print(f"verify: {f}")
    print(f"verify: {Path(led).name}: {'FAILED' if found else 'ok'} ({len(found)} findings)")
    return 1 if found else 0


def _credential(private: str, kind: str, model: str, session: str) -> int:
    print(registry.credential(Path(private), {"kind": kind, "model": model, "session": session}))
    return 0


def _register(private: str, image: str) -> int:
    print(json.dumps(registry.register(Path(private), image, sys.stdin.read().strip()), sort_keys=True))
    return 0


COMMANDS = {"verify": (_verify, 2), "credential": (_credential, 4), "register": (_register, 2)}


def main(argv: list[str]) -> int:
    command, arity = COMMANDS.get(argv[0] if argv else "", (None, -1))
    if command is None or len(argv) - 1 != arity:
        print(USAGE, file=sys.stderr)
        return 2
    try:
        return command(*argv[1:])
    except registry.Refused as e:
        print(f"refused: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
