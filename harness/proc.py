"""Child-process setup and sweeping (brief 1 A4 item 5).

Each child runs in its own session so a timeout can kill its process group;
nested orchestrators start further sessions, which a group kill does not
reach. Tying every process's life to its parent's (Linux PR_SET_PDEATHSIG)
makes a kill cascade down the whole tree. A descendant that escapes both
(new session, no death signal, or double-forked) is reparented to the
orchestrator, a child subreaper (PR_SET_CHILD_SUBREAPER), whose sweep kills
and counts it. Every child Python runs without writing bytecode (`-B`,
PYTHONDONTWRITEBYTECODE=1; brief 1 A5) and reads cached bytecode only under a
fresh PYTHONPYCACHEPREFIX beneath the scratch root, never from an in-tree
`__pycache__` (brief 1 A6).
"""

from __future__ import annotations

import ctypes
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from harness import context

_PR_SET_PDEATHSIG = 1
_PR_SET_CHILD_SUBREAPER = 36
_libc = ctypes.CDLL(None, use_errno=True)


def python(*args: str) -> list[str]:
    """Command line for a child Python: bytecode writing disabled."""
    return [sys.executable, "-B", *args]


def child_env(scratch: Path | None = None) -> dict[str, str]:
    """Environment for a child Python: bytecode writing disabled, and the bytecode cache moved to a fresh directory
    under `scratch` (default: the scratch root this process was given), so an in-tree `__pycache__` is never read."""
    under = scratch or context.scratch
    if under is None:
        raise ValueError("child_env: no scratch root to hold the bytecode cache prefix")
    prefix = tempfile.mkdtemp(prefix="pycache-", dir=under)
    inherited = {k: v for k, v in os.environ.items() if k != "PYTHONPYCACHEPREFIX"}
    return inherited | {"PYTHONDONTWRITEBYTECODE": "1", "PYTHONPYCACHEPREFIX": prefix}


def start_runtime_infrastructure() -> None:
    """Rootless Podman keeps one pause process per user to hold its user namespace, as Docker keeps dockerd. Start it
    before the subreaper is armed, so it is reparented past this process and the sweep never counts it as leaked by
    the first check to use Podman (L2a obligation 23; witness reports/L1/p2/ci-leak.txt). `podman unshare true` is a
    no-op when the process already exists."""
    if shutil.which("podman") is not None:
        subprocess.run(["podman", "unshare", "true"], capture_output=True, timeout=120)


def set_subreaper() -> None:
    """Orphaned descendants of this process are reparented to it, not to init, so its sweep can reach them."""
    if _libc.prctl(_PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "prctl(PR_SET_CHILD_SUBREAPER) failed")


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


def _ppids() -> dict[int, tuple[int, str]]:
    """pid -> (ppid, state) for every process visible in /proc."""
    table = {}
    for d in Path("/proc").iterdir():
        if not d.name.isdigit():
            continue
        try:
            stat = (d / "stat").read_text()
        except OSError:
            continue
        fields = stat[stat.rindex(")") + 2:].split()
        table[int(d.name)] = (int(fields[1]), fields[0])
    return table


def descendants(root: int | None = None) -> dict[int, str]:
    """pid -> state for every descendant of `root` (default: this process), zombies included."""
    root = os.getpid() if root is None else root
    table = _ppids()
    children: dict[int, list[int]] = {}
    for pid, (ppid, _) in table.items():
        children.setdefault(ppid, []).append(pid)
    found, frontier = {}, [root]
    while frontier:
        for c in children.get(frontier.pop(), []):
            if c not in found:
                found[c] = table[c][1]
                frontier.append(c)
    return found


def _live(found: dict[int, str]) -> list[int]:
    return [pid for pid, state in found.items() if state not in "ZX"]


def _reap() -> None:
    """Collect every exited child of this process (reparented orphans included)."""
    while True:
        try:
            pid, _ = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            return
        if pid == 0:
            return


def sweep(grace: float, step: float) -> int:
    """After a child run: wait up to `grace` for every descendant to die on its own, then SIGKILL every one still
    alive, repeating until none remain. Returns the number of distinct processes killed (`leaked_processes`)."""
    def settled() -> bool:
        _reap()
        return not _live(descendants())

    wait_until(settled, grace, step)
    killed: set[int] = set()
    while live := _live(descendants()):
        for pid in live:
            try:
                os.kill(pid, signal.SIGKILL)
                killed.add(pid)
            except ProcessLookupError:
                pass
        time.sleep(step)
        _reap()
    _reap()
    return len(killed)


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
