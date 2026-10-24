"""NetHack 3.6.6 World binding (brief 2 section 3, Version mismatch): one episode of NLE v0.7.3's NetHackChallenge, the
NetHack line AutoAscend plays, declared as a World of its own beside `nethack` (NLE 1.3.0, NetHack 3.6.7) and never
pooled with it.

The game does not run in the judge's interpreter. Two `nle` versions cannot share one, and 3.6.6's C does not build on
a current glibc, so each episode is a container of the image `image/Containerfile` builds, run through
`judge.runtime.run_argv`: no network, a read-only root, every capability dropped, the judge's candidate limits. The
image preloads libfaketime and the instant it is given is derived from the issued seed (`instant`), so the
game's clock-driven effects (moon phase, Friday the 13th, night, midnight) come from the seed and not from the date the
episode is played on; NLE v0.7.3 has no `fix_moon_phase`. `image/server.py` speaks one JSON line per step over the
container's stdin and stdout. Its game is seeded from the issued seed as in the `nethack` binding: the core and display
streams each from a hash of the seed, NetHack's anti-automation reseeding off (NLE v0.7.3 has no level-generator stream).

The image is built from the recipe in `image/` and tagged with a hash of that recipe (`image_tag`). `Episode` never
builds and never pulls: an absent image is an error, and `build` is the one act that makes it present.

The per-episode utility is BALROG's progression, computed here, in the judge's process, by the class `nethack`'s binding
vendors and checksums (`worlds/nethack/balrog/`), from the same bottom-line stats and terminal the container sends; it
is never reimplemented. The judge binds this World beside its `manifest.json` (`judge.evaluate.bound`)."""

from __future__ import annotations

import datetime
import enum
import hashlib
import json
import re
import subprocess
import uuid
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path

import numpy

# The versions the image builds and records (brief 2 section 2, Versions): NLE v0.7.3 and the NetHack in its game library.
NLE_VERSION = "0.7.3"
NETHACK_VERSION = "3.6.6"
IMAGE_DIR = Path(__file__).with_name("image")
# The files that make the image: its tag is a hash of them, so a changed recipe is a different image.
IMAGE_FILES = ("Containerfile", "server.py")
MANIFEST = Path(__file__).with_name("manifest.json")
# Every observation key the image's server emits (`image/server.py` KEYS).
SERVED = ("glyphs", "chars", "message", "blstats", "inv_glyphs", "inv_letters", "inv_oclasses", "inv_strs", "misc",
          "specials", "tty_chars", "tty_cursor")
# The game's two RNG streams, each seeded from the issued seed under its own name.
STREAMS = ("core", "disp")
# NLE v0.7.3's bottom-line stats in `blstats` order, each under NLE's own name for it (`nethack.NLE_BL_<name>`,
# lowercased), read from the image (`installed`).
BLSTATS = ("x", "y", "str25", "str125", "dex", "con", "int", "wis", "cha", "score", "hp", "hpmax", "depth", "gold", "ene",
           "enemax", "ac", "hd", "xp", "exp", "time", "hunger", "cap", "dnum", "dlevel", "condition")
class EndStatus(enum.IntEnum):
    """NLE v0.7.3's `NLE.StepStatus`, read from the image: how a step left the game. BALROG's progression names the end
    of an episode by it."""

    ABORTED = -1  # the task aborted the episode: its step limit, or no progress
    RUNNING = 0
    DEATH = 1  # the game's own end


ABORTED = EndStatus.ABORTED
# The year from which the clock of an episode is drawn: a year of 365 days, every moon phase and a Friday the 13th.
CLOCK_YEAR = 2021
# The size of the one writable directory of a game container, `/tmp`, in MiB.
TMP_MIB = 128
# The names of containers this binding starts, so that a pin can list what it left behind.
CONTAINER_PREFIX = "assize-nethack366-"
# Run in the image to read what it contains.
INSTALLED = """
import importlib.metadata, json, re
from pathlib import Path
import nle
from nle import nethack
lib = Path(nle.__file__).with_name("libnethack.so").read_bytes()
banner = re.search(rb"NetHack Version (\\d+\\.\\d+\\.\\d+)", lib)
names = sorted((n for n in dir(nethack) if n.startswith("NLE_BL_")), key=lambda n: getattr(nethack, n))
print(json.dumps({"nle": importlib.metadata.version("nle"), "nethack": banner.group(1).decode() if banner else "",
                  "blstats": [n[len("NLE_BL_"):].lower() for n in names]}))
"""


