"""Measured compute from cgroup accounting (brief 1 section 2, P4).

A candidate container's CPU time and peak memory are read by the judge from the container's own cgroup, never from
anything the candidate says. The cgroup is the one the runtime created for the container: the judge asks the runtime
for the container's init process and full id, reads that process's cgroup from `/proc`, and keeps the path only up to
the component naming the container's id. A candidate that moves its processes into a child cgroup is therefore still
counted, since a cgroup's `cpu.stat` and `memory.peak` cover its descendants.

`usage_usec` of `cpu.stat` is the container's CPU time since it started; `memory.peak` its high-water mark since it
started. Both are read from cgroup v2 files the kernel keeps; a cgroup that is gone (its container exited) cannot be
read, and the caller records how long the container ran unmeasured instead."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from judge import runtime

CGROUP_ROOT = Path("/sys/fs/cgroup")


@dataclass(frozen=True)
class Sample:
    """A container's CPU time in microseconds and its peak memory in bytes, each since the container started."""

    cpu_usec: int
    peak_bytes: int


def cgroup_of(rt: runtime.Runtime, name: str) -> Path | None:
    """The cgroup the runtime created for the running container `name`, or None if it is not running."""
    out = subprocess.run([rt.binary, "container", "inspect", "--format", "{{.State.Pid}} {{.Id}}", name],
                         capture_output=True, text=True)
    if out.returncode or len(out.stdout.split()) != 2:
        return None
    pid, cid = out.stdout.split()
    try:
        lines = Path(f"/proc/{pid}/cgroup").read_text().splitlines() if pid != "0" else []
    except OSError:
        return None
    parts = next((line.split(":", 2)[2] for line in lines if line.startswith("0::")), "").split("/")
    own = [i for i, part in enumerate(parts) if cid in part]
    return CGROUP_ROOT.joinpath(*parts[1:own[0] + 1]) if own else None


def sample(cgroup: Path) -> Sample | None:
    """The container's CPU time and peak memory now, or None if its cgroup can no longer be read."""
    try:
        stat = dict(line.split() for line in (cgroup / "cpu.stat").read_text().splitlines())
        return Sample(int(stat["usage_usec"]), int((cgroup / "memory.peak").read_text()))
    except (OSError, KeyError, ValueError):
        return None
