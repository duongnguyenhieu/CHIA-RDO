# CHIA-RDO Environment Report

Inspection date: 2026-09-08

Project location: `/home/duong-nguyen-hieu/chia/CHIA-RDO`

CHIA source revision: `16c35e9` on branch `main`

No credential, token, private key, service-account key, or account identity was
printed or stored during this inspection.

## Host

| Item | Detected value | Status |
|---|---|---|
| OS | Ubuntu 24.04.4 LTS (`noble`) | Ready |
| Kernel | Linux 7.0.0-31-generic x86_64 | Ready |
| CPU | Intel Core Ultra 9 185H, 22 logical CPUs reported | Ready |
| RAM | 30 GiB total, about 24 GiB available during inspection | Ready |
| Swap | 8 GiB | Ready |
| Storage | Root filesystem 296 GiB, 82 GiB available | Limited but adequate for initial work |
| Attached FPGA | No FPGA or JTAG device detected by PCI/USB inspection | Not available |

The host contains KV260 platform collateral under
`/home/duong-nguyen-hieu/workspace/kria-vitis-platforms/kv260`, including an
XSA and XPFM. This identifies Kria KV260 as an available local build target,
not as a currently attached board.

## Software Toolchain

| Tool | Detected value | Status |
|---|---|---|
| Python, active base shell | 3.14.7 | Not suitable for the documented CHIA environment |
| Python, `chia_env` | 3.10.21 | Installed; CHIA README recommends 3.10.19, while package metadata permits Python >=3.10 |
| GCC/G++ | 13.3.0 | Ready |
| GNU Make | 4.3 | Ready |
| CMake | 4.3.1 in `chia_env`; Xilinx-bundled CMake 3.24.2 also exists | Ready after environment activation |
| Ninja | 1.13.2 in `chia_env` | Ready after environment activation |
| Git | 2.43.0 | Ready |
| Docker/Compose | Not found | Missing; required for standard CHIA logical workers |
| Icarus Verilog | Not found | Optional, missing |
| Yosys | Not found | Optional open-source synthesis backend, missing |
| Java/Javac | Not found | Missing; not required for HM |
| Scala/SBT | Not found | Missing; not required for HM |
| Chipyard | No checkout found | Missing; not required for this prototype |
| gem5 | No checkout or binary found | Missing; not required for this prototype |

The active shell is Conda `base`, not `chia_env`. Use `conda activate chia_env`
before invoking CHIA. The command `conda run -n chia_env ...` was used for all
CHIA-specific checks in this report.

## CHIA

| Item | Detected value | Status |
|---|---|---|
| Distribution | `chialoops` 1.0.1 | Installed editable from this checkout |
| Source | `https://github.com/ucb-bar/chia.git` | Available |
| Runtime | Ray 2.54.0 | Import verified |
| CLI | `chia` available inside `chia_env` | Ready after environment activation |
| Core node API | `@ChiaFunction`, `chia_remote`, `chia_remote_blocking`, `get`, `chia_wait` | Available |
| Agent tool API | `ChiaTool` with MCP/FastMCP; `BashTool`, `AsyncBashTool`, `AsyncJobTool` | Available |
| Caching/profiling | Tagged caching/bypass and profiler integration | Available |

Agent/model backend modules present in the checkout are Antigravity, AWS
Bedrock, Claude, Codex, Copilot, Ollama, OpenAI-compatible providers, OpenCode,
Google Vertex AI, and vLLM. Presence of a module does not imply provider
credentials or model entitlement.

Execution backends supported by the inspected runtime are local/on-prem Ray,
SSH-connected machines, Docker logical workers, GCP Compute Engine, AWS EC2,
and cloud networking through Tailscale or reverse SSH tunnels. GCP provisioning
supports per-node machine type, image, disk size, zone, and Spot instances.

Relevant examples inspected:

- `examples/memcpy`: agent -> Chisel build -> Verilator -> debug loop.
- `examples/timing_opt`: correctness and synthesis feedback loop with persisted design variants.
- `examples/circt_issue_solver`: multi-stage agent loop with selectable model backends.
- `examples/bypass_cache`: cache and replay behavior.
- `examples/gem5_align`: distributed simulator-oriented loop.

## HEVC

| Item | Detected value | Status |
|---|---|---|
| C/C++ compiler | GCC/G++ 13.3.0 | Ready |
| Build system | CMake 4.3.1 and Ninja 1.13.2 in `chia_env` | Ready |
| HM reference encoder | No HM checkout or `TAppEncoder`/`EncoderApp` binary found | Missing |
| x265/VTM fallback | No checkout or encoder binary found | Missing |
| HEVC test sequences | Not inventoried in Phase 0; no project dataset has been staged | Missing |

Phase 1 must acquire and pin a public HM release, preserve its license and
provenance, install a normal CMake executable, build the encoder, and run a
small full-RDO smoke test before any adaptive policy is implemented.

