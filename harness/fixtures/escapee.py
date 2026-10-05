"""fixture.escapee (brief 0 A3 item 2): a check whose grandchild escapes both kill paths for a while.

The grandchild starts in a new session with NO parent-death signal, so neither the timeout's process-group
kill nor the death signal reaches it. Its working directory is the run's scratch root, so the parent sees the
root held past reap_grace_s and must record the run LEAKED. It sleeps escape_hold_s and exits on its own,
so the fixture leaves nothing behind. Its PID is recorded in the run directory, outside the scratch root.
"""

from __future__ import annotations

import subprocess
import sys
import time

from harness import config, context
from harness.fixtures.toy import OFF_BY_ONE
from harness.pin import ROOT, Pin

FAST = ROOT / "harness" / "fixtures" / "fast.toml"
MARKER = "assize-escapee"
PID_FILE = "escapee.pid"
SLEEPER = "import sys, time; time.sleep(float(sys.argv[1]))"


def check_escapee() -> bool:
    hold = config.load(FAST).escape_hold_s
    grandchild = subprocess.Popen([sys.executable, "-c", SLEEPER, str(hold), MARKER], cwd=context.scratch,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    (context.run_dir / PID_FILE).write_text(str(grandchild.pid))
    while True:
        time.sleep(1)


PINS = [Pin("fixture/escapee", "its grandchild escapes and holds the scratch root (seeded defect)",
            check_escapee, (OFF_BY_ONE,))]
