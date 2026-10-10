"""The judge's tamper-evident ledger (brief 1 A4 item 1; A5 F4).

The ledger is append-only JSONL, one judge record per line. Every record carries `request_id`, `prev_sha256` and
`sha256`: `sha256` is the SHA-256 of the record's canonical serialisation (sorted keys, no whitespace) without its own
`sha256`, and `prev_sha256` is the previous record's `sha256`, or, for a request's first record, the SHA-256 of the
request's `request_id` as UTF-8 bytes. The judge opens the ledger `O_APPEND` and never seeks.

After every request the judge appends to `heads.jsonl` in its private storage the request's chain head: the ledger's
file name, the `request_id`, its record count, its last `sha256` and the ledger's length in bytes after the request.
Each head is signed by an HMAC-SHA256 under a key the judge generates on first start, in the same private storage, and
never exports; only the judge, holding the key, verifies. `verify` recomputes every chain and checks every signature:
the ledger must be exactly the signed requests, in order, ending at the last head's length.

Each signed head stands alone, so the ledger and `heads.jsonl` cannot commit to how many requests there were: a party
who can write both could remove the last request and its head, or both files, and leave a ledger that is exactly what
remains signed (review 2817eb7 F2). The commitment lives with the caller instead. `append` returns a request's records
as written, so the caller holds its head, the last record's `sha256`; `verify` requires that anchor to be the head of a
signed request of the ledger. Every request up to the anchor is then committed; requests after it are admitted, and
only a later anchor commits to them."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

KEY = "key"
HEADS = "heads.jsonl"


def canonical(record: Mapping) -> bytes:
    return json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(record: Mapping) -> str:
    """The SHA-256 of `record`'s canonical serialisation without its own `sha256`."""
    return hashlib.sha256(canonical({k: v for k, v in record.items() if k != "sha256"})).hexdigest()


def genesis(request_id: str) -> str:
    return hashlib.sha256(request_id.encode()).hexdigest()


def _key(private: Path) -> bytes:
    """The judge's signing key, generated on first start; it never leaves `private`."""
    private.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = private / KEY
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return path.read_bytes()
    with os.fdopen(fd, "wb") as f:
        f.write(secrets.token_bytes(32))
    return path.read_bytes()


def _mac(key: bytes, head: Mapping) -> str:
    return hmac.new(key, canonical({k: v for k, v in head.items() if k != "mac"}), hashlib.sha256).hexdigest()


def _append(path: Path, data: bytes) -> int:
    """Append `data` with one descriptor opened O_APPEND, never seeking; return the file's length after it."""
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        view = memoryview(data)
        while view:
            view = view[os.write(fd, view):]
        return os.fstat(fd).st_size
    finally:
        os.close(fd)


def _lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_bytes().splitlines()] if path.exists() else []


def append(ledger: Path, private: Path, request_id: str, records: Sequence[Mapping]) -> list[dict]:
    """Chain `records` as request `request_id`, append them to `ledger` and sign the request's head; return them as
    written. A request_id already signed for this ledger is refused: a request is written once."""
    key = _key(private)
    if any(h["ledger"] == ledger.name and h["request_id"] == request_id for h in _lines(private / HEADS)):
        raise ValueError(f"request {request_id!r} is already in {ledger.name}")
    chained: list[dict] = []
    prev = genesis(request_id)
    for r in records:
        rec = dict(r) | {"request_id": request_id, "prev_sha256": prev}
        rec["sha256"] = digest(rec)
        prev = rec["sha256"]
        chained.append(rec)
    size = _append(ledger, b"".join(canonical(r) + b"\n" for r in chained))
    head = {"ledger": ledger.name, "request_id": request_id, "records": len(chained), "head": prev, "bytes": size}
    _append(private / HEADS, canonical(head | {"mac": _mac(key, head)}) + b"\n")
    return chained


class Unverified(ValueError):
    """The ledger's lines for a signed request are not what its signed head says."""

    def __init__(self, findings: Sequence[str]):
        super().__init__("; ".join(findings))
        self.findings = list(findings)


