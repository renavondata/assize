"""`evaluate(candidate_image_digest, world, n_episodes, request_id)` (brief 1 section 2; A4 items 1 and 2).

Non-interactive and idempotent per `request_id`. In order:

1. The image's proposer is `registry.proposer_of` it: the party whose judge-issued credential registered it. An image
   never registered is refused `unregistered` before anything else, so no seed is issued to it (A4 item 2).
2. A `request_id` the ledger already holds under a signed head returns its records as written, running nothing and
   issuing nothing; the same `request_id` asked of another image, World or episode count is refused `request_conflict`.
   A `request_id` whose seeds were issued but whose records were never signed (a judge that died mid-request) is
   refused `interrupted`: its seeds are spent and never reissued, and a new `request_id` is needed.
3. The World must be one the judge binds, `n_episodes` a positive integer, the runtime usable and the image present
   locally; otherwise the request is refused before any seed is issued.
4. `n_episodes` fresh evaluation seeds are issued from the CSPRNG into judge-private storage (`seeds.issue`) and each
   World is built from one. No seed leaves the judge: no record carries one.
5. The candidate plays every episode through the judge's loop (`episodes.run`): one record per episode, failures
   included, with its termination code, log-loss, calibration, measured compute and price.
6. Each record is stamped with `schema_version`, `judge_sha256` (the hash of the judge's code and config, `judge_hash`),
   the candidate image digest, its `proposer`, the World, the runtime, the request's episode count and the episode's
   achievement set, then chained and signed into the World's append-only ledger (`ledger.append`)."""

from __future__ import annotations

import hashlib
import importlib
import subprocess
from collections.abc import Sequence
from pathlib import Path

from judge import episodes, ledger, registry, runtime, seeds

ROOT = Path(__file__).resolve().parent.parent
# The World bindings the judge owns, by name: each module provides `Episode(seed)`, `world_seed(seed)` and `manifest()`.
WORLDS = {"crafter": "worlds.crafter.binding"}
# What `judge_sha256` covers, relative to the repository root: the judge, the interface, the World bindings and the
# lock file that pins every World's package. Bytecode caches are not code.
HASHED = ("judge", "worlds", "uv.lock")
Refused = registry.Refused


def _files(root: Path) -> list[Path]:
    paths = [root / p for p in HASHED]
    return sorted((f for p in paths for f in ([p] if p.is_file() else p.rglob("*"))
                   if f.is_file() and "__pycache__" not in f.relative_to(root).parts),
                  key=lambda f: f.relative_to(root).as_posix())


def judge_hash(root: Path = ROOT) -> str:
    """SHA-256 over every file `HASHED` names under `root`, in path order: each file's path, a NUL, the SHA-256 of
    its bytes and a newline. Any change of code, config, interface, binding or World version changes it."""
    h = hashlib.sha256()
    for f in _files(root):
        h.update(f.relative_to(root).as_posix().encode() + b"\0" + hashlib.sha256(f.read_bytes()).hexdigest().encode()
                 + b"\n")
    return h.hexdigest()


def ledger_path(ledgers: Path, world: str) -> Path:
    return Path(ledgers) / f"{world}.ledger.jsonl"


def _recorded(led: Path, private: Path, request_id: str) -> list[dict] | None:
    """The records of `request_id` as written, if its head was signed; None if the ledger holds no such request."""
    if not any(h["ledger"] == led.name and h["request_id"] == request_id
               for h in ledger._lines(private / ledger.HEADS)):
        return None
    return [r for r in ledger._lines(led) if r.get("request_id") == request_id]


def _binding(world: str):
    if world not in WORLDS:
        raise Refused("unknown_world", f"{world!r} is not a World the judge binds ({sorted(WORLDS)})")
    return importlib.import_module(WORLDS[world])


def _usable(name: str) -> runtime.Runtime:
    rt = next((r for r in runtime.RUNTIMES if r.name == name), None)
    if rt is None:
        raise Refused("unknown_runtime", f"{name!r} is not one of {[r.name for r in runtime.RUNTIMES]}")
    e = runtime.engine(rt)
    if not e.usable:
        raise Refused("runtime_unusable", e.identity)
    return rt


def _present(rt: runtime.Runtime, image: str) -> None:
    if subprocess.run([rt.binary, "image", "inspect", image], capture_output=True).returncode:
        raise Refused("image_absent", f"{image} is not present under {rt.name}; the judge never pulls a candidate")


def _played(binding, issued: Sequence[int], m: dict, achieved: list):
    """Each World of `issued`, built only when the loop asks for it; once the loop moves past a World, its
    achievement set is appended to `achieved`, so no more than one World is held at a time."""
    for s in issued:
        w = binding.Episode(s, m)
        yield w
        achieved.append(w.achievements)


def stamp(records: Sequence[dict], achieved: Sequence[Sequence[str]], *, image: str, proposer: dict, world: str,
          rt: str, judge_sha256: str) -> list[dict]:
    """`records`, one per episode, each with what every judge record carries (brief 1 section 2, A4 item 2) and its
    episode's achievement set (section 3)."""
    return [{"schema_version": episodes.SCHEMA_VERSION, "judge_sha256": judge_sha256, "image": image,
             "proposer": proposer, "world": world, "runtime": rt, "n_episodes": len(records),
             "achievements": list(a)} | r
            for r, a in zip(records, achieved, strict=True)]


def evaluate(image: str, world: str, n_episodes: int, request_id: str, *, private: Path, ledgers: Path,
             runtime_name: str) -> list[dict]:
    """Evaluate the registered candidate `image` on `n_episodes` fresh seeds of `world`; return the request's records
    as the ledger holds them."""
    private, led = Path(private), ledger_path(ledgers, world)
    proposer = registry.proposer_of(private, image)
    done = _recorded(led, private, request_id)
    if done is not None:
        asked = {(r["image"], r["world"], r["n_episodes"]) for r in done}
        if asked != {(image, world, n_episodes)}:
            raise Refused("request_conflict", f"request {request_id!r} was {sorted(asked)}, not "
                                              f"{(image, world, n_episodes)}")
        return done
    binding = _binding(world)
    if not (type(n_episodes) is int and n_episodes > 0):
        raise Refused("bad_episodes", f"{n_episodes!r} is not a positive episode count")
    rt = _usable(runtime_name)
    _present(rt, image)
    try:
        issued = seeds.issue(private, world, binding.world_seed, n_episodes, request_id)
    except seeds.SeedError as e:
        if e.code == "request_reused":
            raise Refused("interrupted", f"request {request_id!r} has seeds but no signed records; its seeds are "
                                         f"spent, ask again under a new request_id") from e
        raise
    m = binding.manifest()
    achieved: list = []
    records = episodes.run(rt, image, _played(binding, issued, m, achieved), m)
    stamped = stamp(records, achieved, image=image, proposer=proposer, world=world, rt=rt.name,
                    judge_sha256=judge_hash())
    led.parent.mkdir(parents=True, exist_ok=True)
    return ledger.append(led, private, request_id, stamped)
