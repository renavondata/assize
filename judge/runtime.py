"""OCI runtime abstraction for candidate containers (brief 1 section 2, A1 item 2).

A candidate runs under Docker in the cloud and under rootless Podman on the host, with the same isolation either way:
no network, a read-only root, no mount of any host path, all capabilities dropped, no privilege gain, and CPU, memory
and process limits from `config.toml`. The command line is built here and nowhere else, so the isolation a pin
witnesses is the isolation the judge uses. An engine is admitted only on its own report of what it is: Podman's Docker
emulation is not Docker, and rootful Podman is refused (brief 1 refusal list)."""

from __future__ import annotations

import subprocess
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

CONFIG = Path(__file__).with_name("config.toml")
# The cgroup controllers a candidate's limits need; a rootless Podman without them delegated cannot enforce them.
CONTROLLERS = frozenset({"cpu", "memory", "pids"})


@dataclass(frozen=True)
class Limits:
    cpus: float
    memory_mib: int
    pids: int


@dataclass(frozen=True)
class Runtime:
    name: str
    binary: str


@dataclass(frozen=True)
class Engine:
    """What a runtime reports itself to be: `usable` with its identity, or not, with the reason."""

    runtime: Runtime
    usable: bool
    identity: str


RUNTIMES = (Runtime("docker", "docker"), Runtime("podman", "podman"))


def candidate_config(path: Path = CONFIG) -> dict:
    return tomllib.loads(path.read_text())["candidate"]


def limits(path: Path = CONFIG) -> Limits:
    c = candidate_config(path)
    return Limits(float(c["cpus"]), int(c["memory_mib"]), int(c["pids"]))


def _ask(argv: Sequence[str]) -> tuple[int, str]:
    try:
        out = subprocess.run(argv, capture_output=True, text=True)
    except FileNotFoundError:
        return 127, f"{argv[0]}: not found"
    return out.returncode, (out.stdout if out.returncode == 0 else out.stderr).strip()


def _docker(rt: Runtime) -> Engine:
    code, version = _ask([rt.binary, "--version"])
    if code or not version.startswith("Docker version"):
        return Engine(rt, False, f"not a Docker engine: {version[:120]!r}")
    code, server = _ask([rt.binary, "info", "--format", "{{.ServerVersion}} cgroup v{{.CgroupVersion}}"])
    return Engine(rt, code == 0, f"docker server {server}" if code == 0 else f"no Docker server: {server[:120]!r}")


def _podman(rt: Runtime) -> Engine:
    code, info = _ask([rt.binary, "info", "--format", "{{.Version.Version}} {{.Host.Security.Rootless}} "
                       "cgroup {{.Host.CgroupsVersion}} {{.Host.CgroupManager}} {{.Host.CgroupControllers}}"])
    if code:
        return Engine(rt, False, f"no Podman: {info[:120]!r}")
    version, rootless, *rest = info.split()
    controllers = set(info[info.index("[") + 1:info.rindex("]")].split()) if "[" in info else set()
    identity = f"podman {version} rootless={rootless} {' '.join(rest)}"
    if rootless != "true":
        return Engine(rt, False, f"{identity}: rootful Podman is refused")
    missing = sorted(CONTROLLERS - controllers)
    return Engine(rt, not missing, identity + (f": cgroup controllers {missing} not delegated" if missing else ""))


def engine(rt: Runtime) -> Engine:
    return {"docker": _docker, "podman": _podman}[rt.name](rt)


def pull(rt: Runtime, image: str) -> None:
    """Make `image` present locally; containers then run with `--pull=never`."""
    if subprocess.run([rt.binary, "image", "inspect", image], capture_output=True).returncode:
        subprocess.run([rt.binary, "pull", "-q", image], check=True, capture_output=True)


def run_argv(rt: Runtime, image: str, lim: Limits, name: str, command: Sequence[str]) -> list[str]:
    """The command line that runs `command` in a fresh candidate container of `image` named `name`, attached to stdio."""
    isolation = [
        "--network=none",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        f"--cpus={lim.cpus}",
        f"--memory={lim.memory_mib}m",
        f"--memory-swap={lim.memory_mib}m",
        f"--pids-limit={lim.pids}",
    ]
    # Podman mounts writable tmpfs on /tmp, /var/tmp and /run under --read-only unless told not to; Docker does not.
    uniform = ["--read-only-tmpfs=false"] if rt.name == "podman" else []
    return [rt.binary, "run", "--rm", "-i", "--pull=never", f"--name={name}", *isolation, *uniform, image, *command]
