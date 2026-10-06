#!/usr/bin/env bash
# Record measurement-host facts. Every probe is recorded with its exit status; none is dropped.
set -uo pipefail
out="${1:?usage: host_facts.sh OUT_DIR}"
mkdir -p "$out"
facts="$out/facts.txt"
: > "$facts"
probe() {
  local name="$1"; shift
  {
    echo "### $name"
    echo "\$ $*"
    if command -v "$1" >/dev/null 2>&1; then
      "$@" 2>&1
      echo "[exit $?]"
    else
      echo "ABSENT: $1 not found on PATH"
    fi
    echo
  } >> "$facts"
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
probe podman-rootless podman info --format 'rootless={{.Host.Security.Rootless}}'
cat "$facts"
