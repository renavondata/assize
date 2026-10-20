"""A pin over `stamped.VALUE` read by a grandchild the runner does not launch, for P0bp's single-defence case.

The check starts a Python with no PYTHONPYCACHEPREFIX of its own making, as a mutated module might: the child's cache
prefix cannot stand between the cache and the verdict, so only the disposable copy's exclusion of `__pycache__` does."""

import os
import subprocess
import sys

from harness.fixtures.stamp import SAME_LENGTH
from harness.pin import ALWAYS, ROOT, Pin

READ = "from harness.fixtures import stamped; print(stamped.VALUE)"


def check_stamped_bare() -> bool:
    env = {"PATH": os.environ["PATH"], "PYTHONDONTWRITEBYTECODE": "1"}
    out = subprocess.run([sys.executable, "-B", "-c", READ], cwd=ROOT, env=env, capture_output=True, text=True,
                         timeout=60)
    print(f"bare grandchild in {ROOT}: stdout {out.stdout.strip()!r} stderr {out.stderr.strip()!r}")
    return out.stdout.strip() == "4"


PINS = [Pin("fixture/stamp_bare", "a Python with no cache prefix reads the stamped value 4", check_stamped_bare,
            (SAME_LENGTH,), ALWAYS)]
