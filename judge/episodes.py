"""The judge's episode loop (brief 1 section 2): JSON-RPC 2.0 over a candidate container's stdio, one message per line.

The judge owns the World. Per step it sends `{t, observation, legal_actions}` and advances the World only on the
candidate's reply. Every episode ends with a termination code (`rpc.schema.json`) and is recorded, whatever happened:
the World's own ending (`terminal`, `truncated`) or a failure of the candidate (`crash`, `step_timeout`,
`episode_timeout`, `invalid_reply`, `illegal_action`), never dropped (P3). After a failure the container is torn down
and the next episode starts in a fresh one, so no episode inherits a broken candidate.

Every completed step's prediction is validated against the manifest before the World advances, and scored against the
observation the World then emits (`scoring.py`): log-loss per declared target, +inf counted and never clipped, a
missing target recorded missing and never imputed. A reply carrying NaN or an infinity is not JSON and is
`invalid_reply`. Beside the log-loss, every record carries `calibration` (brief 1 A4 item 3): per declared target, the
predicted entropies' sum and mean, and a reliability table over the declared support in the `[calibration] bins` bins
of predicted probability that `config.toml` commits.

Teardown force-removes the container by name and then asks the runtime whether anything of that name is left. A
container still listed is an episode with termination `leaked`, counted, never dropped (brief 1 A4 item 5, P10).

Every episode records its compute, measured by the judge from the container's cgroup (`compute.py`, P4), never
self-reported. The container is sampled after every reply and once more when the episode ends. A container's CPU time
is partitioned over its episodes: each is charged from the previous episode's last sample, or from the container's
start, to its own last sample. `wall_s` runs from the episode's start to its last sample attempt; `peak_memory_bytes`
is the container's high-water mark from its start to the episode's last sample. A container that exits (a crash) takes
its cgroup with it, so its last stretch cannot be read: `unmeasured_s` is the wall-clock time from the last sample read
to the episode's end, zero when the last attempt read, and the candidate's CPU in that stretch is at most the configured
CPUs times it. CPU a candidate spends after its last episode's last sample, before removal, is charged to no episode.

Every record carries `price`, its compute in the World's utility at the rates its manifest commits (`price.py`): the
unmeasured stretch is charged at the configured limits, and the peak memory's scope is stated in the record as
`peak_memory_scope`."""

from __future__ import annotations

import json
import os
import selectors
import subprocess
import time
import tomllib
import uuid
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import jsonschema
import referencing

from judge import compute, price, runtime, scoring

SPEC = Path(__file__).resolve().parent.parent / "worlds" / "spec"
SCHEMA_VERSION = "1.0.0"
WORLD_ENDINGS = frozenset({"terminal", "truncated"})
# One token per judge process: every candidate container this process starts is named under it, so that what a
# process may call its own stray is a fact of the name, not of the runtime's whole listing (L2a obligation 25).
RUN = uuid.uuid4().hex[:12]
CANDIDATE_PREFIX = f"assize-candidate-{RUN}-"


@dataclass(frozen=True)
class Timeouts:
    step_s: float
    episode_s: float
    teardown_s: float
    reply_bytes: int


def timeouts(path: Path = runtime.CONFIG) -> Timeouts:
    c = tomllib.loads(path.read_text())["timeouts"]
    return Timeouts(float(c["step_s"]), float(c["episode_s"]), float(c["teardown_s"]), int(c["reply_bytes"]))


def calibration_bins(path: Path = runtime.CONFIG) -> int:
    return int(tomllib.loads(path.read_text())["calibration"]["bins"])


def _validator(definition: str) -> jsonschema.Draft202012Validator:
    schemas = [json.loads(p.read_text()) for p in sorted(SPEC.glob("*.schema.json"))]
    registry = referencing.Registry().with_resources(
        (s["$id"], referencing.Resource.from_contents(s)) for s in schemas)
    rpc = next(s for s in schemas if s["$id"].endswith("/rpc.schema.json"))
    return jsonschema.Draft202012Validator({"$ref": f"{rpc['$id']}#/$defs/{definition}"}, registry=registry)


REPLY = _validator("response")


class Failure(Exception):
    """The candidate failed: `code` is the episode's termination code."""

    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def _not_json(token: str):
    raise ValueError(f"{token} is not a JSON number")


