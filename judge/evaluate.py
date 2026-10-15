"""`evaluate(candidate_image_digest, world, n_episodes, request_id)` (brief 1 section 2; A4 items 1 and 2).

Non-interactive and idempotent per `request_id`. In order:

1. The image's proposer is `registry.proposer_of` it: the party whose judge-issued credential registered it. An image
   never registered is refused `unregistered` before anything else, so no seed is issued to it (A4 item 2).
2. A `request_id` the ledger already holds under a signed head returns its records as written, running nothing and
   issuing nothing, once they are checked against the signed head (signature, count, chain, last `sha256`; a mismatch
   is refused `ledger_unverified`); the same `request_id` asked of another image, World or episode count is refused
   `request_conflict`.
   A `request_id` whose seeds were issued but whose records were never signed (a judge that died mid-request) is
   refused `interrupted`: its seeds are spent and never reissued, and a new `request_id` is needed. The next request
   of its World seals it into the ledger first, whoever asks it (`_seal`, below; reports/L1/REPORT.md obligation 4).
3. The World must be one the judge binds, its manifest must commit a price, `n_episodes` must be a positive integer, the
   runtime usable and the image present locally under the ID it is asked by (`image_not_id` if it resolves to an image
   whose ID is another, `_present`); otherwise the request is refused before any seed is issued. The judge
   binds every directory of `worlds/` holding both a `manifest.json` and a `binding.py`, under the directory's name; it
   keeps no table of Worlds, so a World is added by its directory alone (brief 2 A2, P19). A World's price is its
   manifest's `price` block, never another World's (P20).
4. `n_episodes` fresh evaluation seeds are issued from the CSPRNG into judge-private storage (`seeds.issue`) and each
   World is built from one. No seed leaves the judge: no record carries one.
5. The candidate plays every episode through the judge's loop (`episodes.run`): one record per episode, failures
   included, with its termination code, log-loss, calibration, measured compute and price.
6. Each record is stamped with `schema_version`, `judge_sha256` (the hash of the judge's code and config, `judge_hash`),
   the candidate image digest, its `proposer`, the World, the runtime, the request's episode count and the episode's
   achievement set. The digest a record's `image` means is the image ID its `runtime` reports for the candidate, which
   under Podman and Docker's classic image store is the SHA-256 of the image's config blob: not a registry manifest
   digest, which names one encoding of the image in one registry, and not a name (brief 2 A2, L2a obligation 17;
   review 6debf231b630 F5). Each record is then chained and appended to the World's append-only ledger as its
   episode ends, and the request's head signed after the last (`ledger.append`). Steps 4 to 6 hold the World's request lock, and begin by sealing
   every interrupted request of the World (`ledger.seal_interrupted`): the episodes it played stay in the ledger, and
   one closing record states its seeds issued, the image and proposer they were issued to (recorded with them at
   issue) and its episodes recorded, all signed. So a request killed and asked again
   under another id leaves its played episodes and its spent seeds on the record, and cannot be selected away."""

from __future__ import annotations

import collections
import contextlib
import fcntl
import hashlib
import importlib
import os
import subprocess
from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path

from judge import episodes, ledger, price, registry, runtime, seeds

ROOT = Path(__file__).resolve().parent.parent
# Where the World bindings live: each `worlds/<name>/binding.py` provides `Episode(seed)`, `world_seed(seed)` and
# `manifest()`, and is bound only beside its `manifest.json`.
WORLDS = ROOT / "worlds"
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
    """The records of `request_id` as written, if its head was signed and they match it; None if the ledger holds no
    such request; refused `ledger_unverified` if they do not match."""
    held = ledger.request_records(led, private, request_id)
    if held is None:
        return None
    rows, found = held
    if found:
        raise Refused("ledger_unverified", f"request {request_id!r} does not match its signed head: {found}")
    return rows


def bound(worlds: Path = WORLDS) -> list[str]:
    """The names of the Worlds the judge binds: every directory of `worlds` with a `manifest.json` and a `binding.py`."""
    return sorted(d.name for d in worlds.iterdir() if (d / "manifest.json").is_file() and (d / "binding.py").is_file())


def _binding(world: str):
    names = bound()
    if world not in names:
        raise Refused("unknown_world", f"{world!r} is not a World the judge binds ({names})")
    return importlib.import_module(f"worlds.{world}.binding")


def _priced(binding) -> dict:
    """The World's manifest, refused `unpriced` if it commits no price."""
    m = binding.manifest()
    try:
        price.of(m)
    except price.Unpriced as e:
        raise Refused("unpriced", str(e)) from e
    return m


def _usable(name: str) -> runtime.Runtime:
    rt = next((r for r in runtime.RUNTIMES if r.name == name), None)
    if rt is None:
        raise Refused("unknown_runtime", f"{name!r} is not one of {[r.name for r in runtime.RUNTIMES]}")
    e = runtime.engine(rt)
    if not e.usable:
        raise Refused("runtime_unusable", e.identity)
    return rt


