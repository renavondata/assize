"""Seed issuance (brief 1 section 2; pin P1). Evaluation seeds come from a CSPRNG, are logged only in judge-private
storage, and are checked against every seed issued before them; a public training-seed stream is domain-separated
from them, and the separation is checked.

A seed is known by its World's key: the value that actually determines the World, so that two seeds the World reduces
to one count as one. Crafter, for example, generates from `hash((seed, 1)) % (2**31 - 1)`. Keys are split into two
domains by parity: evaluation keys are odd, training keys even. Every training seed is even-keyed by construction and
every issued seed is checked odd-keyed, so no training seed can ever be an evaluation seed.

The store is one append-only JSONL file per World in a directory only the judge's user may enter. `admit` is the
issuance check: under an exclusive lock it rereads every record and refuses a seed whose key was ever issued, a key
outside the evaluation domain, a duplicate within the request, or a request id already used; only then does it append
and sync. `issue` draws and filters fresh seeds, and every seed it returns has passed `admit`."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import secrets
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from judge import private as storage

SEED_SPACE = 2**31 - 1  # Crafter's own default seed range, [0, 2**31 - 1)
EVAL, TRAIN = 1, 0  # a key's domain is its parity
TRAIN_TAG = b"assize/training-seeds/"

Key = Callable[[int], int]


class SeedError(Exception):
    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def domain(key: int) -> int:
    return key % 2


def training_seeds(world: str, key: Key, n: int) -> list[int]:
    """The first `n` seeds of `world`'s public training stream: SHA-256 of a tag, the World's name and a counter,
    reduced to the seed space, keeping only seeds whose key is in the training domain. Deterministic and public."""
    def candidate(j: int) -> int:
        digest = hashlib.sha256(TRAIN_TAG + world.encode() + b"/" + str(j).encode()).digest()
        return int.from_bytes(digest[:8], "big") % SEED_SPACE

    out: list[int] = []
    j = 0
    while len(out) < n:
        s = candidate(j)
        if domain(key(s)) == TRAIN:
            out.append(s)
        j += 1
    return out


def _private_dir(path: Path) -> Path:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if found := storage.findings(path):
        raise SeedError("not_private", f"{'; '.join(found)}; judge-private storage is 0700 and the judge's own, "
                                       f"and so is every file in it")
    return path


def store_path(root: Path, world: str) -> Path:
    return _private_dir(Path(root)) / f"{world}.seeds.jsonl"


def records(root: Path, world: str) -> list[dict]:
    p = store_path(root, world)
    return [json.loads(line) for line in p.read_text().splitlines()] if p.exists() else []


def admit(root: Path, world: str, key: Key, seeds: Sequence[int], request_id: str,
          issued_to: Mapping = {}) -> list[int]:
    """The issuance check. Refuses the whole request, recording nothing, if any seed is outside the seed space,
    keyed outside the evaluation domain, keyed like an earlier issued seed or another seed of this request, or if
    `request_id` was used before; otherwise appends one record per seed, carrying `issued_to` (the image and proposer
    the seeds are issued to), and syncs. Returns the seeds."""
    p = store_path(root, world)
    fd = os.open(p, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        past = records(root, world)
        if any(r["request_id"] == request_id for r in past):
            raise SeedError("request_reused", f"request {request_id!r} already has seeds")
        used = {r["key"] for r in past}
        bad = [s for s in seeds if not (type(s) is int and 0 <= s < SEED_SPACE)]
        if bad:
            raise SeedError("out_of_space", f"{bad} not in [0, {SEED_SPACE})")
        keyed = [(s, key(s)) for s in seeds]
        bad = [s for s, k in keyed if domain(k) != EVAL]
        if bad:
            raise SeedError("training_domain", f"{bad} are keyed in the training domain")
        bad = [s for s, k in keyed if k in used]
        if bad:
            raise SeedError("reused", f"{bad} were issued before")
        if len({k for _, k in keyed}) != len(keyed):
            raise SeedError("reused", f"{list(seeds)} repeat a key within request {request_id!r}")
        os.write(fd, b"".join(json.dumps(dict(issued_to) | {"request_id": request_id, "seed": s, "key": k},
                                         sort_keys=True).encode()
                              + b"\n" for s, k in keyed))
        os.fsync(fd)
        return list(seeds)
    finally:
        os.close(fd)


def fresh(root: Path, world: str, key: Key, n: int) -> list[int]:
    """`n` seeds from the CSPRNG, each keyed in the evaluation domain and unlike every issued seed and each other."""
    used = {r["key"] for r in records(root, world)}
    out: list[int] = []
    while len(out) < n:
        s = secrets.randbelow(SEED_SPACE)
        k = key(s)
        if domain(k) == EVAL and k not in used:
            used.add(k)
            out.append(s)
    return out


def issue(root: Path, world: str, key: Key, n: int, request_id: str, issued_to: Mapping = {}) -> list[int]:
    """`n` fresh evaluation seeds for `request_id`, admitted and recorded, with `issued_to`, in judge-private storage
    before return."""
    seeds = fresh(root, world, key, n)
    return admit(root, world, key, seeds, request_id, issued_to)