def recorded(ledger: Path, private: Path, request_id: str) -> list[dict] | None:
    """The records of `request_id` as written, if its head was signed and they are what it signed: the head's
    signature, record count, last `sha256` and every link of the chain (review 6debf23 F2). None if the ledger holds no
    signed request of that id; `Unverified` if they differ."""
    key_path = private / KEY
    heads = [h for h in _lines(private / HEADS) if h.get("ledger") == ledger.name and h.get("request_id") == request_id]
    if not heads:
        return None
    head = heads[-1]
    mine = [r for r in _lines(ledger) if r.get("request_id") == request_id]
    found = (([] if key_path.exists() and hmac.compare_digest(str(head.get("mac")), _mac(key_path.read_bytes(), head))
              else [f"head of {request_id!r}: signature invalid or no signing key"])
             + ([] if len(mine) == head.get("records") else
                [f"{request_id!r}: {len(mine)} records in {ledger.name}, the signed head says {head.get('records')}"])
             + ([] if mine and mine[-1].get("sha256") == head.get("head") else
                [f"{request_id!r}: last record's sha256 is not the signed head"])
             + _chain_findings(request_id, mine))
    if found:
        raise Unverified(found)
    return mine


def _requests(records: Iterable[dict]) -> list[tuple[str, list[dict]]]:
    """Consecutive records grouped by `request_id`, in ledger order."""
    groups: list[tuple[str, list[dict]]] = []
    for r in records:
        if groups and groups[-1][0] == r.get("request_id"):
            groups[-1][1].append(r)
        else:
            groups.append((r.get("request_id"), [r]))
    return groups


def _chain_findings(request_id: str, records: Sequence[dict]) -> list[str]:
    if not isinstance(request_id, str):
        return [f"records without a request_id: {len(records)}"]
    found: list[str] = []
    expected = genesis(request_id)
    for i, r in enumerate(records):
        if r.get("prev_sha256") != expected:
            found.append(f"{request_id}[{i}]: prev_sha256 does not link to the {'request_id' if i == 0 else 'previous record'}")
        if r.get("sha256") != digest(r):
            found.append(f"{request_id}[{i}]: sha256 is not the record's own digest")
        expected = r.get("sha256")
    return found


def verify(ledger: Path, private: Path, anchor: str) -> list[str]:
    """Every finding against `ledger`; empty if and only if it is exactly the requests the judge signed, in order,
    each chained from its request_id, and nothing else, and `anchor`, a head the caller retained, is one of them."""
    key_path = private / KEY
    if not key_path.exists():
        return [f"no signing key in {private}"]
    key = key_path.read_bytes()
    heads = [h for h in _lines(private / HEADS) if h.get("ledger") == ledger.name]
    found = [f"head of {h.get('request_id')!r}: signature invalid" for h in heads
             if not hmac.compare_digest(str(h.get("mac")), _mac(key, h))]
    if anchor not in [h.get("head") for h in heads]:
        found.append(f"the anchor {anchor} is the head of no signed request of {ledger.name}")
    if not ledger.exists():
        return found + ([f"{ledger.name} missing; {len(heads)} heads signed"] if heads else [])
    size, signed = ledger.stat().st_size, heads[-1].get("bytes") if heads else 0
    if size != signed:
        found.append(f"{ledger.name} is {size} bytes; the last signed head says {signed}")
    try:
        groups = _requests(_lines(ledger))
    except json.JSONDecodeError as e:
        return found + [f"{ledger.name}: not JSONL ({e})"]
    got = [(rid, len(rs), rs[-1].get("sha256")) for rid, rs in groups]
    want = [(h.get("request_id"), h.get("records"), h.get("head")) for h in heads]
    if got != want:
        found.append(f"requests in {ledger.name} {got} are not the signed heads {want}")
    for rid, rs in groups:
        found += _chain_findings(rid, rs)
    return found
