"""fixture.escapee (brief 1 A4 item 5): a check whose grandchild does not cooperate.

The grandchild starts in a new session with NO parent-death signal, ignores SIGTERM and hangs past the child's
timeout, so neither the timeout's process-group kill nor the death signal reaches it. Its working directory is the
run's scratch root. It is reparented to the orchestrator (a child subreaper), whose sweep must kill it and record the
run LEAKED. Its PID is recorded in the run directory, outside the scratch root.
"""

from __future__ import annotations

import subprocess
import time

from harness import context, proc
from harness.fixtures.toy import OFF_BY_ONE
from harness.pin import ROOT, Pin

FAST = ROOT / "harness" / "fixtures" / "fast.toml"
MARKER = "assize-escapee"
PID_FILE = "escapee.pid"
HANGER = "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN)\nwhile True: time.sleep(1)"


def check_escapee() -> bool:
    grandchild = subprocess.Popen(proc.python("-c", HANGER, MARKER), cwd=context.scratch, env=proc.child_env(),
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    (context.run_dir / PID_FILE).write_text(str(grandchild.pid))
    while True:
        time.sleep(1)


PINS = [Pin("fixture/escapee", "its grandchild escapes both kill paths (seeded defect)",
            check_escapee, (OFF_BY_ONE,))]
