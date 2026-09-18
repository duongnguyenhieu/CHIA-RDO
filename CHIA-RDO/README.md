# CHIA-RDO

CHIA-RDO is an evidence-preserving CHIA loop for hardware-aware adaptive HEVC
RDO candidate budgeting and FPGA microarchitecture exploration. It connects
pinned HM-16.20 experiments, a history-aware proposal controller, analytical
screening, Verilator regression, persistent Pareto history, GCP workers, and
Vivado implementation.

The selected frozen Adaptive-K policy reduced candidate RDO evaluations by
38.21% on a held-out synthetic matrix while retaining 97.91% of Full-RDO
winners. Physical feedback produced a routed 16-lane balanced-tree kernel with
a derived 8.134 million candidates/s throughput proxy, 2.128x the routed P1
baseline. This is a kernel proxy, not encoder FPS, and the design does not meet
the 200 MHz timing constraint.

Start with the [artifact guide](HACKATHON_ARTIFACT.md), the
[four-page paper](paper.pdf), and the
[final algorithm specification](docs/final_algorithm_spec.md).

## Quick Start

Clone this repository so that `CHIA-RDO` remains inside the CHIA repository,
then create the pinned environment:

```bash
cd CHIA-RDO
conda env create -f environment.yml
conda activate chia-rdo
```

Run the unit suite and validate the published result summaries:

```bash
make test
jq -e '.candidate_count == 832 and .pareto_count == 16' results/phase7b/model_results.json
jq -e '.rows[] | select(.build_id == "serial-p16-d3-w31-tree") | .lut == 61207 and .dsp == 816 and .cost_width == 31' results/phase7b/synthesis_results.json
```

Replay the analytical CHIA search from the repository root:

```bash
conda run -n chia-rdo env PYTHONPATH=. python CHIA-RDO/chia/phase7b_graph.py --count 832
```

The replay should report 832 candidates, 16 Pareto points, and 832 cache hits.
Vivado 2024.2 is required only to reproduce physical implementation; the
published JSON and text reports can be inspected without a Vivado license.

## Artifact Contents

| Component | Location |
|---|---|
| CHIA search graphs | `chia/phase6_graph.py`, `chia/phase7b_graph.py` |
| Proposal controller | `chia/phase6_agent.py` |
| Adaptive-K policies | `software/policy_algorithms.py`, `software/run_policy.py` |
| Final RTL | `rtl/phase7b/` |
| Golden vectors and tests | `tests/full_rdo/`, `tests/test_phase6.py` |
| Published evidence | `results/phase4/`, `results/phase7/`, `results/phase7b/` |
| Final reports | `reports/phase7b_*.md` |

## Scope

The corpus contains deterministic synthetic 8-bit 4:2:0 All-Intra content.
The RTL implements 4x4 luma and consumes externally supplied exact HM candidate
bit counts; it does not implement CABAC context estimation or a complete HEVC
encoder. Modeled and measured values are identified separately throughout the
artifact.

CHIA-RDO is released under the [BSD 3-Clause License](LICENSE). Third-party HM
source is fetched reproducibly and is not redistributed in this repository.
