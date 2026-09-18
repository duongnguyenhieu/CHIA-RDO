# Phase 6 Model Correlation

For K={2,4,8,16,35} and P={1,2,4,8}, RTL measured `4*ceil(K/P)` cycles with zero error against the current serialized-wrapper model. The expanded regression evaluated 66,576 candidates with zero functional, winner, duplicate, dropped, cycle, or interface failures.

This zero error is scoped to fixed-K P-way datapath measurements. Policy-level cycle values are trace-weighted replay of those measured points, not an independent integrated policy-controller RTL measurement. Vivado correlation is unavailable.
