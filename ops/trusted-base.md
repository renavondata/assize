# Trusted base (instruction #113 Part C; Audit criterion 7)

One row per thing outside every loop: what starts or authorises it, the price quantity it lowers (A1.5, Amendment 4
rule 6: `guy-items`, `guy-latency`, `sessions`, `runner-min`), and the pin that fails without it. Names and scopes only,
never values.

`python -m harness.claims trusted-base` reads `.github/workflows/`, `.claude/commands/` and this table at the checkout and
prints each entry of the kinds `workflow`, `command`, `secret`, `runner` and `scope` that no row lists, and each such row
with nothing behind it; it exits non-zero if either set, or a row naming neither price and pin nor `REMOVE`, exists. P0av
runs it on the real tree, so deleting a trigger, command, secret, runner or scope leaves a ghost row and fails `pins`, and
adding one without a row fails `pins`: that is the pin each row below names where no pin of its own reads the entry.

The kinds `grant` and `sovereign` are listed but no file states them as an entry (P0ap reads the grant itself). A `sovereign` row is an act CLAUDE.md
reserves to Guy; a pull request cannot remove it, so its pin cell says so rather than naming a pin that does not exist.

An entry that cannot name both a price quantity and a pin is marked `REMOVE`, with the removal an item in the next Builder
session. At this commit no row is.

