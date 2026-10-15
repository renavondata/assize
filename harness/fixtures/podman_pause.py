"""fixture.podman_pause (L2a obligation 23): a clean check that uses rootless Podman and returns True.

Run by a nested orchestrator whose environment names a fresh XDG_RUNTIME_DIR, Podman has no pause process for it. If the
orchestrator started none before arming its subreaper, the check's `podman unshare true` starts it as the check's
descendant, the subreaper adopts it and the sweep counts it as leaked.
"""

from __future__ import annotations

import subprocess

from harness.fixtures.toy import OFF_BY_ONE
from harness.pin import ALWAYS, Pin


def check_podman() -> bool:
    return subprocess.run(["podman", "unshare", "true"], capture_output=True, timeout=120).returncode == 0


PINS = [Pin("fixture/podman_pause", "uses rootless Podman and returns True (seeded defect)",
            check_podman, (OFF_BY_ONE,), ALWAYS)]
