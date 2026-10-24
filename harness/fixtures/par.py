"""fixture.par (brief 2, Wish #134, P-par): pins whose record must not depend on the number of workers.

One slow pin and two fast ones, so a parallel run finishes its tasks out of registry order. Each check leaves a marker
in its scratch root, sleeps, and fails if another run's marker appeared there meanwhile: two runs sharing a scratch
root fail it. Each records its wall-clock interval in its run directory, outside the record, so the pin can see which
runs overlapped.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable

from harness import context
from harness.fixtures.toy import OFF_BY_ONE, add
from harness.pin import ALWAYS, ROOT, Pin

PAR1 = ROOT / "harness" / "fixtures" / "par1.toml"
PAR4 = ROOT / "harness" / "fixtures" / "par4.toml"
MARKER = "par-marker-"
INTERVAL = "interval.json"


def timed(seconds: float) -> Callable[[], bool]:
    def check() -> bool:
        start = time.time()
        marker = context.scratch / f"{MARKER}{os.getpid()}"
        marker.write_text("")
        time.sleep(seconds)
        others = sorted(p.name for p in context.scratch.iterdir() if p.name.startswith(MARKER) and p != marker)
        (context.run_dir / INTERVAL).write_text(json.dumps({"start": start, "end": time.time(), "others": others}))
        print(f"slept {seconds}s; other markers in this scratch root: {others}")
        return add(2, 2) == 4 and not others
    return check


PINS = [
    Pin("fixture/par_slow", "a slow toy pin", timed(2.0), (OFF_BY_ONE,), ALWAYS),
    Pin("fixture/par_a", "a fast toy pin", timed(0.3), (OFF_BY_ONE,), ALWAYS),
    Pin("fixture/par_b", "another fast toy pin", timed(0.3), (OFF_BY_ONE,), ALWAYS),
]