def image_tag() -> str:
    """The tag of the image the recipe in `image/` builds: a hash of the files that make it."""
    h = hashlib.sha256()
    for name in IMAGE_FILES:
        h.update(name.encode() + b"\0" + (IMAGE_DIR / name).read_bytes() + b"\0")
    return f"assize-nethack366:{h.hexdigest()[:16]}"


def runtime():
    """The first container runtime the judge admits on this host, Docker before Podman (`judge.runtime.engine`)."""
    from judge import runtime as rt

    usable = [r for r in rt.RUNTIMES if rt.engine(r).usable]
    if not usable:
        raise RuntimeError("no usable container runtime for the NetHack 3.6.6 game")
    return usable[0]


def present(rt=None) -> bool:
    """Whether the image the recipe builds is present under the runtime."""
    rt = rt or runtime()
    return subprocess.run([rt.binary, "image", "inspect", image_tag()], capture_output=True).returncode == 0


def build(rt=None) -> str:
    """Build the image from `image/` under the runtime if it is absent, and return its tag. This is the only act of this
    binding that uses the network (the recipe's apt, pip and git steps); an episode never does."""
    rt = rt or runtime()
    if not present(rt):
        subprocess.run([rt.binary, "build", "-q", "-t", image_tag(), str(IMAGE_DIR)], check=True, capture_output=True)
    return image_tag()


def seeds(seed: int) -> dict[str, int]:
    """The game's seed for each stream: the first 8 bytes of SHA-256 of `<seed>:<stream>`, read big-endian and kept
    below 2**63, the range NLE draws its own seeds from. Independent of string-hash salting."""
    return {s: int.from_bytes(hashlib.sha256(f"{seed}:{s}".encode()).digest()[:8], "big") >> 1 for s in STREAMS}


def instant(seed: int) -> str:
    """The instant at which the game's clock is frozen for `seed`, as `faketime -f` reads it: a day of CLOCK_YEAR and an
    hour, each a distinct hash of the seed. Independent of the date the episode is played on."""
    digest = hashlib.sha256(f"{seed}:clock".encode()).digest()
    day = datetime.date(CLOCK_YEAR, 1, 1) + datetime.timedelta(days=int.from_bytes(digest[:8], "big") % 365)
    return f"{day.isoformat()} {int.from_bytes(digest[8:16], 'big') % 24:02d}:00:00"


def world_seed(seed: int) -> int:
    """The seed from which the World of `seed` generates: `seed` itself, since its game's streams and clock are each a
    distinct hash of it, so distinct seeds name distinct Worlds."""
    return seed


def manifest() -> dict:
    return json.loads(MANIFEST.read_text())


def identifier(name: str) -> str:
    """A manifest name for an nle or BALROG name: lowercased, every character that is not a letter or digit dropped."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def balrog():
    """BALROG's vendored `progress` module, loaded and checksummed by the `nethack` binding that vendors it."""
    from worlds.nethack import binding

    return binding.balrog()


def installed(rt=None) -> dict:
    """What the image contains, read inside it: the `nle` distribution's version, the NetHack version in the banner of
    the game library nle loads, and NLE's bottom-line stat names in order."""
    return json.loads(run_in_image(INSTALLED, rt))


def run_in_image(code: str, rt=None) -> str:
    """The standard output of the Python `code` run once in a fresh game container of the image, under the isolation an
    episode has, with the clock frozen at `instant(0)`; the container is removed after. Raises if it exits non-zero."""
    from judge import runtime as jr

    rt = rt or runtime()
    name = f"{CONTAINER_PREFIX}once-{uuid.uuid4().hex[:12]}"
    out = subprocess.run(_argv(rt, name, instant(0), ["python", "-c", code]), stdin=subprocess.DEVNULL,
                         capture_output=True, text=True)
    subprocess.run(jr.remove_argv(rt, name), capture_output=True)
    if out.returncode:
        raise RuntimeError(f"running in the image failed ({out.returncode}): {out.stderr.strip()[-300:]}")
    return out.stdout


def _argv(rt, name: str, clock: str, command: list[str]) -> list[str]:
    from judge import runtime as jr

    argv = jr.run_argv(rt, image_tag(), jr.limits(), name, [f"FAKETIME={clock}", *command])
    # NLE makes a game directory under the temporary directory, which a read-only root does not give it: the one writable
    # place is a size-bounded tmpfs, inserted before the image.
    at = argv.index(image_tag())
    return [*argv[:at], f"--tmpfs=/tmp:rw,nosuid,size={TMP_MIB}m", *argv[at:]]