def _present(rt: runtime.Runtime, image: str) -> None:
    """`image` is present under `rt` and is the image ID `rt` reports for it (`image inspect`'s `.Id`), so the `image`
    a record carries is that ID and nothing that merely resolves to an image: another ID, a name, a manifest digest."""
    out = subprocess.run([rt.binary, "image", "inspect", "--format", "{{.Id}}", image], capture_output=True, text=True)
    if out.returncode:
        raise Refused("image_absent", f"{image} is not present under {rt.name}; the judge never pulls a candidate")
    iid = out.stdout.strip()
    iid = iid if iid.startswith("sha256:") else f"sha256:{iid}"
    if iid != image:
        raise Refused("image_not_id", f"{image} resolves under {rt.name} to the image whose ID is {iid}; a record "
                                      f"names a candidate by its image ID, so register and ask with that")


def _played(binding, issued: Sequence[int], m: dict, achieved: list):
    """Each World of `issued`, built only when the loop asks for it; once the loop moves past a World, its
    achievement set is appended to `achieved`, so no more than one World is held at a time."""
    for s in issued:
        w = binding.Episode(s, m)
        yield w
        achieved.append(w.achievements)


def stamp(records: Iterable[dict], achieved: Sequence[Sequence[str]], *, n_episodes: int, image: str, proposer: dict,
          world: str, rt: str, judge_sha256: str) -> Iterator[dict]:
    """`records`, one per episode, each as it is drawn, with what every judge record carries (brief 1 section 2, A4
    item 2) and its episode's achievement set (section 3), `achieved[episode]` by then."""
    return ({"schema_version": episodes.SCHEMA_VERSION, "judge_sha256": judge_sha256, "image": image,
             "proposer": proposer, "world": world, "runtime": rt, "n_episodes": n_episodes,
             "achievements": list(achieved[r["episode"]])} | r
            for r in records)


@contextlib.contextmanager
def _alone(private: Path, world: str):
    """Hold the World's request lock, in judge-private storage, for the rest of the request: one request writes the
    World's ledger at a time, so a request found issued but unsigned while holding it was interrupted, not running.
    The lock dies with its holder."""
    fd = os.open(seeds.store_path(private, world).with_suffix(".lock"), os.O_WRONLY | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def _seal(led: Path, private: Path, world: str) -> list[str]:
    """Seal into the ledger every interrupted request of `world` (`ledger.seal_interrupted`), its played episodes and
    spent seeds included; the request_ids sealed. Each closing record carries the `image` and `proposer` its seeds were
    issued to (A1.7; brief 1 A4 item 2), so a request's spent seeds are charged to the party that asked it. A ledger
    tail that is no interrupted request's is `ledger_unverified`."""
    held = seeds.records(private, world)
    issued = collections.Counter(r["request_id"] for r in held)
    first = {r["request_id"]: r for r in reversed(held)}
    stamp = {"schema_version": episodes.SCHEMA_VERSION, "judge_sha256": judge_hash(), "world": world}
    closing = {rid: stamp | {"issued": n,
                             "image": first[rid].get("image"),
                             "proposer": first[rid].get("proposer")}
               for rid, n in issued.items()}
    try:
        return ledger.seal_interrupted(led, private, closing)
    except ValueError as e:
        raise Refused("ledger_unverified", str(e)) from e


def evaluate(image: str, world: str, n_episodes: int, request_id: str, *, private: Path, ledgers: Path,
             runtime_name: str) -> list[dict]:
    """Evaluate the registered candidate `image` on `n_episodes` fresh seeds of `world`; return the request's records
    as the ledger holds them."""
    private, led = Path(private), ledger_path(ledgers, world)
    proposer = registry.proposer_of(private, image)
    done = _recorded(led, private, request_id)
    if done is not None:
        if done[-1].get("interrupted"):
            raise Refused("interrupted", f"request {request_id!r} was interrupted after {done[-1]['recorded']} of "
                                         f"{done[-1]['issued']} episodes, sealed as such; its seeds are spent, ask "
                                         f"again under a new request_id")
        asked = {(r["image"], r["world"], r["n_episodes"]) for r in done}
        if asked != {(image, world, n_episodes)}:
            raise Refused("request_conflict", f"request {request_id!r} was {sorted(asked)}, not "
                                              f"{(image, world, n_episodes)}")
        return done
    binding = _binding(world)
    m = _priced(binding)
    if not (type(n_episodes) is int and n_episodes > 0):
        raise Refused("bad_episodes", f"{n_episodes!r} is not a positive episode count")
    rt = _usable(runtime_name)
    _present(rt, image)
    led.parent.mkdir(parents=True, exist_ok=True)
    with _alone(private, world):
        if request_id in _seal(led, private, world):
            raise Refused("interrupted", f"request {request_id!r} had seeds but no signed records; sealed as "
                                         f"interrupted, its seeds are spent, ask again under a new request_id")
        try:
            issued = seeds.issue(private, world, binding.world_seed, n_episodes, request_id,
                                 {"image": image, "proposer": proposer})
        except seeds.SeedError as e:
            if e.code == "request_reused":
                raise Refused("interrupted", f"request {request_id!r} has seeds but no signed records; its seeds "
                                             f"are spent, ask again under a new request_id") from e
            raise
        achieved: list = []
        records = episodes.played(rt, image, _played(binding, issued, m, achieved), m)
        stamped = stamp(records, achieved, n_episodes=n_episodes, image=image, proposer=proposer, world=world,
                        rt=rt.name, judge_sha256=judge_hash())
        return ledger.append(led, private, request_id, stamped)