class Container:
    """One candidate container attached to the judge by stdio. Its stderr is discarded: the judge reads nothing
    from the candidate but its replies."""

    def __init__(self, rt: runtime.Runtime, image: str, lim: runtime.Limits, command: Sequence[str] = ()):
        self.rt = rt
        self.name = f"{CANDIDATE_PREFIX}{uuid.uuid4().hex[:16]}"
        self.proc = subprocess.Popen(runtime.run_argv(rt, image, lim, self.name, command), stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
        self._buffer = b""
        self._next_id = 0
        self.cgroup = None
        self.usage, self.measured_at = compute.Sample(0, 0), time.monotonic()

    def measure(self) -> float:
        """Sample the container's cgroup and return when; `usage` and `measured_at` advance only if it was read."""
        now = time.monotonic()
        self.cgroup = self.cgroup or compute.cgroup_of(self.rt, self.name)
        s = compute.sample(self.cgroup) if self.cgroup else None
        if s is not None:
            self.usage, self.measured_at = s, now
        return now

    def _send(self, method: str, params: Mapping) -> int:
        rid, self._next_id = self._next_id, self._next_id + 1
        line = json.dumps({"jsonrpc": "2.0", "id": rid, "method": method, "params": params}).encode() + b"\n"
        try:
            self.proc.stdin.write(line)
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError) as e:
            raise Failure("crash", f"{method}: candidate closed its input ({e})") from e
        return rid

    def _line(self, step_deadline: float, episode_deadline: float, limit: int) -> bytes:
        fd = self.proc.stdout.fileno()
        with selectors.DefaultSelector() as sel:
            sel.register(fd, selectors.EVENT_READ)
            while b"\n" not in self._buffer:
                if len(self._buffer) > limit:
                    raise Failure("invalid_reply", f"reply exceeds {limit} bytes")
                now = time.monotonic()
                deadline = min(step_deadline, episode_deadline)
                if now >= deadline:
                    raise Failure("episode_timeout" if episode_deadline <= step_deadline else "step_timeout",
                                  "no reply before the deadline")
                if not sel.select(deadline - now):
                    continue
                chunk = os.read(fd, 65536)
                if not chunk:
                    raise Failure("crash", f"candidate closed its output (exit {self.proc.poll()})")
                self._buffer += chunk
        line, self._buffer = self._buffer.split(b"\n", 1)
        if len(line) > limit:
            raise Failure("invalid_reply", f"reply exceeds {limit} bytes")
        return line

    def call(self, method: str, params: Mapping, t: Timeouts, episode_deadline: float) -> dict:
        """Send one request and return the result of its one reply, or raise the Failure that ends the episode."""
        rid = self._send(method, params)
        line = self._line(time.monotonic() + t.step_s, episode_deadline, t.reply_bytes)
        try:
            reply = json.loads(line, parse_constant=_not_json)
        except (ValueError, UnicodeDecodeError) as e:
            raise Failure("invalid_reply", f"{method}: not JSON ({e})") from e
        errors = [e.message for e in REPLY.iter_errors(reply)]
        if errors or reply["id"] != rid or "result" not in reply:
            raise Failure("invalid_reply", f"{method}: {errors[:1] or 'wrong id or an error reply'}")
        self.measure()
        return reply["result"]

    def teardown(self, t: Timeouts) -> bool:
        """Force-remove the container and wait for its client; True only if the runtime lists nothing of its name."""
        try:
            subprocess.run(runtime.remove_argv(self.rt, self.name), capture_output=True, timeout=t.teardown_s)
        except subprocess.TimeoutExpired:
            pass
        try:
            self.proc.wait(timeout=t.teardown_s)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
        return not listed(self.rt, self.name)


def _names(rt: runtime.Runtime, *filters: str) -> list[str]:
    out = subprocess.run([rt.binary, "ps", "-a", *(f"--filter={f}" for f in filters), "--format", "{{.Names}}"],
                         capture_output=True, text=True, check=True)
    return out.stdout.split()


def listed(rt: runtime.Runtime, name: str, running: bool = False) -> list[str]:
    """Every container, in any state or only running ones, that the runtime lists under exactly `name`."""
    return [n for n in _names(rt, f"name=^{name}$", *(["status=running"] if running else [])) if n == name]