def view(raw: Mapping) -> dict:
    """The manifest's observation of the container's: the map, the message line, and each bottom-line stat under its
    name."""
    return {"glyphs": raw["glyphs"], "toplines": raw["message"]} | dict(zip(BLSTATS, raw["blstats"], strict=True))


class Game:
    """One container running one episode of `image/server.py`, spoken to a JSON line at a time."""

    def __init__(self, seed: int, rt=None):
        from judge import runtime as jr

        self.rt = rt or runtime()
        self.name = f"{CONTAINER_PREFIX}{uuid.uuid4().hex[:12]}"
        argv = _argv(self.rt, self.name, instant(seed), ["python", "/server.py"])
        self.proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     text=True, bufsize=1)
        self._remove = jr.remove_argv(self.rt, self.name)
        try:
            self.send(seeds(seed))
            self.reply = self.read()
        except BaseException:
            self.close()
            raise

    def send(self, record: Mapping) -> None:
        self.proc.stdin.write(json.dumps(record, separators=(",", ":")) + "\n")
        self.proc.stdin.flush()

    def read(self) -> dict:
        line = self.proc.stdout.readline()
        if not line:
            raise RuntimeError(f"the game container ended: {self.proc.stderr.read()[-500:]}")
        return json.loads(line)

    def step(self, action: int) -> dict:
        self.send({"action": action})
        self.reply = self.read()
        return self.reply

    def close(self) -> None:
        """Remove the container at once, whatever it is doing, and wait for its client."""
        subprocess.run(self._remove, capture_output=True)
        try:
            self.proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
        for stream in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
            stream.close()


class Episode:
    """One NetHackChallenge episode from `seed`, played in the image. The seed stays here; nothing it returns carries
    it."""

    def __init__(self, seed: int, m: Mapping | None = None, rt=None):
        self.manifest = m or manifest()
        self._game = Game(seed, rt)
        self.t = 0
        self.done = False
        self.truncated = False
        self.end_status = None
        self.nle = self._game.reply["observation"]
        self.observation = view(self.nle)
        # The class BALROG's `get_progress_system` gives NetHackChallenge, fresh at reset as in BALROG's NLE wrapper.
        self.progress = balrog().Progress()

    @property
    def utility(self) -> float:
        """BALROG's progression of the episode so far, in [0, 1] (brief 2 section 2, Utility)."""
        return self.progress.progression

    @property
    def achievements(self) -> list[str]:
        """The progression table's entries the episode reached, depths then experience levels, as manifest names."""
        return [identifier(k) for k in self.progress.dlvl_list + self.progress.xplvl_list]

    @property
    def termination(self) -> str:
        """How the World ended the episode: `truncated` where the task aborted it (its step limit, or no progress), else
        `terminal`."""
        return "truncated" if self.truncated else "terminal"

    @property
    def legal_actions(self) -> list[int]:
        """Every key of NetHackChallenge's full keyboard is legal at every step; NetHack answers one it cannot use."""
        return list(range(len(self.manifest["actions"])))

    def step(self, action: int) -> dict:
        if self.done:
            raise RuntimeError("step after the episode ended")
        if action not in self.legal_actions:
            raise ValueError(f"illegal action {action!r}")
        reply = self._game.step(action)
        self.t += 1
        self.done = bool(reply["done"])
        self.end_status = int(reply["end_status"])
        self.truncated = self.done and self.end_status == ABORTED
        self.nle = reply["observation"]
        self.observation = view(self.nle)
        self.progress.update({"blstats": self.nle["blstats"], "tty_chars": numpy.array(self.nle["tty_chars"],
                                                                                         dtype=numpy.uint8)},
                             0.0, self.done, {"end_status": EndStatus(self.end_status)})
        return self.observation

    def close(self) -> None:
        self._game.close()


def _line(record: Mapping) -> bytes:
    return json.dumps(record, sort_keys=True, separators=(",", ":")).encode()


def trajectory(seed: int, actions: Iterable[int], watch: Callable[[Episode], None] = lambda ep: None
               ) -> tuple[str, int]:
    """Play `actions` from `seed` until they run out or the episode ends. Returns the SHA-256 over every observation the
    container sent (`SERVED`; each emitted one is its `view`), each action and the done flag, step by step, with the
    number of steps played. `watch` is called with the episode after the reset and after every step."""
    ep = Episode(seed)
    try:
        h = hashlib.sha256(_line({"t": 0, "observation": ep.nle}))
        watch(ep)
        for action in actions:
            if ep.done:
                break
            ep.step(action)
            h.update(_line({"t": ep.t, "action": action, "observation": ep.nle, "done": ep.done}))
            watch(ep)
        return h.hexdigest(), ep.t
    finally:
        ep.close()
