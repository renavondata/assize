"""Child-process setup: a spawned process dies with its parent (Linux PR_SET_PDEATHSIG).

Each child runs in its own session so a timeout can kill its process group;
nested orchestrators start further sessions, which a group kill does not
reach. Tying every process's life to its parent's makes a kill cascade down
the whole tree, so no descendant outlives a timed-out child.
"""

from __future__ import annotations

import ctypes
import os
import signal
import time
from collections.abc import Callable
from pathlib import Path

_PR_SET_PDEATHSIG = 1
_libc = ctypes.CDLL(None, use_errno=True)


def setup(new_session: bool) -> Callable[[], None]:
    parent = os.getpid()

    def _preexec() -> None:
        if new_session:
            os.setsid()
        _libc.prctl(_PR_SET_PDEATHSIG, signal.SIGKILL)
        if os.getppid() != parent:  # the parent died before prctl took effect
            os._exit(1)

    return _preexec


def _state(proc_dir: Path) -> str:
    stat = (proc_dir / "stat").read_text()
    return stat[stat.rindex(")") + 2]


def holders(path: Path) -> list[int]:
    """Live processes, other than this one, whose working directory lies under `path`
    or whose command line names it."""
    p = str(path)
    found = []
    for d in Path("/proc").iterdir():
        if not d.name.isdigit() or int(d.name) == os.getpid():
            continue
        try:
            if _state(d) in "ZX":
                continue
            cwd = os.readlink(d / "cwd")
            cmdline = (d / "cmdline").read_bytes()
        except OSError:
            continue
        if cwd == p or cwd.startswith(p + os.sep) or p.encode() in cmdline:
            found.append(int(d.name))
    return found


def alive(pid: int, marker: str) -> bool:
    """True if `pid` is a live (non-zombie) process whose command line contains `marker`."""
    d = Path("/proc") / str(pid)
    try:
        return _state(d) not in "ZX" and marker.encode() in (d / "cmdline").read_bytes()
    except OSError:
        return False


def wait_until(predicate: Callable[[], bool], timeout: float, step: float) -> bool:
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            return False
        time.sleep(step)
    return True
