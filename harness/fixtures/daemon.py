"""fixture.daemon (brief 1 A4 item 5): a clean check that double-forks a daemon and returns True.

The daemon starts a new session, has no parent-death signal, changes directory to `/` and does not name the scratch
root, so only the orchestrator's subreaper and sweep can reach it: without the subreaper it is reparented past the
orchestrator and the run looks clean. Its PID is recorded in the run directory.
"""

from __future__ import annotations

import os
import time

from harness import config, context, proc
from harness.fixtures.toy import OFF_BY_ONE
from harness.pin import Pin

MARKER = "assize-daemon"
PID_FILE = "daemon.pid"
SLEEPER = "import time\nwhile True: time.sleep(1)"


def check_daemon() -> bool:
    pid_file = context.run_dir / PID_FILE
    first = os.fork()
    if first == 0:
        try:
            os.setsid()
            if os.fork() != 0:
                os._exit(0)
            os.chdir("/")
            pid_file.write_text(str(os.getpid()))
            devnull = os.open(os.devnull, os.O_RDWR)
            for fd in (0, 1, 2):
                os.dup2(devnull, fd)
            cmd = proc.python("-c", SLEEPER, MARKER)
            os.execve(cmd[0], cmd, proc.child_env())
        finally:
            os._exit(1)
    os.waitpid(first, 0)
    step = config.load().poll_step_s
    while not pid_file.exists():
        time.sleep(step)
    return True


PINS = [Pin("fixture/daemon", "returns True after double-forking a daemon (seeded defect)",
            check_daemon, (OFF_BY_ONE,))]
