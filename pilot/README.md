L1 — pilot and time-to-learn (brief 1 §5). Host only: nothing here is evidence when run in the cloud.

`config.toml` commits, before any scored run, the pilot (200 incumbent episodes of Crafter or 2 hours, whichever binds first; reaching the cap first is a stop-and-report boundary), the assumed shifts δ ∈ {0.25, 0.5, 1}, the posterior mass 0.9, the FIT (δ = 0.5) and MARGINAL (δ = 1) criteria over a one-day budget, and the analysis's Monte Carlo sizes and seed. None is tuned after a score is seen.

`timetolearn.py` takes the pilot's per-episode utilities and its measured throughput (episodes per wall-clock second). Assumption, stated in every report: a candidate is distributed as the incumbent shifted by δ. The incumbent's distribution has the Bayesian-bootstrap posterior over the pilot's utilities; an experiment of m episodes per arm draws a distribution from it, m incumbent and m shifted episodes, and the Bayesian-bootstrap posterior of each arm's mean; the detection measure at m is the posterior mass on candidate mean > incumbent mean, averaged over experiments (the preposterior probability that the favoured sign is right). `table` reports per δ the smallest m reaching 0.9, searched up to the m the budget affords with both arms run, and its wall-clock 2m / throughput; `verdict` reads FIT, MARGINAL or UNFIT off the table. A random agent's variance is a weak proxy for a competent agent's.

    uv run --frozen python -c "from pilot import timetolearn as t; c = t.config()['time_to_learn']; rows = t.table(UTILITIES, THROUGHPUT, c); print(rows, t.verdict(rows, c))"

P15 (`harness/pins.py`) pins it. The pilot run itself waits for `evaluate()` (brief 1 §2) and for the host (`measure.yml`).
