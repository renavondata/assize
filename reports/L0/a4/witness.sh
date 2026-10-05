#!/usr/bin/env bash
# Reproduces the L0 Addendum A4 witnesses (brief 0 A3). Run from the repository root.
# Hygiene (A3 rule): top-level transcripts and pins.jsonl uncompressed; per-child and nested transcripts packed
# into one reproducible tar.xz per run; SHA-256 and sizes in MANIFEST.txt.
set -uo pipefail
W=reports/L0/a4
RAW=out/a4-witness                      # gitignored
PY="uv run --frozen python"
stamp() { echo "# $(date -u +%Y-%m-%dT%H:%M:%SZ) $(uname -srm) commit=$(git rev-parse --short HEAD) dirty=$(git status --porcelain -- harness Makefile pyproject.toml uv.lock scripts .github .python-version docs | wc -l)"; }
markers() { local n=0; for p in /proc/[0-9]*; do c=$(tr '\0' ' ' 2>/dev/null < $p/cmdline) || continue
              case "$c" in *"-c "*assize-*) n=$((n+1));; esac; done; echo "$n"; }
leftovers() { echo "leftovers: /tmp/assize-* dirs=$(find /tmp -maxdepth 1 -name 'assize-*' | wc -l); harness processes=$(pgrep -fc 'harness (run|check)'); marker processes (assize-* grandchildren/daemons)=$(markers)"; }
pack() {  # pack <dir-containing-runs-or-files> <name> <subpath>
  local arc="$W/$2-runs.tar.xz"
  tar --sort=name --mtime=@0 --owner=0 --group=0 --numeric-owner -C "$1" -cf - "$3" | xz -9e -T1 > "$arc"
  echo "$(sha256sum "$arc" | cut -d' ' -f1)  $(stat -c %s "$arc")  $(xz -dc "$arc" | wc -c)  $(xz -dc "$arc" | tar -tf - | grep -vc '/$')  $arc" >> "$W/MANIFEST.txt"
}
rm -rf "$RAW" "$W"/*.txt "$W"/*.jsonl "$W"/*.tar.xz
mkdir -p "$RAW"
echo "# sha256  compressed_bytes  uncompressed_tar_bytes  files  archive" > "$W/MANIFEST.txt"

# W1. make pins: every pin clean; every mutant (incl. P0h/leaked_not_counted) with its twin.
{ stamp; leftovers; echo "\$ make pins PINS_OUT=$RAW/pins"; make pins PINS_OUT=$RAW/pins 2>&1; echo "[exit $?]"; leftovers; } > "$W/make-pins.txt"
cp "$RAW/pins/pins.jsonl" "$W/make-pins.jsonl"; pack "$RAW/pins" make-pins runs

# W2. fixture.escapee run directly under the fast config; then wait for the grandchild and check leftovers.
{
  stamp; leftovers
  echo "\$ $PY -m harness run --registry fixture.escapee --phase clean --config harness/fixtures/fast.toml --out $RAW/escapee"
  $PY -m harness run --registry fixture.escapee --phase clean --config harness/fixtures/fast.toml --out "$RAW/escapee" 2>&1
  echo "[exit $?]"
  pid=$(cat "$RAW"/escapee/runs/fixture__escapee/clean/escapee.pid)
  echo "escapee grandchild $pid alive right after the run: $(tr '\0' ' ' 2>/dev/null < /proc/$pid/cmdline | grep -q assize-escapee && echo yes || echo no)"
  for _ in $(seq 1 300); do tr '\0' ' ' 2>/dev/null < /proc/$pid/cmdline | grep -q assize-escapee || break; sleep 0.05; done
  echo "escapee grandchild $pid alive after waiting for it to exit on its own: $(tr '\0' ' ' 2>/dev/null < /proc/$pid/cmdline | grep -q assize-escapee && echo yes || echo no)"
  echo "scratch root recorded: $(grep -o '"scratch": "[^"]*"' "$RAW/escapee/pins.jsonl" | cut -d'"' -f4) exists now: $([ -e "$(grep -o '"scratch": "[^"]*"' "$RAW/escapee/pins.jsonl" | cut -d'"' -f4)" ] && echo yes || echo no)"
  leftovers
} > "$W/escapee-fixture.txt"
cp "$RAW/escapee/pins.jsonl" "$W/escapee-fixture.jsonl"; pack "$RAW/escapee" escapee-fixture runs

# W3. Probes R1 (47af530 and HEAD) and N6 (HEAD), on disposable copies.
{ stamp; leftovers; "$W/probes.sh" "$RAW/probes" 2>&1; echo "[exit $?]"; leftovers; } > "$W/probes.txt"
for d in r1-47af530 r1-head n6-head; do cp "$RAW/probes/$d/pins.jsonl" "$W/probe-$d.jsonl"; done
pack "$RAW/probes" probes .
