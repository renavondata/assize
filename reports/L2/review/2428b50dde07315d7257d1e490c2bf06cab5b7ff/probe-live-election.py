"""Review probe for PR #257 head 2428b50 (P0br): `ledger.elect("audit", ...)` on the live ledger.

Rows are master's forecasts (ledger_rows at the head) plus the draws published on origin's `ledger/draws` branch,
which is what review.yml's `elect audit --publish origin` feeds the election. Nothing is published or written.
Usage: cd <clone at the head> && uv run --frozen python <this file> <clone path>
"""
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from harness import ledger  # noqa: E402

repo = Path(sys.argv[1])
head = "2428b50dde07315d7257d1e490c2bf06cab5b7ff"
models, bound = ledger.entrants_of((repo / ledger.ENTRANTS).read_text(), "audit")
rows = ledger.ledger_rows(repo, head) + ledger.draw_rows(repo, "origin/ledger/draws")
draws = {p: ledger.draws_of(rows, p) for p in ledger.PROCEDURES}
print("entrants audit:", models, "bound", bound)
print("draw rows by procedure:", {p: len(d) for p, d in draws.items()})
for p in ("build", "review"):
    last = max(draws[p], key=lambda d: d["ts"])
    print(f"latest {p} draw: {last['ts']} run {last['run']} drew {last['drawn']}")
print("barred(audit):", sorted(ledger.barred(rows, "audit")))
print("barred(build):", sorted(ledger.barred(rows, "build")), "barred(review):", sorted(ledger.barred(rows, "review")))
seen = {}
for seed in range(0, ledger.DRAWS, 997):
    e = ledger.elect(rows, "audit", models, bound, seed)
    seen[e.model] = seen.get(e.model, 0) + 1
    if seed == 0:
        print("audit election at seed 0:", e.report())
print("audit draws over 66 seeds:", seen)
# The refusal on the live rows: every audit entrant barred when the entrants are exactly the two latest models.
latest = [max(draws[p], key=lambda d: d["ts"])["drawn"] for p in ("build", "review")]
try:
    ledger.elect(rows, "audit", tuple(latest), bound, 0)
    print("refusal with entrants", latest, ": NOT REFUSED")
except ValueError as err:
    print("refusal with entrants", latest, ": refused:", err)
# Other procedures are unconstrained on the live rows.
for p in ("build", "review", "vizier"):
    ms, b = ledger.entrants_of((repo / ledger.ENTRANTS).read_text(), p)
    drawn = {ledger.elect(rows, p, ms, b, s).model for s in range(0, ledger.DRAWS, 997)}
    print(f"{p}: drawn over 66 seeds = {sorted(drawn)} of entrants {ms}")
