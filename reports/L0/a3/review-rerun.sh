#!/usr/bin/env bash
# Re-runs the four A2 review mutants against the current harness (Addendum A3 correction).
# Per-child transcripts are packed per run; the top-level transcript is committed uncompressed.
set -uo pipefail
W=reports/L0/a3
SCRATCH=out/a3-witness/review
PY="uv run --frozen python"
stamp() { echo "# $(date -u +%Y-%m-%dT%H:%M:%SZ) $(uname -srm) commit=$(git rev-parse --short HEAD) dirty=$(git status --porcelain -- harness Makefile pyproject.toml uv.lock scripts .github .python-version docs | wc -l)"; }
digest() { find harness -type f -not -path '*/__pycache__/*' -print0 | sort -z | xargs -0 sha256sum | sha256sum | cut -c1-16; }
leftovers() { echo "temporary directories /tmp/assize-*: $(find /tmp -maxdepth 1 -name 'assize-*' | wc -l); harness processes: $(pgrep -fc 'harness (run|check)')"; }
rm -rf "$SCRATCH" "$W"/review-*.tar.xz "$W/review-mutants.txt"
mkdir -p "$SCRATCH"
{
  stamp; leftovers
  echo "harness/ digest of the invocation tree before: $(digest)"
  for f in exit2_as_pass inconclusive_omitted applied_to_original_tree clean_failures_ignored; do
    echo; echo "## $f"
    echo "\$ $PY -m harness run --under-edits reports/L0/a2/review-mutants/$f.toml --config reports/L0/a2/review-mutants/config.toml --out $SCRATCH/$f"
    $PY -m harness run --under-edits reports/L0/a2/review-mutants/$f.toml --config reports/L0/a2/review-mutants/config.toml --out "$SCRATCH/$f" 2>&1 \
      | grep -E '^UNDER EDITS|^STALE|^registry|^\[|^MUTANT|^CLEAN|^(clean|mutants|twins):|^PINS' | sed -E 's# \S*transcript\.log##'
    echo "[exit ${PIPESTATUS[0]}]"
    tar --sort=name --mtime=@0 --owner=0 --group=0 --numeric-owner -C "$SCRATCH/$f" -cf - . | xz -9e -T1 > "$W/review-$f.tar.xz"
    a="$W/review-$f.tar.xz"
    echo "$(sha256sum "$a" | cut -d' ' -f1)  $(stat -c %s "$a")  $(xz -dc "$a" | wc -c)  $(xz -dc "$a" | tar -tf - | grep -vc '/$')  $a" >> "$W/MANIFEST.txt"
  done
  echo
  echo "harness/ digest of the invocation tree after:  $(digest)"
  leftovers
} > "$W/review-mutants.txt"
