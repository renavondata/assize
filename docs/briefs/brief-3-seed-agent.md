# Claude Code brief 3 — the crude seed agent, judged by the sealed image (DRAFT)

**REPO:** the agent repository, `<Guy to fill>`. Not this one: CLAUDE.md puts L3 in the agent repo, and no agent under evaluation may live in, import from, or write to assize.
**HARDWARE:** the measurement host, as the judge's host facts record it (brief 2 A4 item 4).

Draft of the next layer's brief, written by the Builder as L2's last deliverable (CLAUDE.md A1.10), in the form of briefs 0–2. Adding it is a layer boundary (A1.3); it opens L3 when Guy merges it.

## Precondition
- The root `REPORT.md` records L2 as SEALED (line present since 46ddef7: judge image `sha256:c7856fe2cc22222a9c1af4bde31272acd4e4ae4f60bae605c975e75ed918259c`, `release/seal.toml`; Crafter FIT under it, host run 40337732387).
- The agent repository exists, with its own constitution, branch protection and runner registration. Creating them is Guy's (CLAUDE.md reserves repository settings and runner registration to him); a session does not create them.
- Read first: brief 1, `reports/L1/REPORT.md`, `reports/L2/REPORT.md`, `judge/README.md`, `worlds/spec/`, `worlds/crafter/manifest.json` and `incumbents/random/`. These are read, never imported.

## Context
L3 asks the smallest question the ladder can ask of an agent: does Bayesian conditioning within one episode, over a mixture of programs in a tiny language, beat the random incumbent on decisions and the predictive floor on predictions, on seeds the agent has never seen? The court answers it. The agent never sees the court's code, only its interface; the court never sees the agent's code, only its image digest.

The sealed World is Crafter (CLAUDE.md Amendment 6: the L3 exit gate reads "in the sealed World"). NetHack is carried, not done, and is out of scope here.

## 1. The candidate image
- A candidate image in the shape of `incumbents/random/`: JSON-RPC 2.0 over stdio per `worlds/spec/rpc.schema.json`, one reply `{action, prediction}` per step, built offline on the judge's pinned candidate base image (`judge/config.toml`), run by the judge with `--network=none`, a read-only root and the committed cgroup limits and timeouts.
- The image is registered to its proposer by `python -m judge register` under a credential Guy issues (`python -m judge credential`); the image never names its own proposer.
- World vocabulary (observation names, the 19 semantic tokens, the 17 actions, the declared targets and supports) enters the agent from one committed copy of `worlds/crafter/manifest.json`, checked by SHA-256 against the file at the sealed tree, and from nowhere else.

## 2. The seed language
- A tiny language of programs. Each program denotes, for the current episode's history, (a) a distribution over each declared target at t+1, given the action taken, and (b) an action-value: its expected one-step change in the World's utility, as the manifest's `utility` block defines it, for each legal action.
- The grammar, its primitive set and each primitive's one-line rationale are committed before any scored run, in the plan.
- The prior is a description-length prior under that grammar (weight proportional to 2^−length, normalised over the enumerated programs). The enumeration bound is a resource cap, committed in config before the first scored run and priced by the judge's compute price; it is never tuned after scores are seen.
- The predictive floor (add-one unigram frequencies per target, reset each episode, `incumbents/random/agent.py`'s rule) is itself a program of the language with nonzero prior weight. So the mixture's cumulative log-loss over an episode exceeds the floor's by at most −ln w_floor, the Bayes-mixture regret bound; that bound is the only constant §5 derives from the language.

## 3. Within-episode conditioning
- After each step, every program's weight is multiplied by the probability it gave the realised target values and the weights are renormalised: Bayes' rule, and no other update.
- Predictions are the posterior predictive: the weight-averaged program predictions. They sum to one within the judge's derived bound (`len(support)` machine epsilons) and never put zero mass on a support value while the floor program holds weight.
- Weights reset to the prior at every `begin_episode`. Memory across episodes is out of scope at L3.

## 4. Decision: Thompson sampling (brief 2 A4 item 10)
- At each step the agent draws one program from the current posterior, with randomness from the OS CSPRNG (it holds no seed, like the random incumbent), and takes a legal action maximising that program's action-value; ties are broken uniformly at random.
- That is the agent's one decision rule. No action is chosen by any other path.

## 5. Measurement (on the host only)
- Both arms run on the measurement host in one run, through the sealed image by digest: the seed agent, and the random incumbent rebuilt from `incumbents/random/` at the sealed tree. Each arm gets n = 200 fresh evaluation episodes from `evaluate()` (brief 1's pilot size, the population the L2 verdict was measured on). Evaluation seeds are the held-out seeds: drawn by the judge, never issued before, never seen by the agent.
- Utility per episode is the record's achievement count minus its `price.total`, both in achievements (brief 1: compute is priced in utility).
- Predictions are compared, from the judge's records, per target under the rule of the judge's `scoring.per_step` (a missing step priced at +∞; read, never imported), and in total as the sum over the six declared targets, the log-loss of their product forecast.
- n, the wall-clock cap, the agent's config and its committed grammar are fixed before the first scored run and never changed after it.

## Pre-stated criteria (bind agent and Guy)
- **Beats random** if, under a Bayesian bootstrap over the two arms' per-episode net utilities (brief 1 §5's method), the posterior mass on mean(agent) > mean(random) is at least 0.9, the mass brief 1 fixes.
- **Beats the floor** if the same posterior mass, over per-episode summed log-loss per completed step, on agent < floor is at least 0.9; and no declared target has an infinite total log-loss for the agent.
- **L3 PASSED** only if both hold on the host and every pin below passes; **NOT PASSED** otherwise. Cloud numbers are never evidence.
- Brief 2's time-to-learn verdict is rechecked against the seed agent's variance, the first non-random candidate's (L2 A2's fourth criterion, carried as an L3 obligation in `reports/L2/status/l2a-o41-proxy-note-pinned.md`): the L2 table is recomputed with the agent's per-episode utilities in place of the incumbent's and reported beside it. It decides no L3 verdict.

