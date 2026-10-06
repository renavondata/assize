#!/usr/bin/env bash
# Reproduces the L0 Addendum A3 witnesses. Run from the repository root.
# Hygiene: the top-level transcript and pins.jsonl are committed uncompressed; per-child and nested
# transcripts of each run are packed into one reproducible tar.xz, whose SHA-256 and uncompressed size
# are recorded in MANIFEST.txt (and copied into the report).
set -uo pipefail
W=reports/L0/a3
SCRATCH=out/a3-witness            # gitignored; raw per-child output lives here before packing
PY="uv run --frozen python"
stamp() { echo "# $(date -u +%Y-%m-%dT%H:%M:%SZ) $(uname -srm) commit=$(git rev-parse --short HEAD) dirty=$(git status --porcelain -- harness Makefile pyproject.toml uv.lock scripts .github .python-version docs | wc -l)"; }
leftovers() {
  echo "temporary directories /tmp/assize-*: $(find /tmp -maxdepth 1 -name 'assize-*' | wc -l)"
  echo "live processes carrying the P0h grandchild marker: $(ps -eo args | grep -F 'assize-p0h-grandchild' | grep -vc -e grep -e 'ps -eo')"
}
pack() {  # pack <run-out-dir> <name>
  local src="$1" name="$2" arc="$W/$2-runs.tar.xz"
  tar --sort=name --mtime=@0 --owner=0 --group=0 --numeric-owner -C "$src" -cf - runs | xz -9e -T1 > "$arc"
  local raw files
  raw=$(xz -dc "$arc" | wc -c); files=$(xz -dc "$arc" | tar -tf - | grep -vc '/$')
  echo "$(sha256sum "$arc" | cut -d' ' -f1)  $(stat -c %s "$arc")  $raw  $files  $arc" >> "$W/MANIFEST.txt"
}

rm -rf "$SCRATCH" "$W"/*.txt "$W"/*.jsonl "$W"/*.tar.xz
mkdir -p "$SCRATCH"
echo "# sha256  compressed_bytes  uncompressed_tar_bytes  files  archive" > "$W/MANIFEST.txt"

# W1. make pins: every pin's clean run; every mutant with its causal twin (incl. both P0h mutants).
{ stamp; leftovers; echo "\$ make pins PINS_OUT=$SCRATCH/pins"; make pins PINS_OUT=$SCRATCH/pins 2>&1; echo "[exit $?]"; leftovers; } > "$W/make-pins.txt"
cp "$SCRATCH/pins/pins.jsonl" "$W/make-pins.jsonl"
pack "$SCRATCH/pins" make-pins

# W2. The leaking fixture run directly: INCONCLUSIVE (timeout), then nothing left behind.
{
  stamp; leftovers
  echo "\$ $PY -m harness run --registry fixture.leaks --phase mutants --config harness/fixtures/fast.toml --out $SCRATCH/leaks"
  $PY -m harness run --registry fixture.leaks --phase mutants --config harness/fixtures/fast.toml --out "$SCRATCH/leaks" 2>&1
  echo "[exit $?]"
  d=$(find "$SCRATCH/leaks/runs" -path '*leaks_and_hangs/mutant' -type d)
  echo "grandchild PID recorded: $(cat "$d/grandchild.pid")"
  echo "  alive now: $( [ -d /proc/$(cat "$d/grandchild.pid") ] && grep -q assize-p0h-grandchild /proc/$(cat "$d/grandchild.pid")/cmdline 2>/dev/null && echo yes || echo no)"
  echo "nested copy recorded: $(cat "$d/nested_copy.path")"
  echo "  exists now: $( [ -e "$(cat "$d/nested_copy.path")" ] && echo yes || echo no)"
  leftovers
} > "$W/leaks-fixture.txt"
cp "$SCRATCH/leaks/pins.jsonl" "$W/leaks-fixture.jsonl"
pack "$SCRATCH/leaks" leaks-fixture
