# From Adaptive K to Routed RTL: A CHIA Loop for HEVC RDO Co-Design

**Authors:** Nguyen Hieu Duong and Duy Hieu Bui, Vietnam National University,
24020497@vnu.edu.vn

**Artifact:** <https://github.com/duongnguyenhieu/CHIA-RDO>, release `v1.0.0`

## Abstract

HEVC intra coding can evaluate 35 luma prediction modes with full rate-distortion optimization (RDO). Prior work reduces this cost with content-adaptive candidate budgets and relative-SATD screening. We build on those ideas without claiming exact paper reproduction and use CHIA to test independently defined Adaptive-K policies together with FPGA microarchitectures. Candidate count alone is a poor hardware objective: latency is quantized by the number of parallel lanes, while replication changes timing, area, and power. Our loop connects pinned HM-16.20 encodes, a history-aware proposal controller, analytical screening, Verilator regression, Pareto updates, GCP workers, and Vivado implementation. The selected frozen Adaptive-K policy reduced candidate RDO evaluations by 38.21% on a held-out synthetic matrix while retaining 97.91% of Full-RDO winners; its aggregate Y-PSNR BD-rate was -0.026%, which we interpret as no observed aggregate penalty on this limited corpus. Physical feedback exposed a 170-level combinational baseline and later an 80-level serial winner-reduction path. Resource sharing, pipeline separation, a corpus-qualified 31-bit cost, and a balanced reduction tree produced a routed 16-lane design with a derived 68.120 MHz Fmax and 8.134 million candidates/s kernel-throughput proxy. This is 2.128x the routed P1 baseline proxy while remaining below 70% of device resources. The implementation does not close the 200 MHz constraint, and the result is not encoder throughput. The case study shows how a CHIA loop can preserve evidence across software quality, RTL correctness, cloud execution, and physical design, then use failed backend results to drive a concrete microarchitectural revision.

## 1. Motivation and Contributions

HEVC intra mode decision exposes a cross-layer tradeoff. Evaluating fewer modes lowers software RDO work, but an FPGA scheduler with parallelism `P` executes `ceil(K/P)` batches for candidate count `K`. Policies with similar average `K` can therefore have different hardware costs, and adding lanes can reduce batch count while worsening routing or timing. A useful optimization loop must retain coding-quality evidence while distinguishing analytical estimates, RTL measurements, and physical implementation results.

CHIA-RDO makes four contributions:

1. It integrates candidate-policy evaluation, HM quality curves, RTL checking, hardware modeling, and Vivado feedback in one persistent CHIA workflow.
2. It evaluates prior-art-inspired Adaptive-K families under one matched interface, freezes the selected software policy before hardware exploration, and versions later hardware-oriented policies separately.
3. It turns physical failures into architecture changes. A replicated baseline failed to scale; a later P16 serial winner scan became the new bottleneck; a balanced tree removed that path at small area cost.
4. It preserves machine-readable experiment identities, hashes, Pareto history, and cache behavior across local and GCP execution.

### 1.1 Prior-art basis and Adaptive-K evolution

Adaptive candidate pruning is established prior art. Stock HM first ranks all 35 modes with rough mode decision (RMD), keeps a fixed number based on PU size, adds most probable modes (MPMs), and applies expensive RDO to that candidate set. Gwon and Choi instead use relative SATD and a minimum-risk Bayesian classifier to choose a subset of HM's RMD modes [2]. Their abstract reports 31.54% average encoding-time reduction with 0.93% BD-rate loss relative to HM 16.6 under their Intra Main test condition. Those published numbers are context, not a direct comparison with our different corpus and HM version.

The project initially explored adaptive-threshold variants, but no unverified
source is used to claim exact reproduction. Our first independently written
baseline, `adaptive-v0.v1`, uses the relative gap between the two best
signaling-aware rough costs as confidence. Confidence at least 0.088 selects
`K=4`, confidence at least 0.045 selects `K=8`, and lower confidence selects
`K=16`. Our Gwon-Choi-inspired baseline computes
`r_i=(SATD_i-SATD_min)/max(SATD_min,1)`, counts modes below a threshold, bounds
that count, and quantizes it upward to a supported K. Unlike the paper, it has
no Bayesian classifier, does not use `SATD_min/SATD_max` subset risk, and starts
from all 35 modes. Relative SATD controls only the budget, while HM's
signaling-aware rough cost determines candidate order.

