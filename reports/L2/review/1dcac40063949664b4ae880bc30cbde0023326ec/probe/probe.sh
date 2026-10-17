#!/bin/sh
# Review probe for PR #226 (L2a obligation 26). Question: under the seeded mutant P0h/copy_deleted_before_sweep
# (the old order: the disposable copy's rmtree runs before the sweep), how often does the nested fixture.litter run
# end in an exception (no summary row: the mutant is KILLED by p0h_copy_swept_first) and how often does rmtree win
# the race against the writer so that the run finishes with a LEAKED row and a summary (the mutant would SURVIVE)?
# Runs the fixture registry under the mutant's edits, N times, on the scratch clone of the PR head.
cd /tmp/review-226-clone || exit 1
N=${1:-20}
echo "probe start $(date -u +%Y-%m-%dT%H:%M:%SZ) head $(git rev-parse --short HEAD) N=$N"
for i in $(seq 1 "$N"); do
  out=/tmp/review-226-probe/out/$i
  mkdir -p "$out"
  nice -n 19 uv run --frozen python -m harness run --registry fixture.litter --phase mutants --out "$out" \
    --config harness/fixtures/fast.toml --under-edits harness/edits/P0h_copy_deleted_before_sweep.toml \
    > "$out/stdout.log" 2>&1
  code=$?
  summary=$(grep -c '"kind": "summary"' "$out/pins.jsonl" 2>/dev/null || echo 0)
  verdict=$(grep -o '"verdict": "[A-Z-]*"' "$out/pins.jsonl" 2>/dev/null | head -1)
  err=$(grep -m1 -o 'OSError: \[Errno [0-9]*\] [A-Za-z ]*' "$out/stdout.log" || true)
  echo "run $i: exit $code summary_rows $summary $verdict $err"
done
echo "probe end $(date -u +%Y-%m-%dT%H:%M:%SZ); writers still alive: $(pgrep -fc assize-litter || echo 0)"
