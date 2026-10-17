"""fixture.litter (L2a obligation 26): a mutant check whose grandchild keeps writing in the disposable copy.

The check's seeded mutant starts a grandchild in a new session with no parent-death signal, ignoring SIGTERM, whose
working directory is the copy the check runs in and which rewrites files under it without pause; the check then
returns False. The grandchild is reparented to the orchestrator, whose sweep must kill it before the copy is removed:
removing the copy first races the writer, and the run ends in an exception instead of a LEAKED row. Its PID is recorded
in the run directory, outside the scratch root, once it has written.
"""

from __future__ import annotations

import subprocess
import time

from harness import config, context, proc
from harness.fixtures.toy import toy_pin
from harness.pin import ROOT, Mutant

MARKER = "assize-litter"
PID_FILE = "litter.pid"
WRITER = """import os, signal, sys
signal.signal(signal.SIGTERM, signal.SIG_IGN)
litter, pid_file, i = os.path.join(os.getcwd(), "litter"), sys.argv[1], 0
while True:
    try:
        os.makedirs(litter, exist_ok=True)
        open(os.path.join(litter, str(i % 64)), "w").close()
    except OSError:
        pass
    if i == 0:
        with open(pid_file, "w") as f:
            f.write(str(os.getpid()))
    i += 1
"""
LITTERS = Mutant("litters_copy", "harness/fixtures/edits/toy_litters_copy.toml")


def litter() -> None:
    pid_file = context.run_dir / PID_FILE
    subprocess.Popen(proc.python("-c", WRITER, str(pid_file), MARKER), cwd=ROOT, env=proc.child_env(),
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    step = config.load().poll_step_s
    while not pid_file.exists():
        time.sleep(step)


PINS = [toy_pin(LITTERS)]
