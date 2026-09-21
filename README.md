# CHIA-RDO

**From Adaptive K to Routed RTL: A CHIA Loop for HEVC RDO Co-Design**

Nguyen Hieu Duong and Duy Hieu Bui<br>
Vietnam National University<br>
Contact: [24020497@vnu.edu.vn](mailto:24020497@vnu.edu.vn)

[Paper](CHIA-RDO/paper.pdf) |
[LaTeX Source](CHIA-RDO/docs/paper.tex) |
[v1.0.0 Release](https://github.com/duongnguyenhieu/CHIA-RDO/releases/tag/chia-rdo-v1.0.0) |
[Artifact Guide](CHIA-RDO/HACKATHON_ARTIFACT.md) |
[Source](CHIA-RDO/)

CHIA-RDO is an evidence-preserving agentic hardware/software co-design loop for
adaptive HEVC rate-distortion optimization (RDO) candidate budgeting and FPGA
microarchitecture exploration. It connects pinned HM-16.20 experiments, a
history-aware proposal controller, analytical screening, Verilator regression,
persistent Pareto history, distributed GCP workers, and Vivado implementation.

This repository is the public artifact for the A3 CHIA Hackathon. The complete
project is under [`CHIA-RDO/`](CHIA-RDO/); the surrounding source tree provides
the pinned CHIA framework used to execute the loop.

## Key Results

| Result | Value |
|---|---:|
| Held-out RDO evaluation reduction | **38.21%** |
| Full-RDO winner retention | **97.91%** |
| Aggregate Y-PSNR BD-rate | **-0.026%** |
| Final architecture | **16-lane, depth-3, 31-bit, balanced tree** |
| Routed LUT / DSP use | **61,207 LUTs / 816 DSPs** |
| Derived post-route Fmax | **68.120 MHz** |
| Candidate-kernel throughput proxy | **8.134 M candidates/s** |
| Improvement over routed P1 proxy | **2.128x** |

The negative aggregate BD-rate is interpreted as no observed penalty on the
limited synthetic corpus, not as a general quality improvement. The final
design has -9.680 ns WNS and does not close the 200 MHz constraint. The reported
throughput is a candidate-kernel proxy, not encoder FPS or board performance.

## Co-Design Loop

```text
history-aware proposal -> analytical screen -> CHIA/Ray dispatch
-> pinned HM quality curves -> Verilator RTL checks -> Vivado route
-> schema validation and atomic persistence -> Pareto update -> next wave
```

The final calibrated graph evaluates 832 hardware configurations and preserves
16 Pareto points. Backend failures remain in history and directly informed the
transition from monolithic replication to resource-shared serial lanes and a
balanced winner-reduction tree.

## Repository Map

| Component | Location |
|---|---|
| IEEE four-page paper | [`CHIA-RDO/paper.pdf`](CHIA-RDO/paper.pdf), [`CHIA-RDO/docs/paper.tex`](CHIA-RDO/docs/paper.tex) |
| Artifact and claim guide | [`CHIA-RDO/HACKATHON_ARTIFACT.md`](CHIA-RDO/HACKATHON_ARTIFACT.md) |
| CHIA search graphs | [`CHIA-RDO/chia/`](CHIA-RDO/chia/) |
| Adaptive-K policies | [`CHIA-RDO/software/`](CHIA-RDO/software/) |
| Final SystemVerilog | [`CHIA-RDO/rtl/phase7b/`](CHIA-RDO/rtl/phase7b/), [`CHIA-RDO/rtl/rdo_pe.sv`](CHIA-RDO/rtl/rdo_pe.sv) |
| Tests and golden vectors | [`CHIA-RDO/tests/`](CHIA-RDO/tests/) |
| Machine-readable evidence | [`CHIA-RDO/results/`](CHIA-RDO/results/) |
| Final technical reports | [`CHIA-RDO/reports/`](CHIA-RDO/reports/) |

## Quick Start

Create the pinned environment:

```bash
cd CHIA-RDO
conda env create -f environment.yml
conda activate chia-rdo
```

Run the unit suite and validate the headline results:

```bash
make test
jq -e '.candidate_count == 832 and .pareto_count == 16' \
  results/phase7b/model_results.json
jq -e '.rows[] | select(.build_id == "serial-p16-d3-w31-tree") \
  | .lut == 61207 and .dsp == 816 and .cost_width == 31' \
  results/phase7b/synthesis_results.json
```

Replay the analytical CHIA search from the repository root:

```bash
conda run -n chia-rdo env PYTHONPATH=. \
  python CHIA-RDO/chia/phase7b_graph.py --count 832
```

A cache replay should report 832 candidates, 16 Pareto points, and 832 cache
hits. Vivado 2024.2 is only required to reproduce physical implementation; the
published summaries and text reports can be inspected without a Vivado license.

## Scope and Limitations

The software corpus contains deterministic synthetic 8-bit 4:2:0 All-Intra
content. The RTL implements 4x4 luma and consumes externally supplied exact HM
candidate bit counts. It does not implement CABAC context estimation, chroma,
inter prediction, larger transforms, or a complete HEVC encoder. The 31-bit
cost width is qualified on the observed corpus rather than formally proven for
arbitrary input.

## Built on CHIA

This project integrates the open-source
[CHIA framework](https://github.com/ucb-bar/chia), developed by the SLICE Lab at
UC Berkeley. CHIA provides the composable graph and distributed execution
runtime used by this artifact. See the
[CHIA documentation](https://docs.chialoops.ai/) and
[CHIA paper](https://arxiv.org/abs/2606.27350) for framework details.

CHIA-RDO is released under the
[BSD 3-Clause License](CHIA-RDO/LICENSE). Third-party HM source is fetched
reproducibly and is not redistributed in this repository.
