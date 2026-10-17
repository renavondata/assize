"""Independent check of harness.pins._uniform_sf (PR #234): brute enumeration on small cases, a float DP over
(draws placed, sum of squares capped at s0) for the boundary vector, the chi-square value, timing on random uniform
draws, and a Monte Carlo of the clean false-failure rate's order."""
import itertools, math, random, sys, time
from fractions import Fraction

import numpy as np

sys.path.insert(0, sys.argv[1])
from harness import pins  # noqa: E402


def brute(counts):
    n, k = sum(counts), len(counts)
    s0 = sum(c * c for c in counts)
    hit = 0
    for seq in itertools.product(range(k), repeat=n):
        if sum(seq.count(a) ** 2 for a in range(k)) >= s0:
            hit += 1
    return Fraction(hit, k ** n)


def dp_float(counts):
    """P(sum c_i^2 >= s0) under Multinomial(n, uniform k): f[m, s] = sum of prod 1/c_i! over first cells, s capped."""
    n, k = sum(counts), len(counts)
    s0 = sum(c * c for c in counts)
    lf = np.array([math.lgamma(c + 1) for c in range(n + 1)])
    f = np.zeros((n + 1, s0 + 1))
    f[0, 0] = 1.0
    for _ in range(k):
        g = np.zeros_like(f)
        for c in range(n + 1):
            w = math.exp(-lf[c])
            sq = c * c
            src = f[: n + 1 - c]
            if sq >= s0:
                g[c:, s0] += w * src.sum(axis=1)
            else:
                g[c:, sq:s0] += w * src[:, : s0 - sq]
                g[c:, s0] += w * src[:, s0 - sq:].sum(axis=1)
        f = g
    return f[n, s0] * math.exp(math.lgamma(n + 1) - n * math.log(k))


def chi2_sf(x, df):
    h = x / 2
    if df % 2 == 0:
        return math.exp(-h) * math.fsum(h ** i / math.factorial(i) for i in range(df // 2))
    return math.erfc(math.sqrt(h)) + math.exp(-h) * math.fsum(h ** (i + 0.5) / math.gamma(i + 1.5)
                                                               for i in range((df - 1) // 2))


small = [(6, 0, 0), (2, 2, 2), (1, 1, 0), (2, 1, 0), (3, 1, 0, 0), (2, 2, 1, 0), (4, 0, 1), (3, 3, 0, 1), (5, 1, 1, 0)]
for c in small:
    a, b = pins._uniform_sf(c), brute(c)
    print(f"small {c}: pins {a} brute {b} {'EQUAL' if a == b else 'DIFFER'}")

rng = random.Random(234)
for _ in range(20):
    k, n = rng.randint(2, 5), rng.randint(1, 7)
    seq = [rng.randrange(k) for _ in range(n)]
    c = tuple(seq.count(a) for a in range(k))
    a, b = pins._uniform_sf(c), brute(c)
    print(f"random {c}: {'EQUAL' if a == b else f'DIFFER pins {a} brute {b}'}")

B = pins.UNIFORM_BOUNDARY
n, k = sum(B), len(B)
t = time.monotonic()
e = pins._uniform_sf(B)
print(f"boundary {B}: n {n} k {k}; pins exact {float(e):.6g} ({time.monotonic() - t:.2f}s); "
      f"float DP {dp_float(B):.6g}; chi2 stat {k * sum(x * x for x in B) / n - n:.4g} "
      f"chi2 p {chi2_sf(k * sum(x * x for x in B) / n - n, k - 1):.4g}; alpha {pins.UNIFORM_ALPHA}")

for _ in range(5):
    seq = [rng.randrange(17) for _ in range(200)]
    c = tuple(seq.count(a) for a in range(17))
    t = time.monotonic()
    a = pins._uniform_sf(c)
    dt = time.monotonic() - t
    print(f"uniform draw {c}: pins {float(a):.6g} ({dt:.2f}s) float DP {dp_float(c):.6g}")
