#!/usr/bin/env bash
# Reproduces every brief 0 A2 witness in this directory. Run from the repository root.
set -uo pipefail
W=reports/L0/a2
REPO=$(pwd)
PY="uv run --frozen python"
stamp() { echo "# $(date -u +%Y-%m-%dT%H:%M:%SZ) $(uname -srm) commit=$(git rev-parse --short HEAD) dirty=$(git status --porcelain -- harness Makefile pyproject.toml uv.lock scripts .github .python-version docs | wc -l)"; }
digest() { find harness -type f -not -path '*/__pycache__/*' -print0 | sort -z | xargs -0 sha256sum | sha256sum | cut -c1-16; }

rm -rf "$W/pins" "$W/fixtures" "$W/review" "$W"/*.txt
mkdir -p "$W"

# W1. make pins: every pin's clean run; every mutant run with its causal twin.
{ stamp; echo '$ make pins PINS_OUT=reports/L0/a2/pins'; make pins PINS_OUT=$W/pins 2>&1; echo "[exit $?]"; } > "$W/make-pins.txt"

# W2. STALE and NON-CAUSAL fixtures, run directly.
{
  stamp
  for r in fixture.stale fixture.noncausal; do
    echo "## $r"
    echo "\$ $PY -m harness run --registry $r --phase all --out $W/fixtures/$r"
    $PY -m harness run --registry $r --phase all --out $W/fixtures/$r 2>&1; echo "[exit $?]"
    echo
  done
} > "$W/fixtures.txt"

# W3. The four unregistered review mutants: the whole suite in a disposable copy carrying each; must go red.
{
  stamp
  echo "harness/ digest of the invocation tree before: $(digest)"
  for f in exit2_as_pass inconclusive_omitted applied_to_original_tree clean_failures_ignored; do
    echo
    echo "## $f"
    sed 's/^/    /' "$W/review-mutants/$f.toml"
    echo "\$ $PY -m harness run --under-edits $W/review-mutants/$f.toml --out $W/review/$f"
    $PY -m harness run --under-edits $W/review-mutants/$f.toml --out $W/review/$f 2>&1; echo "[exit $?]"
  done
  echo
  echo "harness/ digest of the invocation tree after:  $(digest)"
} > "$W/review-mutants.txt"

# W4. Withdrawal: the previous design (5f7372a) replayed with an inert flag that selects no code path.
OLD=$(mktemp -d)
git archive 5f7372a harness | tar -x -C "$OLD"
{
  stamp
  echo "previous design: git archive 5f7372a harness -> <tmp>; python $($PY -c 'import sys;print(sys.version.split()[0])')"
  echo "Each pin's check is run once with ASSIZE_""MUTANT=<pin>/inert, a flag that selects no code path."
  echo "A pin that fails under it would have failed under its registered flag whatever that flag's code did:"
  echo "its kill was not caused by the mutant (NON-CAUSAL)."
  for p in P0 P0b P0c P0d P0e; do
    echo
    echo "## $p with ASSIZE_""MUTANT=$p/inert"
    out=$(cd "$OLD" && env "ASSIZE_""MUTANT=$p/inert" ASSIZE_RUN_DIR="$OLD/runs/$p" \
      "$REPO/.venv/bin/python" -m harness check --registry harness --pin "$p" --mutant inert 2>&1); rc=$?
    echo "$out" | grep -E '\[(ok|FAIL)\]|result:|LEAK'
    echo "[exit $rc]"
  done
} > "$W/withdrawal.txt"
rm -rf "$OLD"
