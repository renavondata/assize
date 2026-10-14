"""Reviewer probe of P28 at 3b591e2: runs p28_missing_priced against the head and against alternative mutants of
judge.scoring.per_step / beats, monkeypatched in memory (no file edited). Prints one line per variant."""
import contextlib
import io
import math
import sys

sys.path.insert(0, sys.argv[1])
from harness import pins  # noqa: E402
from judge import scoring  # noqa: E402

HEAD_PER_STEP, HEAD_BEATS = scoring.per_step, scoring.beats


def missing_free(row):
    steps = row["scored"] + row["missing"]
    if not steps:
        return None
    return math.inf if row["infinite"] else row["finite_sum"] / steps


def missing_uniform(row):
    steps = row["scored"] + row["missing"]
    if not steps:
        return None
    return math.inf if row["infinite"] else (row["finite_sum"] + row["missing"] * math.log(3)) / steps


def infinite_ignored(row):
    steps = row["scored"] + row["missing"]
    if not steps:
        return None
    return math.inf if row["missing"] else row["finite_sum"] / steps


def beats_le(a, b):
    pa, pb = HEAD_PER_STEP(a), HEAD_PER_STEP(b)
    return pa is not None and pb is not None and pa <= pb


def beats_none_as_zero(a, b):
    pa, pb = HEAD_PER_STEP(a), HEAD_PER_STEP(b)
    return (pa or 0) < (pb or 0)


VARIANTS = {
    "head (clean)": {},
    "missing_free (missing at loss 0, denominator kept)": {"per_step": missing_free},
    "missing_uniform (missing at ln|support|)": {"per_step": missing_uniform},
    "infinite_ignored (scored inf not priced)": {"per_step": infinite_ignored},
    "beats_le (non-strict)": {"beats": beats_le},
    "beats_none_as_zero (empty row compares as 0)": {"beats": beats_none_as_zero},
}

for name, patch in VARIANTS.items():
    scoring.per_step = patch.get("per_step", HEAD_PER_STEP)
    scoring.beats = patch.get("beats", HEAD_BEATS)
    # beats() calls per_step through the module global, so patching per_step reaches it
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            result = pins.p28_missing_priced()
        except Exception as e:  # a probe records the exception as its outcome
            result = f"raised {type(e).__name__}: {e}"
    print(f"{name}: P28 -> {result}  {'KILLED' if result is not True and name != 'head (clean)' else ''}")