CHIA evaluated these policies against Full-RDO, fixed-K, and hardware-aware variants on matched inputs and QPs. `adaptive-v0.v1` was aggressive but lost too many winners; relative SATD preserved more winners but removed less work. A bounded search then selected the project-defined `adaptive-threshold.v1`, which uses normalized best rough cost and the explicit K set `{4,16,35}`. Thus the Adaptive-K concept comes from prior literature, while the exact normalization, thresholds, K levels, evaluation contract, and hardware/software loop reported here are CHIA-RDO definitions. Our contribution is not invention of Adaptive-K, but carrying these alternatives through a composable, evidence-aware co-design loop from encoder metrics to routed RTL.

## 2. CHIA-RDO Loop

### 2.1 Software policy and quality contract

For each of the 35 luma modes, the HM instrumentation computes a stable rough ranking:

```text
rough_cost[m] = SATD[m] + mode_bits[m] * sqrt_lambda
```

The algorithm boundary is therefore explicit:

```text
stock HM: 35-mode RMD -> fixed-size shortlist + MPMs -> RDO
project anchor: 35-mode ranking -> RDO all 35 modes
CHIA-RDO Adaptive-K: 35-mode ranking -> content-dependent K prefix -> RDO
```

The frozen `adaptive-threshold.v1` controller normalizes the minimum rough cost by luma block area and sample range. It selects `K=4` when the normalized value is at most 0.04, `K=16` when it is at most 0.20, and `K=35` otherwise. The policy does not consume `P`, scheduler state, QP, or activity. Hardware-aware alternatives are separate experiment versions rather than modifications to this frozen controller.

The policy was selected on two deterministic synthetic workloads, then evaluated without retuning on three predeclared held-out synthetic families. All matched curves use HM-16.20 revision `22178e370178133438c0339f57b3b3a29f112909`, Main-profile 8-bit 4:2:0 All-Intra coding, four frames, and QP 22/27/32/37.

### 2.2 Agentic execution graph

The core loop is:

```text
history-aware proposal -> analytical screen -> HM/RTL evaluation
-> schema check -> atomic persistence -> Pareto update -> next wave
```

CHIA `ChiaFunction` nodes connect stages through Ray object references and dispatch independent jobs asynchronously. The deterministic proposal controller consumes completed history, excludes existing experiment IDs, rewards configuration novelty and Pareto-boundary exploration, and emits only schema-valid candidates. Dominated results remain in history so later waves do not repeat failed ideas. This is a history-aware agentic search controller; we do not claim that an LLM autonomously designed the RTL.

The exploration grew in three stages. An initial graph screened 72 `(P, depth, buffer, width)` points. A multi-wave search accumulated 114 hardware/history records, 107 successful logical experiments, 11 matched HM curves comprising 132 encodes, and a 10-point Pareto set. The final calibrated graph screened 832 combinations over `P=1..16`, depth 2/3, and cost width 31..56. It produced 16 Pareto points; an intentional replay resolved all 832 candidates from cache with zero new evaluations.

### 2.3 RTL and physical feedback

The checked kernel implements 4x4 8-bit luma prediction for all 35 intra modes, residual formation, integer transform, scalar quantization, inverse reconstruction, SSE distortion, and fixed-point RD cost. Exact HM candidate bit counts are supplied externally; hardware CABAC and context evolution are outside the scope.

The first P-way baseline replicated a large combinational candidate datapath. P1 routed with 36,454 LUTs and a -60.395 ns worst negative slack; P2 routed with 70,817 LUTs and -64.653 ns; P4 required 140,102 synthesized LUTs and failed placement. Timing trace showed up to 175 logic levels dominated by arithmetic and carry chains.

The revised design uses resource-shared serial lanes and separates quantization from dequantization at pipeline depth 3. Corpus tracing observed a maximum RD cost of 1,312,532,898, permitting a 31-bit unsigned cost for this corpus. At P16, a serial winner scan then formed an 80-level critical path. Replacing it with a balanced comparator tree reduced the critical path to 39 levels and moved the bottleneck back inside a candidate lane.

