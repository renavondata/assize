# Reviewer transcript — PR #306 at 0effeb65efe4 — session 63e1291d-fda7-4b8c-9aef-53f274b3ec0e

Scratch copy: `git clone` to /tmp/rv306.Jtks/w at 0effeb6 (removed at session end).

## Full suite
`python -m harness run --registry harness --phase all --since 1cd7c62 --since-run 39646656800` in the scratch copy: every
pin it reached was clean and every mutant KILLED, then `timeout 580` ended it (exit 124). CLAUDE.md "Never run a command
expected to exceed 10 minutes" forbids a longer cloud run, so the full suite is read from the Actions API:
- run 39665687395 on 673588d (the last code head): completed success; summary reports/L2/build/l2b-nethack-utility/ci-39665687395-summary.txt:
  clean 96/96; mutants 315/315 killed; twins 315/315; leaked 0.
- run 39674442767 on 0effeb6 (this head, STATUS-only change over 673588d): completed success.
- The first run on d772564 (39661407109) failed: P36 moon_from_clock and character_fixed stale; re-anchored in 673588d (declared in STATUS).

## Targeted reproduction (clean role, scratch copy)
`python -m harness check --registry harness --pin P37 --role clean ...` : result PASS, 14 [ok] lines, none failing
(record = b7afe79e3e42; three SHA-256s equal the committed ones; table-entry and code tamper refused; seed 1 utility 0.0;
seed 3 utility 0.015392269075361172 (Dlvl:2); both episodes end and BALROG reads 'DEATH: starved to death.').
`... --pin P36 --role clean ...` : result PASS, 3 seeds, hashes equal goldens 55ea807e58a374c2, 3c363323144b3c13, 587dba1b18d4bc17.

## Vendored files against upstream (gh api, balrog-ai/BALROG @ b7afe79e3e4265811cfa985ed7c95c4d1a11e3f5)
progress.py 7c267bd2...a8f2 SAME; achievements.json a582cff2...3101 SAME; LICENSE 4e2bcd21...a118 SAME (sha256 of upstream raw vs worlds/nethack/balrog/*).

## Scope
`git diff master...HEAD --name-only` touches no CLAUDE.md, CODEOWNERS, .github, .claude, judge/ or worlds/spec/.
No `Instruction:` trailer on the branch. Not a layer boundary (no REPORT.md verdict line, no new brief).
