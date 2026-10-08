L1–L2 — reference incumbents (random agent at L1, AutoAscend at L2).

`random/` (brief 1 section 4): the random incumbent, a candidate image. `agent.py` speaks the judge's JSON-RPC over stdio, plays an action drawn uniformly from `legal_actions` by the OS CSPRNG (`random.SystemRandom`; it holds no seed), and predicts the predictive floor: each declared target's add-one unigram frequencies over its own observations of the episode so far, the current one included, reset at every `begin_episode`. `Containerfile` copies it onto the judge's candidate base image, pinned by the digest in `judge/config.toml`; nothing is installed, so it builds with no network:

    podman build --network=none --pull=false -f incumbents/random/Containerfile incumbents/random   # or docker build

The judge runs the resulting image id with no command. P14 (`harness/pins.py`) builds it under every usable runtime, plays two 100-step Crafter episodes in one container through the judge's loop, and requires the recorded log-loss to equal the floor derived from the episodes' own observations, and the 200 actions not refused as uniform by Pearson's chi-square at 1e-6. Mutants: `first_legal_action`, `floor_unsmoothed`, `seen_not_reset`.
