#!/usr/bin/env bash
# Record measurement-host facts. Every probe is recorded with its exit status; none is dropped.
# Brief 1 A4 item 8: a measurement whose facts lack load averages, the runner's cpuset, the runner version or the
# podman runtime line is not a measurement, so this script exits non-zero if any of those four probes fails.
# It records the checked-out head sha as a fact too (obligation 43), so a verifier can bind the artefact to a head.
# It also refuses unless both the user slice and the measuring process's own cgroup have a non-empty cpuset.cpus (obligation 42).
# It records a stable host id (brief 2 A4 item 4), so measurements are compared only between artefacts of one host.
# CPUSET_FILE, RUNNER_DIR, SELF_CGROUP_DIR and MACHINE_ID_FILE say where to read four of them; they default to the
# paths the brief names and the system's machine-id.
set -uo pipefail
out="${1:?usage: host_facts.sh OUT_DIR [CPUSET_FILE] [RUNNER_DIR] [SELF_CGROUP_DIR] [MACHINE_ID_FILE]}"
cpuset_file="${2:-/sys/fs/cgroup/user.slice/user-$(id -u).slice/cpuset.cpus.effective}"
runner_dir="${3:-$HOME/actions-runner}"
# The cgroup directory the measuring process itself runs in (R 70d26b83818e F2); default from /proc/self/cgroup.
self_cgroup_dir="${4:-/sys/fs/cgroup$(sed -n 's/^0:://p' /proc/self/cgroup)}"
machine_id_file="${5:-/etc/machine-id}"
mkdir -p "$out"
facts="$out/facts.txt"
: > "$facts"
missing=()
probe() {
  local name="$1"; shift
  local status
  {
    echo "### $name"
    echo "\$ $*"
    if command -v "$1" >/dev/null 2>&1; then
      "$@" 2>&1
      status=$?
      echo "[exit $status]"
    else
      status=127
      echo "ABSENT: $1 not found on PATH"
    fi
    echo
  } >> "$facts"
  return "$status"
}
# A required probe that fails is named in `missing`.
require() {
  probe "$@" || missing+=("$1")
}
# The runner version, from the runner's registration file or its config script; either suffices.
runner_version() {
  local found=1
  if [ -r "$1/.runner" ]; then cat "$1/.runner" && echo && found=0; fi
  if [ -x "$1/config.sh" ]; then "$1/config.sh" --version && found=0; fi
  [ "$found" -eq 0 ] || echo "neither $1/.runner nor $1/config.sh is readable"
  return "$found"
}
# A cgroup is pinned only if its own cpuset.cpus is non-empty: cpuset.cpus.effective shows the parent's full set on an
# unpinned child (R 70d26b83818e F1). Both are recorded side by side; an empty or unreadable own set fails.
pinned_cpus() {
  local own effective
  own=$(cat "$1/cpuset.cpus") || return 1
  effective=$(cat "$1/cpuset.cpus.effective" 2>&1)
  echo "$1 cpuset.cpus=[$own] cpuset.cpus.effective=[$effective]"
  [ -n "$own" ]
}
# The host id is the SHA-256 of the machine-id, which is stable across boots; the raw machine-id, which systemd asks be
# kept confidential, is never written. A missing or empty machine-id fails.
host_id() {
  local id
  id=$(tr -d '[:space:]' < "$1") || return 1
  [ -n "$id" ] || { echo "$1 is empty"; return 1; }
  printf '%s' "$id" | sha256sum | cut -d' ' -f1
}
probe date date -u +%Y-%m-%dT%H:%M:%SZ
probe whoami whoami
probe lscpu lscpu
probe free free -h
probe uname uname -a
probe uv uv --version
probe python3 python3 --version
probe docker docker --version
probe podman podman --version
probe own-cgroup cat /proc/self/cgroup
require uptime uptime
require cpuset cat "$cpuset_file"
require cpuset-slice pinned_cpus "$(dirname "$cpuset_file")"
require cpuset-own pinned_cpus "$self_cgroup_dir"
require runner-version runner_version "$runner_dir"
# The head this artefact measured: a host witness is admissible only if it equals the head the Reviewer reproduced
# (obligation 43, R 7498b94a505b F1; `python -m harness.claims measure-head`).
require head git rev-parse HEAD
# The host this artefact was measured on: no throughput or time-to-learn is compared across two ids, and a second
# measurement host carries its own verdicts (brief 2 A4 item 4; `python -m harness.claims same-host`).
require host-id host_id "$machine_id_file"
require podman-info podman info --format '{{.Host.OCIRuntime.Name}} {{.Host.CgroupsVersion}} {{.Host.CgroupManager}} rootless={{.Host.Security.Rootless}}'
if [ "${#missing[@]}" -gt 0 ]; then
  echo "NOT A MEASUREMENT: required facts missing: ${missing[*]}" >> "$facts"
fi
cat "$facts"
[ "${#missing[@]}" -eq 0 ]
