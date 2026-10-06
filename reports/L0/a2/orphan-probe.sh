#!/usr/bin/env bash
# Kill an orchestrator while its hanging child runs; count descendants left alive.
set -u
tree="$1"; py="$2"
out=$(mktemp -d)
(cd "$tree" && exec "$py" -m harness run --registry fixture.inconclusive --phase mutants --out "$out" >/dev/null 2>&1) &
orch=$!
for _ in $(seq 1 100); do pgrep -f "$out/runs/fixture__toy/hangs/mutant" >/dev/null && break; sleep 0.1; done
echo "hanging child running: $(pgrep -fc "$out/runs/fixture__toy/hangs/mutant")"
kill -9 "$orch"; sleep 2
echo "processes left alive 2 s after SIGKILL of the orchestrator: $(pgrep -fc "$out")"
pkill -9 -f "$out"; rm -rf "$out"
