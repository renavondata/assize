"""Probe (review of PR #79 @ b2a173f): instruction #64 item 1 says `elect` uses "the importance-weighted loss estimate
(observed loss / probability of the draw). Unobserved entrants get an estimate of zero." This compares the head's
`ledger.election` (gain form: (1 - clip/B)/p for the drawn entrant, 0 gain for the rest) with EXP3 run on that loss
estimate (l/p for the drawn entrant, 0 loss for the rest), same gamma, same clip, same fixture as P0u."""
import math, sys
sys.path.insert(0, sys.argv[1])
from harness import ledger, pins

rows, ent, B = list(pins.ELECTION_FIXTURE), pins.ELECTION_ENTRANTS, pins.ELECTION_BOUND
got = ledger.election(rows, "review", ent, B)
hist = ledger.plays(rows, "review")
k = len(ent)
gamma = ledger.exploration(k, len(hist) + ledger.ELECTION_HORIZON)

def probs(L):  # EXP3 on losses: p = (1-gamma) w + gamma/K, w ∝ exp(-gamma Lhat / (K B))
    lo = min(L.values()); raw = {m: math.exp(-gamma / k * (v - lo) / B) for m, v in L.items()}
    return {m: (1 - gamma) * r / sum(raw.values()) + gamma / k for m, r in raw.items()}

L = {m: 0.0 for m in ent}
for model, loss in hist:
    if model in L:
        c = min(max(loss, 0.0), B)
        L[model] += c / probs(L)[model]
want = probs(L)
print("gamma", gamma, "rounds", got.rounds, "observed", got.observed, "unknown", got.unknown, "clipped", got.clipped)
print("head (gain-form estimate):     ", {m: round(v, 6) for m, v in got.probs.items()})
print("instruction (loss/p, 0 else):  ", {m: round(v, 6) for m, v in want.items()})
print("max |diff|", max(abs(got.probs[m] - want[m]) for m in ent))
# the entrant with zero observed loss: under the instruction's estimator it can only gain weight; under the head's it
# loses weight to entrants that were merely drawn, because each draw adds 1/p of gain regardless of loss.
one = [{"id": "a", "claim": "x", "p": 0.999999, "proposer": {"kind": "reviewer", "model": "m-a"}},
       {"id": "a", "outcome": True}]
print("one near-perfect m-a round, head:", {m: round(v, 6) for m, v in ledger.election(one, "review", ent, B).probs.items()})