## 3. Evaluation

### 3.1 Coding tradeoff

Table 1 separates four references that could otherwise be confused. “Stock HM” is the standard encoder strategy described above. “Full-RDO anchor” is our modified HM reference that evaluates all 35 luma modes, against which project BD-rate and winner retention are calculated. The Gwon-Choi row reports that paper's HM-16.6 experiment and is not directly comparable. CHIA-RDO discovery results cover two synthetic workloads; held-out results cover three different synthetic families. The small negative held-out BD-rate is not treated as a general quality improvement.

**Table 1: Algorithm comparison with HM and prior work.**

| Method | Candidate rule and evaluation scope | Complexity result | Coding result |
|---|---|---:|---:|
| Stock HM RMD | Fixed N by PU size, then MPM insertion and RDO | Reference strategy | Reference strategy |
| CHIA-RDO Full-RDO anchor | All 35 modes enter RDO | 0% RDO reduction | 100% retention, 0% BD-rate |
| Gwon-Choi paper [2] | Bayesian relative-SATD subset of stock-HM RMD modes; HM 16.6 standard corpus | 31.54% encoding-time reduction, reported in abstract | +0.93% BD-rate, reported in abstract |
| Fixed-K8, discovery corpus | First 8 of 35 rough-ranked modes | 77.14% RDO reduction | 68.05% retention, +3.574% BD-rate |
| `adaptive-v0.v1`, discovery corpus | Confidence gap selects K in 4/8/16 | 66.95% RDO reduction, avg. K 11.568 | 75.67% retention, +2.866% BD-rate |
| CHIA-RDO relative SATD, discovery corpus | Threshold count selects quantized K | 26.79% RDO reduction, avg. K 25.624 | 96.07% retention, +0.528% BD-rate |
| Frozen adaptive threshold, discovery corpus | Normalized rough cost selects K in 4/16/35 | 46.71% RDO reduction, avg. K 18.651 | 90.25% retention, +0.755% BD-rate |
| Frozen adaptive threshold, held-out corpus | Same policy, no retuning | 38.21% RDO reduction, avg. K 21.628 | 97.91% retention, -0.026% BD-rate |
| Hardware-aware Track-B, P8 | Joint quality/cycle objective | 52.98% RDO reduction, avg. K 16.456 | 88.02% retention, -0.054% BD-rate |

The held-out adaptive policy responds strongly to content: it reduced RDO work by 13.30-13.95% on mixed-texture and repetitive families, and by 87.36% on smooth/edge content. Its worst individual run retained 91.00% of Full-RDO winners. The separately versioned Track-B point demonstrates a more aggressive hardware-oriented tradeoff but has lower retention than the frozen policy.

### 3.2 RTL evidence

The final RTL campaigns executed 121,600 vector or candidate checks: 8,960 serial depth-3 vectors, 28,160 width-56 P-way evaluations, 56,320 width-31 evaluations, 17,600 extended-P evaluations, and 10,560 balanced-tree evaluations. All candidate values, order, winners, cycle counts, backpressure behavior, and interface checks passed. This is an execution total, not a unique-stimulus count, because campaigns intentionally replay the same pinned corpus across architectures.

### 3.3 Routed results

Table 2 presents the hardware evolution without relying on project phase names. All rows target a KV260 `xck26-sfvc784-2LV-c` using Vivado 2024.2 and a 5 ns out-of-context constraint. The monolithic design computes one candidate with a large combinational lane and replicates that lane with P. The shared-serial design instead uses a 132-cycle candidate lane, launches P candidates concurrently per batch, and retires a batch in 134 cycles.

**Table 2: RTL microarchitecture and physical-result comparison.**