| entry | what starts or authorises it | price quantity it lowers | pin that fails without it |
|---|---|---|---|
| `workflow:build.yml:push` | a push to master starts a Builder on master | guy-latency | P0av (ghost_row_admitted) |
| `workflow:build.yml:pull_request_target:labeled` | a `blocked` label (Builder on the PR) or an `awaits-guy` label (Builder on master), applied by any account | guy-items | P0aj (awaits_guy_clause_removed); P0ao (build_pull_request_restored, review_pull_request_restored) |
| `workflow:build.yml:issues:labeled` | the `instruction` label on an issue starts a Builder on master | guy-latency | P0av (ghost_row_admitted) |
| `workflow:build.yml:workflow_dispatch` | Guy's dispatch, the acknowledgement of a stop (`ASSIZE_ACK`), optionally on a PR | guy-latency | P0av (ghost_row_admitted) |
| `workflow:review.yml:pull_request_target:labeled` | a `needs-review` or `awaits-guy` label starts a review or the Vizier | guy-latency | P0v (reviewer_label_excluded); P0ao (build_pull_request_restored, review_pull_request_restored) |
| `workflow:review.yml:push` | a push to master touching `REPORT.md` starts the Vizier and the Auditor | guy-items | P0av (ghost_row_admitted) |
| `workflow:review.yml:issues:labeled` | a `failed-run` or `wish` label starts the Vizier and, for `failed-run`, the Auditor | guy-latency | P0av (ghost_row_admitted) |
| `workflow:review.yml:issues:assigned` | an issue assigned to gfrmin starts the Vizier | guy-latency | P0av (ghost_row_admitted) |
| `workflow:review.yml:schedule` | cron `0 5 * * *`, daily: the Vizier | guy-latency | P0av (ghost_row_admitted) |
| `workflow:review.yml:workflow_dispatch` | Guy's dispatch: a review when `pr` is set, the Auditor at master when it is empty | guy-items | P0au (dispatch_always_review) |
| `workflow:failed.yml:workflow_run:completed` | a `build`, `review` or `pins` run that ended failed, cancelled or timed out opens an issue assigned to Guy | guy-latency | P0z (pins_failure_unrouted) |
| `workflow:failed.yml:push` | a push to master labels each conflicted open pull request `blocked`, or files it to Guy from the third round (instruction #126) | guy-latency | P0aq (conflict_as_clean) |
| `workflow:pins.yml:pull_request` | every pull request head runs `make pins` and the self-run on `ubuntu-latest` | guy-items | P0as (selfrun_step_skipped) |
| `workflow:measure.yml:workflow_dispatch` | Guy's dispatch of the host measurement | guy-items | P0av (ghost_row_admitted) |
| `workflow:measure.yml:pull_request:labeled` | the `measure` label on a PR starts the host measurement | guy-items | P0av (ghost_row_admitted) |
| `workflow:stale.yml:schedule` | cron `0 6 * * *`, daily: the stuck-PR sweep | guy-latency | P0av (ghost_row_admitted) |
| `workflow:stale.yml:workflow_dispatch` | Guy's dispatch of the sweep | guy-latency | P0av (ghost_row_admitted) |
| `command:build` | `claude -p /build` from `build.yml`, on the builder account | sessions | P0av (ghost_row_admitted) |
| `command:review` | `claude -p "/review <pr>"` from `review.yml`, on the reviewer account | sessions | P0av (ghost_row_admitted) |
| `command:audit` | `claude -p /audit` from `review.yml` (push, `failed-run`, a dispatch with no `pr`) | sessions | P0au (dispatch_always_review) |
| `command:vizier` | `claude -p /vizier` from `review.yml` | sessions | P0av (ghost_row_admitted) |
| `secret:ASSIZE_BUILDER_TOKEN` | repository secret, `GH_TOKEN` of `build.yml`; the builder account's fine-grained token: Actions read and write, Commit statuses read, Contents read and write, Metadata read, Pull requests read and write (CLAUDE.md A1.2) | guy-items | P0av (ghost_row_admitted) |
| `secret:ASSIZE_REVIEWER_TOKEN` | repository secret, `GH_TOKEN` of `review.yml`; the reviewer account's fine-grained token: Actions read, Commit statuses read, Contents read and write, Metadata read, Pull requests read and write (CLAUDE.md A1.2) | guy-items | P0av (ghost_row_admitted) |
| `secret:CLAUDE_CODE_OAUTH_TOKEN` | repository secret, the model credential of both session workflows; model calls only | sessions | P0av (ghost_row_admitted) |
| `runner:self-hosted,agent` | the agent runner, registered by Guy, labelled `agent`; runs `build.yml` and `review.yml` | runner-min | P0av (ghost_row_admitted) |
| `runner:self-hosted,measure` | the measurement host's runner, registered by Guy, labelled `measure`; runs `measure.yml` | runner-min | P0av (ghost_row_admitted) |
| `runner:ubuntu-latest` | GitHub-hosted; runs `pins.yml`, `failed.yml`, `stale.yml` | runner-min | P0av (ghost_row_admitted) |
| `scope:pins.yml:contents:read` | job token, `pins.yml` | guy-items | P0av (ghost_row_admitted) |
| `scope:pins.yml:issues:read` | job token, `pins.yml` (P0m reads instruction issues) | guy-items | P0av (ghost_row_admitted) |
| `scope:pins.yml:pull-requests:read` | job token, `pins.yml` (P0r reads pull requests) | guy-items | P0av (ghost_row_admitted) |
| `scope:pins.yml:actions:read` | job token, `pins.yml` (P0r and `harness base` read pins runs) | runner-min | P0av (ghost_row_admitted) |
| `scope:failed.yml:issues:write` | job token, `failed.yml` (files the issue) | guy-latency | P0z (pins_failure_unrouted) |
| `scope:failed.yml:actions:read` | job token, `failed.yml` (reads the dead run's jobs and log) | guy-latency | P0z (pins_failure_unrouted) |
| `scope:failed.yml:pull-requests:read` | job token, `failed.yml` (the conflicts job lists open pull requests and their `mergeable`) | guy-latency | P0aq (conflict_as_clean) |
| `scope:stale.yml:issues:write` | job token, `stale.yml` (files and closes the sweep issue) | guy-latency | P0av (ghost_row_admitted) |
| `scope:stale.yml:pull-requests:read` | job token, `stale.yml` (lists stuck pull requests) | guy-latency | P0av (ghost_row_admitted) |
| `scope:measure.yml:contents:read` | job token, `measure.yml` | guy-items | P0av (ghost_row_admitted) |
| `grant:allowedTools` | the `--allowedTools` argument of each `claude` call in `build.yml` and `review.yml`: `Bash(gh:*)`, `Bash(make:*)`, `Bash(podman:*)`; `permissions.allow` in `.claude/settings.json` is ignored on both runners (untrusted workspace) | sessions | P0ap (grant_undeclared) |
| `grant:master-hooks` | `git checkout origin/master -- .claude scripts/bootstrap.sh` before each session, so hooks, commands and settings are master's | sessions | P0ap (pr_hook_runs) |
| `sovereign:instruction-label` | the `instruction` label applied by gfrmin, the signature the Builder verifies through the issue timeline (Amendment 3, Amendment 4 rule 5) | guy-items | none: reserved to Guy by CLAUDE.md; P0m reads the signature but cannot witness its absence |
| `sovereign:entrenched-approval` | Guy's approval and merge of a pull request touching an entrenched path or a layer boundary (A1.1, A1.3), enforced by `CODEOWNERS` | guy-items | none: reserved to Guy by CLAUDE.md; branch protection is a repository setting no pin reads |
| `sovereign:settings-and-runners` | repository settings, branch protection, runner registration, secrets, `CLAUDE.md` (CLAUDE.md, first paragraph) | guy-items | none: reserved to Guy by CLAUDE.md; outside the repository |
