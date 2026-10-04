"""Mutant flags.

`ASSIZE_MUTANT` holds a comma-separated set of active mutant flags, each
`<pin>/<mutant>`. Nested runs take the union with the inherited set, so a
mutant active in an outer run stays active in the harness code it spawns.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

ENV = "ASSIZE_MUTANT"


def active_set(env: Mapping[str, str] | None = None) -> frozenset[str]:
    raw = (os.environ if env is None else env).get(ENV, "")
    return frozenset(f for f in (s.strip() for s in raw.split(",")) if f)


def active(flag: str) -> bool:
    return flag in active_set()


def with_mutants(env: Mapping[str, str], *flags: str) -> dict[str, str]:
    out = dict(env)
    merged = sorted(active_set(env) | set(flags))
    if merged:
        out[ENV] = ",".join(merged)
    else:
        out.pop(ENV, None)
    return out
