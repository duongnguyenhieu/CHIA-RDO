# Phase 6 DSE

- Native CHIA hardware/history records: **114**
- Matched Phase-6 HM policy curves: **11** (132 encode results)
- Successful logical experiments: **107**
- Cancelled unavailable policy labels: **18**
- Extended RTL evaluations: **66,576**, zero failures

The agent screened P, pipeline depth, buffer depth, width, and scheduler labels. Only the validated static P-way architecture has actual RTL evidence; other hardware combinations remain analytical and cannot support implementation claims.

The strongest measured Track-B operating point is `phase6_hw_cycle_v1` at P=8: BD-rate -0.0543%, average K 16.456, RDO reduction 52.98%, winner retention 88.02%, and 10.482 trace-replayed RTL cycles/event. Its independent HM replicate produced identical BD-rate, K distribution, RDO reduction, and winner retention.
