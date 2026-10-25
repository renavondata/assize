"""fixture.parcrash (brief 2, Wish #134, P-par): a check that kills the worker running it.

Run under a parallel configuration, the worker of each of this pin's tasks dies before it records any row, so the
orchestrator must record those tasks itself. Under any other parent (a serial orchestrator) the check refuses to kill
and fails, so the fixture can never take a serial run down with it. The toy pin beside it runs normally.
"""

from __future__ import annotations

import os
import signal
import time

from harness import proc
from harness.fixtures.toy import OFF_BY_ONE, toy_pin
from harness.pin import ALWAYS, Mutant, Pin

WORKER = "harness\0task\0"


def check_kills_worker() -> bool:
    worker = os.getppid()
    if not proc.alive(worker, WORKER):
        print(f"parent {worker} is not a worker (`python -m harness task`); not killed")
        return False
    os.kill(worker, signal.SIGKILL)
    time.sleep(5)  # the worker's death signal ends this process first
    return True


PINS = [
    Pin("fixture/par_crash", "a check that kills its worker", check_kills_worker,
        (Mutant("lost", OFF_BY_ONE.edits),), ALWAYS),
    toy_pin(OFF_BY_ONE),
]
