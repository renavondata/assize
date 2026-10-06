# STATUS — L1 — 2026-10-06 — 6ef8006 — PR #15
VERDICT: SESSION DONE
LAYER BOUNDARY: no (per A1.3's definition: no root REPORT.md verdict; opens no layer's brief)
pins: clean 16/16; mutants 30/30 KILLED; twins 30/30; leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0
changed: judge/{__init__.py,runtime.py,config.toml,README.md}; harness/pins.py (P2); harness/edits/P2_*.toml (4); harness/{proposer.toml,README.md}; Makefile; reports/L1/{forecasts.jsonl,make-pins.txt,p2/,ci/,measure-*.txt,STATUS.md}
did: brief 1 §2 first item: judge/runtime.py builds the one candidate command line (--network=none, --read-only, caps dropped, no-new-privileges, no mounts, cpu/memory/pids limits from judge/config.toml) for Docker or rootless Podman, each admitted only on its own report
did: P2 probes inside the container under every usable runtime: judge paths ENOENT, IPv4/IPv6 TCP/UDP ENETUNREACH, loopback only, root EROFS, cgroup limits = config; mutants network_enabled, judge_mounted, rootfs_writable, memory_limit_dropped each KILLED with a passing twin (reports/L1/p2/*.log)
did: Docker witness: pins CI run 37525906600 on 6ef8006: success; Docker 28.0.4 and rootless Podman 4.9.3 both witnessed, 0 leaked (reports/L1/p2/ci-clean-37525906600.log). Host witness: measure run 37525910249 on 6ef8006, rootless Podman 6.1.2, P2 4/4 KILLED, 0 leaked (reports/L1/measure-37525910249.txt, p2/host-clean-37525910249.log)
did: the PR's first pins run, 37523381746 at 7bbadbf, failed: every P2 run LEAKED 1 process on ubuntu-latest; reproduced as rootless Podman's pause process (catatonit -P) reparented to the harness subreaper; fixed by starting it in `make pins` before the harness (6ef8006); witness reports/L1/p2/ci-leak.txt, ci/37523381746.json
did: make pins at 6ef8006 on steel-legend, 20:14:31Z–20:21:41Z, PINS PASSED (reports/L1/make-pins.txt); also passed at 7bbadbf (19:54:25Z–20:01:34Z)
decided (not asked): P2 runs under every usable runtime and fails if none is usable; Podman's Docker emulation is not Docker, and a rootless Podman without cpu/memory/pids delegated is not usable. Which runtime each context witnessed is named in its transcript — p(stands on review)=0.7
decided (not asked): Podman's per-user pause process is runtime infrastructure like dockerd, so `make pins` starts it outside the harness rather than the sweep exempting it; any process a container leaves is still counted — p=0.65
decided (not asked): P2 also pins the read-only root and the configured cgroup limits (§2 isolation), each with its own mutant — p=0.85
decided (not asked): candidate base image python:3.11-slim by index digest 0dd364ba…; limits 1 CPU, 1024 MiB (swap 0), 64 pids, committed before any scored run — p=0.75
decided (not asked): Podman gets --read-only-tmpfs=false so both runtimes give one root with no writable tmpfs; a candidate has no scratch disk — p=0.7
forecasts: made 4; resolved 0 this session; ledger L0+L1: 42 claims, 27 resolved; cumulative log-loss 6.118 vs base rate 18.715 (0.5) over 27
obligations added: none
NEEDS YOU (at most 1): none
next: brief 1 §2 continued: the judge process and JSON-RPC stdio loop over runtime.run_argv, with per-step and per-episode timeouts in judge/config.toml, termination codes (P3) and container teardown (P10); add judge-private storage to P2's probed paths when it exists
