VERDICT: FIT
proposer: {"kind": "builder", "model": "claude-opus-5-5", "session": "95480223-ce68-40b9-8786-3b70a9bdb7da"}
world crafter; runtime podman; image sha256:4ae7df19a747a8d7d8b7c697d9efc7f2ef4864737dd87d9ed6829931b9d7ebcb; judge_sha256 28710725463f36b93123771ddcda4390e3b02f4ee15488b42834809929eda7ff
episodes: 200 recorded of 200 requested (cap 7200 s); terminations {'terminal': 200}
utility over 200 episodes: mean 2.285, min 0, max 5; counts {'0': 4, '1': 67, '2': 28, '3': 72, '4': 27, '5': 2}
Hafner score (reported beside the utility, never as it): 1.4700191637769526
throughput: 0.7197369313958408 episodes/s over 277.9 s wall-clock, 20 requests
compute per episode over 200: cpu_s mean 0.102662185, wall_s mean 0.5297045212849661, peak_memory_bytes max 23957504, price mean 4.6213153270308086e-05
predictive floor, per declared target: log-loss per scored step (scored, missing, infinite); mean entropy
  health: 0.8065727163863242 (35064, 0, 0); 0.797662424014823
  food: 1.9873826377178179 (35064, 0, 0); 1.5969860837877774
  drink: 2.1202285227456867 (35064, 0, 0); 1.7126998247249055
  energy: 0.9468308739283392 (35064, 0, 0); 1.1475643052248943
  wood: 0.29817171482963595 (35064, 0, 0); 0.715235413818434
  stone: 0.17901708795052773 (35064, 0, 0); 0.6722914074312838
time-to-learn. Assumption: a candidate's per-episode utility is distributed as the incumbent's shifted by delta achievements per episode. Note: a random agent's variance is a weak proxy for that of a competent agent.
  delta | episodes per arm | measure | wall-clock s (both arms)
  0.25 | 145 | 0.9059349999999999 | 402.92499571695015
  0.5 | 33 | 0.903826 | 91.70017143903003
  1.0 | 9 | 0.9183389999999999 | 25.009137665190007
