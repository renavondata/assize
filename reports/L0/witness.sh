#!/usr/bin/env bash
# Reproduces every L0 witness in this directory. Run from the repository root.
set -uo pipefail
W=reports/L0
S="${ACTIONLINT_CONFIG:?set ACTIONLINT_CONFIG to a file declaring the self-hosted label 'measure'}"
stamp() { echo "# $(date -u +%Y-%m-%dT%H:%M:%SZ) $(uname -srm) commit=$(git rev-parse --short HEAD) dirty=$(git status --porcelain -- harness Makefile pyproject.toml uv.lock scripts .github .python-version | wc -l)"; }

rm -rf "$W/pins" "$W/negatives"
{ stamp; echo '$ make pins PINS_OUT=reports/L0/pins'; make pins PINS_OUT=$W/pins 2>&1; echo "[exit $?]"; } > "$W/make-pins.txt"

{
  stamp
  echo '## N1. Seeded mutant P0/checks_always_pass, applied directly to a fixture suite (every check returns success)'
  echo '$ ASSIZE_MUTANT=P0/checks_always_pass uv run --frozen python -m harness run --registry fixture.basic --phase mutants --out reports/L0/negatives/n1'
  ASSIZE_MUTANT=P0/checks_always_pass uv run --frozen python -m harness run --registry fixture.basic --phase mutants --out $W/negatives/n1 2>&1; echo "[exit $?]"
  echo
  echo '## N2. A mutant flag leaked into the top-level clean run of make pins'
  echo '$ ASSIZE_MUTANT=P0b/leak_probe make pins PINS_OUT=reports/L0/negatives/n2'
  ASSIZE_MUTANT=P0b/leak_probe make pins PINS_OUT=$W/negatives/n2 2>&1; echo "[exit $?]"
  echo
  echo '## N3. make measure without ASSIZE_HOST=measure'
  echo '$ make measure'
  env -u ASSIZE_HOST make measure 2>&1; echo "[exit $?]"
  echo
  echo '## N4. make smoke'
  echo '$ make smoke'
  make smoke 2>&1; echo "[exit $?]"
  echo
  echo '## N5. bootstrap idempotence (two consecutive runs)'
  echo '$ scripts/bootstrap.sh; scripts/bootstrap.sh'
  scripts/bootstrap.sh 2>&1; echo "[exit $?]"; scripts/bootstrap.sh 2>&1; echo "[exit $?]"
} > "$W/negatives.txt"

{
  stamp
  echo '$ uvx --from actionlint-py actionlint --version'
  uvx --from actionlint-py actionlint --version 2>&1 | head -1
  echo '$ cat <actionlint config>'; cat "$S"
  echo '$ actionlint -config-file <config> .github/workflows/pins.yml .github/workflows/measure.yml'
  uvx --from actionlint-py actionlint -config-file "$S" .github/workflows/pins.yml .github/workflows/measure.yml 2>&1; echo "[exit $?]"
  echo '$ grep -n -E "runs-on|^on:|types:|if:|ASSIZE_HOST|uses:" .github/workflows/*.yml'
  grep -n -E 'runs-on|^on:|types:|if:|ASSIZE_HOST|uses:' .github/workflows/*.yml
} > "$W/workflow-check.txt"
