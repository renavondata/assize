"""Seeded misbehaviour for P0h: leave a SIGTERM-immune grandchild and a nested copy behind, then hang.

The grandchild is spawned the way the harness spawns its own children (new session, parent-death
signal), so a process-group kill of the hanging child cannot reach it; only the parent-death signal can.
Its PID and the nested copy's path are recorded in the run directory, outside every temporary copy.
"""

from __future__ import annotations

import subprocess
import sys
import time

from harness import config, context, proc
from harness.tree import disposable_copy

MARKER = "assize-p0h-grandchild"
GRANDCHILD = """import os, signal, sys, time
signal.signal(signal.SIGTERM, signal.SIG_IGN)
with open(sys.argv[1], "w") as f:
    f.write(str(os.getpid()))
while True:
    time.sleep(1)
"""
PID_FILE = "grandchild.pid"
COPY_FILE = "nested_copy.path"


def leak_and_hang() -> None:
    pid_file = context.run_dir / PID_FILE
    subprocess.Popen([sys.executable, "-c", GRANDCHILD, str(pid_file), MARKER],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, preexec_fn=proc.setup(True))
    step = config.load().poll_step_s
    while not pid_file.exists():
        time.sleep(step)
    with disposable_copy() as nested:
        (context.run_dir / COPY_FILE).write_text(str(nested))
        while True:
            time.sleep(1)
