# Relative-SATD Policy

This project-owned policy is inspired by:

D. Gwon and H. Choi, “Relative SATD-based Minimum Risk Bayesian Framework for Fast Intra Decision of HEVC,” KSII Transactions on Internet and Information Systems, vol. 13, no. 1, pp. 385-405, Jan. 2019, doi:10.3837/tiis.2019.01.022.

It is not a reproduction of that method. The paper starts from the fixed-size HM RMD candidate set, defines a subset statistic `gamma = SATD_min / SATD_max`, and applies a trained minimum-risk Bayesian classifier with a loss factor. CHIA-RDO starts from all 35 modes, uses the independently defined per-mode distance below, counts threshold-qualified modes, and applies no Bayesian classifier or trained paper parameters.

For the 35 intra luma modes, HM measures absolute SATD `S_i`. The reference is the best absolute SATD:

```text
S_ref = min_i(S_i)
relative_satd_i = (S_i - S_ref) / max(S_ref, 1)
```

The decision counts modes satisfying `relative_satd_i <= tau`, clamps that count to configured minimum and maximum K, then rounds upward to the first supported level in `{2,4,8,16,35}`. `tau`, minimum K, and maximum K are explicit experiment parameters.

Candidate ordering remains HM's stable rough-cost ranking:

```text
rough_cost_i = SATD_i + mode_bits_i * sqrt(lambda)
```

The relative-SATD feature controls only the budget. This deliberately keeps absolute SATD, signaling-aware rough cost, feature normalization, ranking, and the K decision distinct. A relative-SATD-qualified mode is not guaranteed to enter the evaluated prefix if signaling bits move it down the rough-cost ranking; that behavior is part of the measured policy definition rather than an unstated paper claim.
