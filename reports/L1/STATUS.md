# STATUS — L1 — 2026-10-06 — 8270085 — PR #9
VERDICT: SESSION DONE
LAYER BOUNDARY: no (per A1.3's definition: no root REPORT.md verdict; adds or opens no layer's brief)
pins: clean 10/10; mutants 14/14 KILLED; twins 14/14; leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0
changed: scripts/host_facts.sh; harness/{pins.py,README.md,proposer.toml,edits/P0j_incomplete_facts_accepted.toml}; reports/L1/{forecasts.jsonl,make-pins.txt,measure-37457660562.txt,STATUS.md}
did: brief 1 A4 item 8: host_facts.sh records uptime, the cpuset file, the runner version (.runner or config.sh --version), and the podman info runtime line; it exits non-zero, naming each missing fact, when any of the four fails
did: P0j: runs host_facts.sh against stubbed probes, complete and then lacking each fact in turn; seeded mutant incomplete_facts_accepted KILLED, twin passes
did: make pins at 8270085 on steel-legend (reports/L1/make-pins.txt): PINS PASSED, 2m29s; registry proposer session 76372e0f-…; afterwards no harness process and no /tmp/assize-scratch-* or /tmp/assize-copy-* left
did: first pins CI run 37457653249 on 8270085: success. Host witness (A6 item 2): label `measure` → run 37457660562 on 8270085: failure, by design: NOT A MEASUREMENT: required facts missing: cpuset. The runner (assize-runner, uid 1002) runs in system.slice with controllers `memory pids`; AllowedCPUs is empty on the service and on user-1002.slice; there is no pinned CPU set to record (reports/L1/measure-37457660562.txt)
decided (not asked): missing facts make host_facts.sh, and so `make measure`, exit non-zero before pins run, reading "is not a measurement" as a refusal; facts.txt is still uploaded (if: always()) — p(stands on review)=0.8
decided (not asked): CPUSET_FILE and RUNNER_DIR are optional positional arguments, defaulting to the brief's paths, so P0j runs hermetically; they are not environment switches and P0b does not flag them — p(stands on review)=0.8
decided (not asked): /proc/self/cgroup is also recorded, as an extra and non-required probe, because the brief's user-slice cpuset path is absent when the runner runs as a system service — p(stands on review)=0.85
decided (not asked): host run triggered now, not after A6 item 1, because A4 item 8's facts have landed and A4 §6 wants item 5 witnessed on the host before any pilot; A6 item 1 will need its own host run — p(stands on review)=0.75
decided (not asked): the brief's cpuset path is kept, not replaced by the runner's own cgroup: rootless podman puts candidate containers under user-1002.slice, so the brief's path names the right set once one is pinned; the refusal stands until then — p(stands on review)=0.7
forecasts: made 3; resolved 0 this session; ledger L0+L1: 23 claims, 15 resolved, 8 open; cumulative log-loss 3.329 vs base rate 10.397 (0.5) over 15 (the 2 id-less L0 resolution rows named in A4 7a are not counted)
obligations added: none
NEEDS YOU (at most 1): runner host configuration: pin the measurement CPU set on steel-legend, e.g. `sudo systemctl set-property user-1002.slice AllowedCPUs=<cpus>`, so that /sys/fs/cgroup/user.slice/user-1002.slice/cpuset.cpus.effective exists (brief 1 A4 item 8); then any session re-adds the `measure` label
next: brief 1 A6 item 1 (PYTHONPYCACHEPREFIX + P0i case + unset-prefix mutant); after Guy pins the cpuset, re-run the host witness by the `measure` label (A4 §6: item 5 on the host before any pilot)
