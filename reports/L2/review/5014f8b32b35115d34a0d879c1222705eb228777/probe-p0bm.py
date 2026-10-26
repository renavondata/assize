"""Probe for the review of PR #358 at 5014f8b: is the trusted-base admission of `measure.yml github.token` necessary for
P0bm to pass at this head? Pure-function probe on `harness.trusted` (no file is edited): the list, the declared set
and the admissions are read from a `git archive` copy of the head, then varied in memory.

Usage: cd <copy> && uv run --frozen python /tmp/rv358-probe-scripts/probe_p0bm.py <copy>
"""
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root))
from harness import trusted  # noqa: E402

listed = trusted.parse((root / trusted.LIST_PATH).read_text())
decl = trusted.declared(root)
admitted = trusted.admissions(root)

ENTRY = "measure.yml github.token"
HEADING = "Admitted by instruction #356"

print("declared tokens:", sorted(decl["token"]))
print("admissions in the briefs:", sorted(admitted))

cases = {
    "as committed (entry + heading)": (listed, admitted),
    "entry removed from trusted_base.toml": (
        {k: ({n: a for n, a in v.items() if n != ENTRY} if k == "token" else v) for k, v in listed.items()}, admitted),
    "heading removed from the brief (entry kept)": (listed, frozenset(h for h in admitted if h != HEADING)),
    "entry and heading both removed (master's list against this head's .github/)": (
        {k: ({n: a for n, a in v.items() if n != ENTRY} if k == "token" else v) for k, v in listed.items()},
        frozenset(h for h in admitted if h != HEADING)),
}
for name, (lst, adm) in cases.items():
    found = trusted.findings(lst, decl, adm)
    print(f"{name}: {'PASS (no findings)' if not found else 'FAIL ' + repr(found)}")