## RTL and FPGA

| Tool | Detected value | Status |
|---|---|---|
| Verilator | 5.052 in `chia_env` | Ready after environment activation |
| Vivado | 2024.2 at `/tools/Xilinx/Vivado/2024.2/bin/vivado` | Installed, not on `PATH` |
| Vivado | 2025.2 at `/tools/Xilinx/2025.2/Vivado/bin/vivado` | Installed, not on `PATH` |
| Vitis | 2024.2 and 2025.2 under `/tools/Xilinx` | Installed, not on `PATH` |
| FPGA target collateral | Kria KV260 / `xck26-sfvc784-2LV-c` | Available locally |
| Physical FPGA | None detected | Not available |

### Vivado Synthesis License Probe

A temporary, one-register Verilog design was synthesized in batch mode for
`xck26-sfvc784-2LV-c`. The temporary probe source was removed after testing.

| Vivado | License result | Synthesis result |
|---|---|---|
| 2024.2 | `Synthesis`/`xck26` feature acquired and released | Passed: 0 errors, 0 critical warnings |
| 2025.2 | `Synthesis`/`xck26` feature acquired and released | Passed: 0 errors, 0 critical warnings |

This verifies local RTL synthesis entitlement for the intended KV260 device at
inspection time. It does not prove board availability, implementation closure,
or that a floating license will always be available during future parallel runs.
Vivado synthesis must therefore remain a local backend unless an explicitly
licensed remote worker is later configured.

To expose the preferred version for future local work without hard-coding it in
project scripts:

```bash
source /tools/Xilinx/2025.2/Vivado/settings64.sh
```

## Google Cloud

| Item | Detected value | Status |
|---|---|---|
| GCloud CLI | Google Cloud SDK 583.0.0 | Installed |
| CLI authentication | Active credential can refresh; identity deliberately not printed | Authenticated |
| Application Default Credentials | Token refresh succeeded through ADC | Authenticated |
| ADC library path | `google-cloud-compute` import and read call verified in `chia_env` | Ready for CHIA |
| ADC default project | Unset | Needs explicit project configuration |
| ADC quota project | `project-1bfffc90-767b-48e2-ac1` | Configured |
| GCloud active project | Unset | Needs configuration |
| Compute region/zone | Unset | Needs configuration |
| Intended project candidate | `project-1bfffc90-767b-48e2-ac1` (`CHIA-RDO-Project`) | Active; billing enabled |
| Compute Engine API | Enabled and ADC read verified on intended project candidate | Ready |
| Service Usage API | Enabled | Ready |
| Vertex AI API | Not enabled | Optional; only needed for a Vertex-backed agent |

Seven projects are visible to the configured identity. Compute Engine API and
ADC read access were verified on these two projects:

- `project-1bfffc90-767b-48e2-ac1`
- `project-d7828622-c9f3-4241-b61`

Compute Engine is disabled or not confirmed on the other five visible projects.
No VM, disk, image, firewall rule, bucket, or paid API call was created.

Authentication is not missing, so `gcloud auth application-default login` is
not currently required. If ADC later expires or is removed, the exact manual
recovery commands are:

```bash
gcloud auth application-default login
gcloud auth application-default set-quota-project project-1bfffc90-767b-48e2-ac1
```

Before Phase 7, configure the CLI explicitly. The following uses CHIA's default
GCP zone and must be confirmed by the user before resources are launched:

```bash
gcloud config set project project-1bfffc90-767b-48e2-ac1
gcloud config set compute/region us-central1
gcloud config set compute/zone us-central1-a
```

If the selected agent uses Vertex AI, enable it manually for the selected
project:

```bash
gcloud services enable aiplatform.googleapis.com \
  --project=project-1bfffc90-767b-48e2-ac1
```

## Missing Dependencies and Blockers

Required before Phase 1 software baseline:

- Activate `chia_env` for every CHIA command.
- Acquire and pin HM source and baseline encoder configuration.
- Acquire a minimal licensed HEVC test sequence or create a synthetic smoke input.

Required before containerized CHIA execution:

- Install Docker with Compose support if CHIA container workers will be used.

Not blocking initial software work:

- Vivado is not on `PATH`; both installed versions can synthesize the KV260 target.
- No physical FPGA is attached; synthesis and timing can proceed locally without a board.
- GCloud project/region/zone are unset; no cloud execution is needed until Phase 7.
- Storage has 82 GiB free, so datasets, Docker images, Vivado output, and cloud caches need quotas and cleanup rules.

## Phase 0 Verdict

CHIA and GCP ADC are functional. Local Vivado synthesis is licensed and verified
for KV260. CMake and Verilator are installed in `chia_env`. Phase 1 is blocked
only by acquiring/building the HM reference encoder. Docker remains a blocker
for standard containerized CHIA workers, but local Ray tasks can be developed.
