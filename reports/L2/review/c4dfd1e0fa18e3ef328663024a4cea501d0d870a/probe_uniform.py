"""Independent probe of harness.pins._uniform_sf at PR #246 head (review run 39131480590)."""
import itertools
import math
import random
import sys
import time
from fractions import Fraction

sys.path.insert(0, sys.argv[1])
from harness import pins  # noqa: E402


def brute(counts):
    n, k = sum(counts), len(counts)
    s0 = sum(c * c for c in counts)
    hit = sum(1 for seq in itertools.product(range(k), repeat=n)
              if sum(seq.count(a) ** 2 for a in range(k)) >= s0)
    return Fraction(hit, k ** n)


def float_dp(counts):
    """Probability mass over (draws placed, capped sum of squares), multinomial cell by cell."""
    n, k = sum(counts), len(counts)
    s0 = sum(c * c for c in counts)
    dist = {(0, 0): 1.0}
    for j in range(k):
        nxt = {}
        for (m, s), w in dist.items():
            r = n - m
            cells = k - j
            for c in (range(r + 1) if j < k - 1 else [r]):
                pr = math.comb(r, c) * (1 / cells) ** c * (1 - 1 / cells) ** (r - c) if j < k - 1 else 1.0
                key = (m + c, min(s + c * c, s0))
                nxt[key] = nxt.get(key, 0.0) + w * pr
        dist = nxt
    return sum(w for (m, s), w in dist.items() if s >= s0)


rng = random.Random(246)
bad = 0
for _ in range(40):
    k, n = rng.randint(2, 5), rng.randint(1, 7)
    counts = [0] * k
    for _ in range(n):
        counts[rng.randrange(k)] += 1
    if pins._uniform_sf(counts) != brute(counts):
        bad += 1
        print("MISMATCH", counts)
print(f"brute-force agreement: {40 - bad}/40 random vectors (k<=5, n<=7)")

t = time.time()
edge = pins._uniform_sf(pins.UNIFORM_BOUNDARY)
x = 17 * sum(c * c for c in pins.UNIFORM_BOUNDARY) / 200 - 200
h = x / 2
chi2 = math.exp(-h) * math.fsum(h ** i / math.factorial(i) for i in range(8))
print(f"boundary exact {float(edge):.6g} ({time.time() - t:.1f}s); >= alpha {edge >= pins.UNIFORM_ALPHA}; "
      f"chi-square(16) sf at {x:.2f}: {chi2:.4g}, < alpha {chi2 < pins.UNIFORM_ALPHA}")
for i in range(3):
    counts = [0] * 17
    for _ in range(200):
        counts[rng.randrange(17)] += 1
    t = time.time()
    print(f"uniform sample {i}: exact {float(pins._uniform_sf(counts)):.6g} ({time.time() - t:.1f}s)")
# a strongly biased count, the shape `first_legal_action` produces
print("all on one action, k=17 n=200: exact p", float(pins._uniform_sf([200] + [0] * 16)))