| Architecture | P | Result | LUT | DSP | WNS | Derived Fmax | Kernel throughput |
|---|---:|---|---:|---:|---:|---:|---:|
| Monolithic combinational | 1 | Routed | 36,454 | 178 | -60.395 ns | 15.292 MHz | 3.823 M/s |
| Monolithic combinational | 2 | Routed | 70,817 | 356 | -64.653 ns | 14.357 MHz | 7.178 M/s |
| Monolithic combinational | 4 | Placement failed | 140,102 | 712 | N/A | N/A | N/A |
| Shared serial, depth 3, 31-bit cost | 8 | Routed | 30,813 | 408 | -9.620 ns | 68.399 MHz | 4.084 M/s |
| Shared serial, P16 serial winner scan | 16 | Routed | 60,232 | 816 | -19.092 ns | 41.508 MHz | 4.956 M/s |
| Shared serial, P16 balanced winner tree | 16 | Routed | 61,207 | 816 | -9.680 ns | 68.120 MHz | 8.134 M/s |

The monolithic architecture scales throughput through cheap four-cycle batches but scales area almost directly with P and rapidly deepens routing-critical combinational cones; P4 cannot be placed. Serial resource sharing reduces per-lane area and raises Fmax, allowing P16 to route, but its 134-cycle batch means that low-P serial designs do not beat the monolithic P1 throughput. At P16, balanced winner reduction is decisive: the selected design improves the kernel-throughput proxy by 2.128x over monolithic P1 and 1.133x over monolithic P2. It uses 52.26% of device LUTs and 65.38% of DSPs. Against our internal 70%-of-device budget, it uses 74.66% of the LUT allowance and 93.47% of the DSP allowance, leaving 57 DSPs. The calibrated CHIA model predicted P16 within 0.14% for LUT, 0.45% for Fmax/throughput, and 0.43% for power.

The balanced tree itself increased LUT count by 1.6% over the P16 serial scan, left DSP count unchanged, improved derived Fmax by 64.1%, and reduced estimated power by 2.1%. Thus the backend trace identified a specific control reduction rather than merely recommending more parallelism.

### 3.4 Distributed reproducibility

Local/GCP parity produced identical bitstream, reconstruction, and trace hashes for a reference encode. Later GCP workers replayed RTL campaigns with zero failures. The final analytical run demonstrated 832/832 cache hits, and post-run Compute Engine queries found no remaining instances, disks, or reserved addresses. Actual billed spend and remaining promotional credit are unavailable and are not replaced by estimates.

## 4. Limitations and Conclusion

The coding study uses small deterministic synthetic All-Intra workloads, not standard natural-video classes. The RTL scope excludes chroma, inter prediction, larger transforms, RDOQ, syntax coding, and hardware CABAC. The 31-bit cost is safe only for the observed corpus, not formally proven for arbitrary inputs. All physical runs are out of context and omit board-level clock and pin constraints. Most importantly, the selected implementation has -9.680 ns WNS and does not close 200 MHz. Its 68.120 MHz value is derived from failed post-route timing, and 2.128x denotes candidate-kernel throughput, not encoder FPS.

Within these limits, CHIA-RDO demonstrates an end-to-end, inspectable co-design loop. It preserved a software quality contract, distributed repeatable experiments, checked a bit-exact RTL kernel, calibrated broad analytical exploration with routed points, and converted physical-design failures into a balanced-tree microarchitecture. The resulting routed design more than doubled the P1 candidate-throughput proxy while satisfying the resource budget. The remaining critical path is now inside forward-transform accumulation, giving the next loop iteration a concrete optimization target.

## References

[1] CHIA, “An Open Framework for Agile and Principled Hardware/Software Co-Design Research,” arXiv:2606.27350, 2026.

[2] D. Gwon and H. Choi, “Relative SATD-based Minimum Risk Bayesian Framework for Fast Intra Decision of HEVC,” KSII Transactions on Internet and Information Systems, vol. 13, no. 1, pp. 385-405, Jan. 2019, doi:10.3837/tiis.2019.01.022.

[3] ITU-T/ISO/IEC, “High Efficiency Video Coding Test Model HM-16.20.”

[4] CHIA-RDO artifact, <https://github.com/duongnguyenhieu/CHIA-RDO>, release `v1.0.0`.

## AI Assistance Acknowledgement

The authors used OpenAI OpenCode to assist with code review, artifact
organization, and manuscript editing. The human authors reviewed the output and
are responsible for the paper's contents, tone, and quality.
