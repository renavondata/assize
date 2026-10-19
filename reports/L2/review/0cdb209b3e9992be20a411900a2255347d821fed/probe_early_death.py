"""Review probe for PR #248 (P14, L2a obligation 34): how often does the random incumbent's episode end before the
100-step cut on P14's five seeds, and how often would the five episodes together leave fewer than 275 draws, the least
for which P14's coverage assertion holds at UNIFORM_ALPHA? Plays `worlds.crafter.binding.Episode(seed)` cut to 100
steps with actions drawn by `random.SystemRandom().choice` over the legal set, as the incumbent does, in process, with
no container and no file of the clone changed. Usage: cd <scratch clone> && uv run --frozen python <this file> <runs per seed>
[<scratch clone>]; the clone (the current directory by default) is put on sys.path, since this file lives outside it."""

import math
import os
import random
import sys
from fractions import Fraction

sys.path.insert(0, sys.argv[2] if len(sys.argv) > 2 else os.getcwd())
from worlds.crafter import binding  # noqa: E402

SEEDS, STEPS, RUNS = (1, 2, 3, 4, 5), 100, int(sys.argv[1]) if len(sys.argv) > 1 else 40
NEED, ALPHA, K = 275, 1e-6, len(binding.manifest()["actions"])
choose = random.SystemRandom().choice


def some_cell_empty_sf(n: int, k: int) -> Fraction:
    return sum((-1) ** (j + 1) * math.comb(k, j) * Fraction(k - j, k) ** n for j in range(1, k + 1))


def play(seed: int) -> tuple[int, str]:
    ep = binding.Episode(seed)
    ep._env._length = STEPS
    while not ep.done:
        ep.step(choose(ep.legal_actions))
    return ep.t, ep.termination


least = min(n for n in range(1, 1000) if some_cell_empty_sf(n, K) < ALPHA)
print(f"least draws with P(some action unplayed | uniform over {K}) < {ALPHA}: {least} "
      f"(p at {least}: {float(some_cell_empty_sf(least, K)):.3g}; at {least - 1}: {float(some_cell_empty_sf(least - 1, K)):.3g}; "
      f"at 500: {float(some_cell_empty_sf(500, K)):.3g}; at 300: {float(some_cell_empty_sf(300, K)):.3g})")
lengths = {}
for seed in SEEDS:
    lengths[seed] = [play(seed) for _ in range(RUNS)]
    early = [(t, how) for t, how in lengths[seed] if t < STEPS]
    print(f"seed {seed}: {RUNS} episodes, {len(early)} ended before step {STEPS} ({len(early) / RUNS:.3f}); "
          f"early endings {sorted(early)}; all terminations {sorted(set(h for _, h in lengths[seed]))}")
all_early = sum(1 for seed in SEEDS for t, _ in lengths[seed] if t < STEPS)
print(f"all seeds: {all_early} of {RUNS * len(SEEDS)} episodes ended early ({all_early / (RUNS * len(SEEDS)):.3f})")
totals = [sum(lengths[s][i][0] for s in SEEDS) for i in range(RUNS)]
print(f"five-episode draw totals over {RUNS} aligned runs: min {min(totals)}, max {max(totals)}; "
      f"below {NEED} (coverage cannot give a verdict): {sum(1 for x in totals if x < NEED)} of {RUNS}")
worst = min(t for s in SEEDS for t, _ in lengths[s])
print(f"shortest episode seen: {worst} steps; the committed loss tolerance is {len(SEEDS) * STEPS - NEED} draws, so "
      f"coverage fails only if the five episodes together lose more than that")
