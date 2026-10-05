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
from collections.abc import Callable

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