def listed_prefix(rt: runtime.Runtime, prefix: str) -> list[str]:
    """Every container, in any state, whose name starts with `prefix`."""
    return [n for n in _names(rt, f"name=^{prefix}") if n.startswith(prefix)]


def own_candidates(rt: runtime.Runtime) -> list[str]:
    """Every container, in any state, that this process started: the runtime may list others' under the same engine."""
    return listed_prefix(rt, CANDIDATE_PREFIX)


def _play(c: Container, world, manifest: Mapping, t: Timeouts, losses: list, predicted: list) -> tuple[str, str]:
    """One episode on `world` with `c`; returns its termination code and detail, and appends to `losses` each
    completed step's log-loss per declared target, and to `predicted` its predicted distributions and realised values."""
    deadline = time.monotonic() + t.episode_s
    try:
        c.call("begin_episode", {"schema_version": SCHEMA_VERSION, "manifest": manifest}, t, deadline)
        while not world.done:
            legal = world.legal_actions
            result = c.call("step", {"t": world.t, "observation": world.observation, "legal_actions": legal},
                            t, deadline)
            if result.get("action") not in legal:
                raise Failure("illegal_action", f"t={world.t}: action {result.get('action')!r} not legal")
            prediction = result.get("prediction", {})
            why = scoring.invalid(prediction, manifest["targets"])
            if why:
                raise Failure("invalid_reply", f"t={world.t}: prediction: {why}")
            world.step(result["action"])
            losses.append(scoring.step_losses(prediction, manifest["targets"], world.observation))
            predicted.append(scoring.step_predictions(prediction, manifest["targets"], world.observation))
        c.call("end_episode", {"termination": world.termination, "utility": world.utility}, t, deadline)
        return world.termination, ""
    except Failure as f:
        return f.code, f.detail


def run(rt: runtime.Runtime, image: str, worlds: Iterable, manifest: Mapping, **kw) -> list[dict]:
    """Every record of `played`, in order."""
    return list(played(rt, image, worlds, manifest, **kw))


def played(rt: runtime.Runtime, image: str, worlds: Iterable, manifest: Mapping, *, command: Sequence[str] = (),
           lim: runtime.Limits | None = None, t: Timeouts | None = None) -> Iterator[dict]:
    """Play every World of `worlds` with the candidate `image`, one record per World, in order, each yielded once it
    is final: when the next World is drawn, or after the last container's teardown. A container serves episodes until
    one fails; it is then torn down, and the next episode starts in a fresh container. Any other exit, an exception
    escaping the World, the scoring or the draw of the next World, or the caller closing this generator, tears the open
    container down too before it propagates, and a container still listed then is noted on the exception (brief 2 A2,
    L2a obligation 16)."""
    lim, t = lim or runtime.limits(), t or timeouts()
    rate, bins = price.of(manifest), calibration_bins()
    records: list[dict] = []
    final = 0
    c: Container | None = None
    try:
        for i, world in enumerate(worlds):
            yield from records[final:]
            final = len(records)
            c = c or Container(rt, image, lim, command)
            losses: list[dict] = []
            predicted: list[dict] = []
            start, began = c.usage, time.monotonic()
            code, detail = _play(c, world, manifest, t, losses, predicted)
            ended = c.measure()
            used = {"cpu_s": (c.usage.cpu_usec - start.cpu_usec) / 1e6, "wall_s": ended - began,
                    "peak_memory_bytes": c.usage.peak_bytes, "peak_memory_scope": price.PEAK_SCOPE,
                    "unmeasured_s": ended - c.measured_at}
            charged = price.charge(used, lim, rate)
            if code not in WORLD_ENDINGS:
                if not c.teardown(t):
                    code, detail = "leaked", f"container {c.name} listed after teardown ({detail})"
                c = None
            records.append({"episode": i, "termination": code, "detail": detail, "steps": world.t,
                            "utility": world.utility, "prediction": scoring.summary(losses, manifest["targets"]),
                            "calibration": scoring.calibration(predicted, manifest["targets"], bins),
                            "compute": used, "price": charged})
    except BaseException as e:
        if c is not None and not c.teardown(t):
            e.add_note(f"leaked: container {c.name} listed after teardown")
        raise
    if c is not None and not c.teardown(t):
        records[-1] |= {"termination": "leaked", "detail": f"container {c.name} listed after teardown"}
    yield from records[final:]
