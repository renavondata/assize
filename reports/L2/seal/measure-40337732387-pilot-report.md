VERDICT: FIT
proposer: {"kind": "builder", "model": "claude-opus-5-5", "session": "95480223-ce68-40b9-8786-3b70a9bdb7da"}
world crafter; runtime podman; image sha256:c2f6e943291fc913e35e92bdbb77980a2c3b7b9890c5ce1be0ba7fb701386984; judge_sha256 4a6ad9bc51a6be1a9b5a3f188d91b1edd690e14f19846db6d71b15ed6a507321; pilot_sha256 eea08d35c21bab22b0f057bc5665496774a7dbbfb75fa6ad405ef84b96752745
episodes: 200 recorded of 200 requested (cap 7200 s); terminations {'terminal': 200}
utility over 200 episodes: mean 2.315, min 0, max 6; counts {'0': 8, '1': 70, '2': 24, '3': 59, '4': 29, '5': 8, '6': 2}
Hafner score (reported beside the utility, never as it): 1.6203178978117152
throughput: 0.6941032295460777 episodes/s over 288.1 s wall-clock, 20 requests
compute per episode over 200: cpu_s mean 0.10693765499999999, wall_s mean 0.5501418975769775, peak_memory_bytes max 22786048, price mean 4.823376604408747e-05
predictive floor, per declared target: log-loss per scored step (scored, missing, infinite); mean entropy
  health: 0.7523433082007556 (34541, 0, 0); 0.7659028822741639
  food: 1.9901950268172872 (34541, 0, 0); 1.5963750815992952
  drink: 2.1287647264091563 (34541, 0, 0); 1.7217748887711821
  energy: 0.9646018112575668 (34541, 0, 0); 1.158480766981119
  wood: 0.3420234849957565 (34541, 0, 0); 0.7431070696732852
  stone: 0.18068361832302435 (34541, 0, 0); 0.6767197103677263
time-to-learn. Assumption: a candidate's per-episode utility is distributed as the incumbent's shifted by delta achievements per episode. Note: a random agent's variance is a weak proxy for that of a competent agent.
  expected reading (the committed one, which gives the verdict): mean posterior mass on the correct sign reaches the mass; assurance reading: that fraction of experiments reach it
  verdict under the assurance reading, shown beside the committed one: FIT
  each reading is a Monte Carlo mean, not monotone in episodes per arm, shown with its standard error at m*, at m* - 1 and at the budget; a delta's detection is settled only if the reading at the budget is more than one standard error from the mass on the side of the detection
  delta | episodes per arm | measure (se) | at m*-1 (se) | at budget (se) | wall-clock s (both arms) | assured episodes per arm | assured fraction (se) | at m*-1 (se) | at budget (se) | assured wall-clock s
  0.25 | 182 | 0.905307 (0.004647454096662019) | 0.89698 (0.0048777501008196444) | 1.0 (0.0) | 524.417672336786 | 356 | 0.902 (0.009406619184621245) | 0.895 (0.00969892102602496) | 1.0 (0.0) | 1025.7840184170102
  0.5 | 46 | 0.9069919999999999 (0.004490800510513156) | 0.89881 (0.004927154833649411) | 1.0 (0.0) | 132.54512597523166 | 97 | 0.904 (0.009320454434783257) | 0.899 (0.009533618929341046) | 1.0 (0.0) | 279.49733086081454
  1.0 | 10 | 0.9043329999999999 (0.004928297497841139) | 0.8779199999999999 (0.00568081307888556) | 1.0 (0.0) | 28.814157820702533 | 23 | 0.909 (0.009099549538400337) | 0.897 (0.009616833339695739) | 1.0 (0.0) | 66.27256298761583
