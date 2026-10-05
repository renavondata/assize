#!/usr/bin/env bash
# Brief 0 A3 probes, each on a disposable copy carrying an injected probe fixture (nothing is added to harness/).
#   R1  reviewer probe 1, reconstructed from F1: a clean check whose detached grandchild (new session, no death
#       signal) holds the run's scratch root past reap_grace_s, while the check itself returns True.
#       Run at 47af530 (before item 1) and at HEAD.
#   N6  reviewer probe 2 = negative witness N6: a clean check that double-forks a daemon (new session, no death
#       signal, cwd /, not holding the scratch root) and returns True. Run at HEAD. The daemon is then killed by
#       its PID file, and shown dead.
# Usage: probes.sh OUTDIR   (raw per-child output; the caller packs it)
set -uo pipefail
OUT=$(realpath -m "$1"); REPO=$(pwd); PY="$REPO/.venv/bin/python"
HOLD=10   # R1 grandchild lifetime, s; > reap_grace_s (5, default config at both revisions) with 5 s margin
mkdir -p "$OUT"

alive() { [ "$(awk '{print $3}' /proc/$1/stat 2>/dev/null)" != Z ] && tr '\0' ' ' 2>/dev/null < /proc/$1/cmdline | grep -q "$2"; }
markers() { local n=0; for p in /proc/[0-9]*; do c=$(tr '\0' ' ' 2>/dev/null < $p/cmdline) || continue
              case "$c" in *"-c "*assize-probe-*) n=$((n+1));; esac; done; echo "$n"; }

prepare() {  # prepare <rev|WORKTREE> <dest> <fixture-python-file>
  local rev="$1" dest="$2" fixture="$3"
  mkdir -p "$dest"
  if [ "$rev" = WORKTREE ]; then git ls-files -z | xargs -0 -I{} cp --parents {} "$dest"/
  else git archive "$rev" . | tar -x -C "$dest"; fi
  cp "$fixture" "$dest/harness/fixtures/probe.py"
  "$PY" - "$dest/harness/registries.py" <<'PYEOF'
import sys
p = sys.argv[1]; s = open(p).read()
assert s.count("REGISTRIES = {\n") == 1
open(p, "w").write(s.replace("REGISTRIES = {\n", 'REGISTRIES = {\n    "probe": "harness.fixtures.probe",\n'))
PYEOF
}

row_summary() {  # row_summary <pins.jsonl>
  "$PY" - "$1" <<'PYEOF'
import json, sys
for line in open(sys.argv[1]):
    r = json.loads(line)
    if r["kind"] == "run":
        print(f"  row: pin={r['pin']} observed={r['observed']} scratch_quiescent={r.get('scratch_quiescent')} "
              f"scratch_removed={r.get('scratch_removed')} verdict={r['verdict']}")
    elif r["kind"] == "summary":
        print(f"  summary: clean_ok={r.get('clean_ok')} clean_failed={r.get('clean_failed')} "
              f"leaked={r.get('leaked', '(field absent at this revision)')} exit_code={r['exit_code']}")
PYEOF
}

TMP=$(mktemp -d)

# ---- R1 fixture
cat > "$TMP/r1.py" <<PYEOF
import subprocess, sys
from harness import context
from harness.fixtures.toy import OFF_BY_ONE
from harness.pin import Pin
def check():
    g = subprocess.Popen([sys.executable, "-c", "import sys, time; time.sleep(float(sys.argv[1]))", "$HOLD",
                          "assize-probe-r1"], cwd=context.scratch, start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    (context.run_dir / "r1.pid").write_text(str(g.pid))
    return True
PINS = [Pin("probe/r1", "returns True; detached grandchild holds the scratch root", check, (OFF_BY_ONE,))]
PYEOF

for rev in 47af530 WORKTREE; do
  label=$([ $rev = WORKTREE ] && echo "HEAD ($(git rev-parse --short HEAD))" || echo $rev)
  name=r1-$([ $rev = WORKTREE ] && echo head || echo $rev)
  echo "## R1 at $label"
  echo "probe markers alive before: $(markers)"
  prepare $rev "$TMP/$name" "$TMP/r1.py"
  (cd "$TMP/$name" && "$PY" -m harness run --registry probe --phase clean --out "$OUT/$name" 2>&1 | sed -E 's# \S*transcript\.log##')
  echo "[exit ${PIPESTATUS[0]}]"
  row_summary "$OUT/$name/pins.jsonl"
  pid=$(cat "$OUT/$name"/runs/probe__r1/clean/r1.pid)
  echo "  grandchild $pid alive right after the run: $(alive $pid assize-probe-r1 && echo yes || echo no)"
  for _ in $(seq 1 $((HOLD * 20))); do alive $pid assize-probe-r1 || break; sleep 0.05; done
  echo "  grandchild $pid alive after waiting up to HOLD=${HOLD}s for it to exit on its own: $(alive $pid assize-probe-r1 && echo yes || echo no)"
  echo "probe markers alive after: $(markers)"
  echo
done

# ---- N6 fixture: double-forked daemon
PIDFILE="$TMP/n6-daemon.pid"
cat > "$TMP/n6.py" <<PYEOF
import os, subprocess, sys, time
from harness.fixtures.toy import OFF_BY_ONE
from harness.pin import Pin
DAEMON = """import os, sys, time
if os.fork():
    os._exit(0)
os.setsid()
if os.fork():
    os._exit(0)
os.chdir("/")
open(sys.argv[1], "w").write(str(os.getpid()))
time.sleep(3600)
"""
def check():
    subprocess.run([sys.executable, "-c", DAEMON, "$PIDFILE", "assize-probe-n6"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    while not os.path.exists("$PIDFILE"):
        time.sleep(0.05)
    return True
PINS = [Pin("probe/n6", "returns True after double-forking a daemon", check, (OFF_BY_ONE,))]
PYEOF

echo "## N6 at HEAD ($(git rev-parse --short HEAD)): double-forked daemon from a clean check"
echo "probe markers alive before: $(markers)"
prepare WORKTREE "$TMP/n6-head" "$TMP/n6.py"
(cd "$TMP/n6-head" && "$PY" -m harness run --registry probe --phase clean --out "$OUT/n6-head" 2>&1 | sed -E 's# \S*transcript\.log##')
echo "[exit ${PIPESTATUS[0]}]"
row_summary "$OUT/n6-head/pins.jsonl"
dpid=$(cat "$PIDFILE")
echo "  daemon pid (from PID file): $dpid"
echo "  daemon alive after the suite finished: $(alive $dpid assize-probe-n6 && echo yes || echo no)"
echo "  daemon: ppid=$(awk '{print $4}' /proc/$dpid/stat 2>/dev/null) sid=$(awk '{print $6}' /proc/$dpid/stat 2>/dev/null) cwd=$(readlink /proc/$dpid/cwd 2>/dev/null)"
echo "\$ kill -9 $dpid   # by PID file"
kill -9 "$dpid"; echo "[exit $?]"
for _ in $(seq 1 40); do alive $dpid assize-probe-n6 || break; sleep 0.05; done
echo "  daemon alive after the probe's kill: $(alive $dpid assize-probe-n6 && echo yes || echo no)"
echo "probe markers alive after: $(markers)"
rm -rf "$TMP"
