"""fixture.orphaner (L2a obligation 27): a clean check that leaves a daemon and then SIGKILLs the run that spawned it.

The daemon is fixture.daemon's (new session, no parent-death signal, double-forked, cwd `/`), so it is reparented to
the `harness run` orchestrating this check. The check then kills that orchestrator with SIGKILL before its sweep can
run, and dies itself by its parent-death signal. The daemon is reparented again, to the nearest subreaper above: under
`harness run --under-edits`, the outer process, whose own sweep must kill and count it. The daemon's PID and the
killed run's scratch root (which no one is left to delete) are recorded in the run directory.
"""

from __future__ import annotations

import os
import signal
import time

from harness import context
from harness.fixtures import daemon
from harness.fixtures.toy import OFF_BY_ONE
from harness.pin import ALWAYS, Pin

SCRATCH_FILE = "scratch.path"


def check_orphaner() -> bool:
    daemon.check_daemon()
    (context.run_dir / SCRATCH_FILE).write_text(str(context.scratch))
    os.kill(os.getppid(), signal.SIGKILL)
    while True:
        time.sleep(1)


PINS = [Pin("fixture/orphaner", "leaves a daemon, then SIGKILLs its own orchestrator (seeded defect)",
            check_orphaner, (OFF_BY_ONE,), ALWAYS)]
