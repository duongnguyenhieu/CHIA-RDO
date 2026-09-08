# CHIA-RDO

CHIA-RDO is a research project for hardware-aware adaptive HEVC RDO candidate
budgeting. The Phase 1 smoke baseline and instrumentation quality gate pass;
research-scale sequence validation and adaptive policies are not complete.

Start with [docs/environment_report.md](docs/environment_report.md) and
[docs/project_plan.md](docs/project_plan.md).

The existing installation can be used with:

```bash
conda activate chia_env
```

To create a separate project environment from this directory:

```bash
conda env create -f environment.yml
conda activate chia-rdo
```

No cloud resources are created by Phase 0.

Run the verified baseline and blocking Phase 1 gate with:

```bash
make baseline
make phase1-gate
```

See [reports/phase1_quality_gate.md](reports/phase1_quality_gate.md) for measured
evidence and limitations.
