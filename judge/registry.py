"""Candidate registration (brief 1 A4 item 2). The judge takes a candidate's proposer from the credential that registered
its image, never from anything the candidate shipped.

A credential is a random token the judge issues to one party, `{kind, model, session}` with `kind` one of CLAUDE.md
A1.7's kinds. The judge keeps only the token's SHA-256 beside the party, in `credentials.jsonl` in its private storage;
the token itself is printed once, to whoever issued it. Registration takes an image digest and a token, nothing else:
the image's contents, labels and files are never read, so a candidate cannot name its own proposer. A token matching no
issued credential is refused `unattributed`, recording nothing. An image is registered once: the same party registering
it again gets its registration back; another party is refused `registered`, so a later credential cannot take over an
earlier party's image. `proposer_of` is what every judge record of an image carries."""

from __future__ import annotations

import fcntl
import hashlib
import hmac
import json
import os
import re
import secrets
from collections.abc import Mapping
from pathlib import Path

from judge import private as storage

KINDS = ("builder", "reviewer", "guy", "counsel")
CREDENTIALS = "credentials.jsonl"
REGISTRATIONS = "registrations.jsonl"
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")


class Refused(Exception):
    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def _private(path: Path) -> Path:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if found := storage.findings(path):
        raise Refused("not_private", f"{'; '.join(found)}; judge-private storage is 0700 and the judge's own, "
                                     f"and so is every file in it")
    return path


def _lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def _locked_append(path: Path, act) -> object:
    """Run `act(rows)` under an exclusive lock on `path`; append and sync the row it returns second, if any."""
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        result, row = act(_lines(path))
        if row is not None:
            os.write(fd, json.dumps(row, sort_keys=True).encode() + b"\n")
            os.fsync(fd)
        return result
    finally:
        os.close(fd)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _proposer(p: Mapping) -> dict:
    """`p` as a proposer, `{kind, model, session}`; Guy alone may leave model and session empty (A1.7)."""
    out = {k: p.get(k) for k in ("kind", "model", "session")}
    if set(p) != set(out) or out["kind"] not in KINDS or not all(isinstance(v, str) for v in out.values()) \
            or (out["kind"] != "guy" and not (out["model"] and out["session"])):
        raise Refused("bad_proposer", f"{dict(p)} is not {{kind in {KINDS}, model, session}}")
    return out


def credential(private: Path, proposer: Mapping) -> str:
    """Issue a credential to `proposer` and return its token; the judge keeps only the token's SHA-256."""
    party = _proposer(proposer)
    token = secrets.token_hex(32)
    _locked_append(_private(private) / CREDENTIALS, lambda _: (None, {"token_sha256": _hash(token), "proposer": party}))
    return token


def _holder(private: Path, token: str) -> dict | None:
    """The party holding `token`, or None if the judge issued no credential matching it."""
    want = _hash(token)
    held = [r["proposer"] for r in _lines(private / CREDENTIALS) if hmac.compare_digest(r["token_sha256"], want)]
    return held[0] if held else None


def register(private: Path, image: str, token: str) -> dict:
    """Register `image` under the credential `token`; return the registration `{image, proposer, credential}`."""
    if not (isinstance(image, str) and DIGEST.fullmatch(image)):
        raise Refused("bad_image", f"{image!r} is not an image digest sha256:<64 hex>")
    party = _holder(_private(private), token if isinstance(token, str) else "")
    if party is None:
        raise Refused("unattributed", f"{image}: no credential the judge issued matches; a candidate with no "
                                      f"attributable proposer is refused")

    def act(rows: list[dict]):
        past = [r for r in rows if r["image"] == image]
        if past and past[0]["proposer"] == party:
            return past[0], None
        if past:
            raise Refused("registered", f"{image} is registered to {past[0]['proposer']}, not {party}")
        row = {"image": image, "proposer": party, "credential": _hash(token)}
        return row, row

    return _locked_append(private / REGISTRATIONS, act)


def proposer_of(private: Path, image: str) -> dict:
    """The proposer every judge record of `image` carries: the party whose credential registered it."""
    past = [r for r in _lines(private / REGISTRATIONS) if r["image"] == image]
    if not past:
        raise Refused("unregistered", f"{image} was never registered")
    return past[0]["proposer"]
