"""Judge subcommands.
`verify LEDGER PRIVATE ANCHOR`: recompute every chain of the ledger and check every signed head against the judge's
private storage (brief 1 A4 item 1), and require ANCHOR, the last `sha256` of a request the caller holds, to be a signed
head (review 2817eb7 F2); exit 0 if and only if nothing is found.
`credential PRIVATE KIND MODEL SESSION`: issue a credential to that proposer and print its token once (A4 item 2).
`register PRIVATE IMAGE`: register the image digest under the credential whose token is read from stdin, never from
the command line; print the registration, or exit 1 with the refusal's code.
`evaluate PRIVATE LEDGERS RUNTIME IMAGE WORLD N REQUEST_ID`: evaluate the registered image on N fresh seeds of WORLD
under RUNTIME (`judge/evaluate.py`), the ledger in LEDGERS; print the request's records, one JSON line each, or exit 1
with the refusal's code. Asked again with the same REQUEST_ID, it prints the same records and runs nothing."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from judge import evaluate, ledger, registry, seeds

USAGE = ("usage: python -m judge verify LEDGER PRIVATE ANCHOR | credential PRIVATE KIND MODEL SESSION | "
         "register PRIVATE IMAGE (token on stdin) | evaluate PRIVATE LEDGERS RUNTIME IMAGE WORLD N REQUEST_ID")


def _verify(led: str, private: str, anchor: str) -> int:
    found = ledger.verify(Path(led), Path(private), anchor)
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


def _episodes(n: str) -> int:
    """N as a positive count written in ASCII digits; `str.isdigit` also admits `²` and Arabic-Indic digits, which
    `int` rejects with a traceback (L2a obligation 5, review 6debf231b630 F4)."""
    if not (n.isascii() and n.isdigit() and int(n) > 0):
        raise registry.Refused("bad_episodes", f"{n!r} is not a positive episode count")
    return int(n)


def _evaluate(private: str, ledgers: str, rt: str, image: str, world: str, n: str, request_id: str) -> int:
    for r in evaluate.evaluate(image, world, _episodes(n), request_id, private=Path(private), ledgers=Path(ledgers),
                               runtime_name=rt):
        print(json.dumps(r, sort_keys=True))
    return 0


COMMANDS = {"verify": (_verify, 3), "credential": (_credential, 4), "register": (_register, 2),
            "evaluate": (_evaluate, 7)}


def main(argv: list[str]) -> int:
    command, arity = COMMANDS.get(argv[0] if argv else "", (None, -1))
    if command is None or len(argv) - 1 != arity:
        print(USAGE, file=sys.stderr)
        return 2
    try:
        return command(*argv[1:])
    except (registry.Refused, seeds.SeedError) as e:
        print(f"refused: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