## Pins (each must demonstrate it can fail; each mutant KILLED with a passing twin)
- **Q1 Bayes only.** On a fixture episode with known program likelihoods, the weights equal the exact posterior. Mutants: `fixed_weights` (no update), `tempered_update` (likelihood raised to a power other than one).
- **Q2 Within-episode reset.** Two fixture episodes in one container: the second starts at the prior. Mutant `weights_carried`.
- **Q3 Floor in the mixture.** A fixture where every program but the floor puts zero mass on the realised value: the agent's loss is finite and within −ln w_floor of the floor's. Mutant `floor_dropped`.
- **Q4 Thompson draw.** Over a fixture posterior, the empirical frequency of each program's draws is not refused as the posterior by Pearson's chi-square at 1e-6 (P14's test). Mutants: `argmax_program` (draws the posterior mode), `prior_draw` (draws from the prior).
- **Q5 One decision path.** A static scan finds exactly one function that returns the step's action. Mutant `second_action_path`.
- **Q6 Vocabulary from the manifest.** A static scan finds no manifest vocabulary token in agent code outside the committed manifest copy, and the copy's SHA-256 equals the sealed tree's. Mutants: `hardcoded_action_name`, `manifest_copy_edited`.
- **Q7 No court code.** A static scan of the image finds no import of, and no file from, `judge`, `worlds`, `harness` or `incumbents`. Mutant `judge_imported`.
- **Q8 Isolation unchanged.** The agent image runs under the sealed judge's container flags with no network; a mutant agent that opens a socket is denied by the OS (P2's errno), not by convention. Mutant `socket_opened`.
- **Q9 Criteria fixed before scores.** The scored run's config, grammar and n carry a commit that precedes the run's first record. Mutant `config_after_scores`.

## Refusal list
- No edit to, import from, or file written in the assize repository. The court is frozen at L2.
- No LLM calls. No neural networks.
- No hand-written game strategy: no fixed action sequence, no rule that maps an observation to an action outside §4.
- No learning across episodes (L4 and above).
- No library learning, no adoption of language changes (L4, L5).
- No config, grammar, n or cap change after the first scored run.

## Stop-and-report boundaries
Stop and report if:
- the sealed image cannot be pulled and verified by digest on the host;
- the agent cannot reply within the judge's committed `step_s` at the committed enumeration bound;
- any criterion or pin would need a change to `judge/`, `worlds/spec/` or `worlds/crafter/` (a stop, never a reason to re-seal);
- the cap is reached before either arm's 200 episodes are recorded;
- any pin cannot be made to fail.

On completion, report:
- the grammar, prior, config and the manifest copy's SHA-256;
- the image digest and its registered proposer;
- both arms' net utilities with episode counts and termination codes (nothing dropped), compute per episode, and the posterior masses of both criteria;
- per-target and summed log-loss for agent and floor;
- the rechecked time-to-learn table;
- pin transcripts showing each kill;
- the verdict: L3 PASSED or NOT PASSED.

## Deliverables
- In the agent repository: the seed language, the agent, its `Containerfile`, its pins, a README with exact run commands, and `REPORT.md` with the verdict.
- A draft of brief 4 (A1.10).

## Carried from assize (not L3 items)
The court's records name obligations "on L3": 300 `OBLIGATION on L3` lines in review and audit files and 72 STATUS `obligations added:` lines naming L3, across 187 files under `reports/` at 46ddef7. Enumerate them with `grep -rhE "OBLIGATION on L3|^obligations added:.*L3" reports/`. They concern the court (pins, harness, workflows, the measurement host), which is frozen once L3 begins (CLAUDE.md: lower layers freeze), so this brief does not build them. They stand as obligations on the court if Guy unfreezes it. The one that concerns a candidate, the time-to-learn recheck, is a criterion above.
