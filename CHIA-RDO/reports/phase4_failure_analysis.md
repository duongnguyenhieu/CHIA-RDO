# Phase 4 Failure Analysis

Frozen Adaptive-threshold matched 97.91% of Full-RDO winners in aggregate. The worst run was `phase4-smooth-edges-96x64-4f-yuv420p8` QP 22 at 91.00%; the largest per-run bitrate increase was +0.172% on `phase4-smooth-edges-96x64-4f-yuv420p8` QP 27.

## Distribution And Miss Concentration

| Workload | Events | Mean confidence | Mean activity | Mean normalized rough cost | K=4 | K=16 | K=35 | Miss rate | K=4 miss rate | K=35/top-16 proxy | Most common missed PU |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| phase4-mixed-texture-192x128-4f-yuv420p8 | 32736 | 0.05108 | 0.12231 | 0.21876 | 0.00% | 25.70% | 74.30% | 1.43% | 0.00% | 67.97% | 4x4 |
| phase4-repetitive-128x96-4f-yuv420p8 | 16352 | 0.18875 | 0.09070 | 0.26141 | 0.00% | 24.50% | 75.50% | 0.06% | 0.00% | 43.33% | 16x16 |
| phase4-smooth-edges-96x64-4f-yuv420p8 | 8176 | 0.66072 | 0.00859 | 0.00768 | 96.78% | 3.02% | 0.20% | 4.79% | 4.77% | 0.20% | 4x4 |

The smooth/edge workload drives the controller into K=4 and contains the highest miss concentration, while repetitive and mixed texture shift almost entirely to K=16/35. This is a systematic feature-distribution response, not a threshold change: low normalized rough cost classifies smooth blocks as easy. Its coding impact remains bounded in the four-point curve, so no v2 is created.

Adaptive-threshold is not dominated by Fixed-K 2/4/8/16 on coding quality: its aggregate BD-rate is lower and its winner retention is higher. Fixed-K 16 is more aggressive and therefore faster in the analytical model, but retains fewer winners. The K=35/top-16 column is an over-allocation proxy: it counts events where K=35 was selected although the Full-RDO winner ranked within 16. It is not proof that K=16 would preserve the final coding trajectory, but it locates conservative decisions that limit speedup.

## Worst Missed-Winner Events

| Workload | QP | CU | PU | K | Winner rank | SATD | Rough cost | Confidence | Activity | Norm. best rough | Full winner | Policy winner |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| phase4-smooth-edges-96x64-4f-yuv420p8 | 27 | 16x16 | 16x16 | 4 | 35 | 164 | 193.896 | 0.04085 | 0.00196 | 0.00160 | 32 | 26 |
| phase4-smooth-edges-96x64-4f-yuv420p8 | 32 | 8x8 | 8x8 | 4 | 35 | 16 | 61.659 | 0.32231 | 0.00196 | 0.00145 | 34 | 27 |
| phase4-smooth-edges-96x64-4f-yuv420p8 | 22 | 8x8 | 4x4 | 4 | 35 | 8 | 22.382 | 0.18735 | 0.00000 | 0.00314 | 34 | 33 |
| phase4-smooth-edges-96x64-4f-yuv420p8 | 22 | 8x8 | 4x4 | 4 | 35 | 8 | 22.382 | 0.18735 | 0.00000 | 0.00314 | 34 | 33 |
| phase4-smooth-edges-96x64-4f-yuv420p8 | 22 | 8x8 | 4x4 | 4 | 35 | 8 | 22.382 | 0.23054 | 0.00000 | 0.00255 | 34 | 10 |
| phase4-smooth-edges-96x64-4f-yuv420p8 | 27 | 8x8 | 4x4 | 4 | 35 | 15 | 44.896 | 0.25819 | 0.00000 | 0.00405 | 34 | 31 |
| phase4-smooth-edges-96x64-4f-yuv420p8 | 27 | 8x8 | 4x4 | 4 | 35 | 16 | 45.896 | 0.23383 | 0.00000 | 0.00552 | 34 | 31 |
| phase4-smooth-edges-96x64-4f-yuv420p8 | 27 | 8x8 | 4x4 | 4 | 35 | 8 | 33.625 | 0.25819 | 0.00000 | 0.00405 | 34 | 31 |
| phase4-smooth-edges-96x64-4f-yuv420p8 | 27 | 8x8 | 4x4 | 4 | 35 | 8 | 33.625 | 0.34805 | 0.00000 | 0.00301 | 34 | 0 |
| phase4-smooth-edges-96x64-4f-yuv420p8 | 27 | 8x8 | 4x4 | 4 | 35 | 8 | 33.625 | 0.34805 | 0.00000 | 0.00301 | 34 | 0 |
| phase4-smooth-edges-96x64-4f-yuv420p8 | 27 | 8x8 | 4x4 | 4 | 35 | 0 | 29.896 | 0.50000 | 0.00000 | 0.00209 | 34 | 31 |
| phase4-smooth-edges-96x64-4f-yuv420p8 | 27 | 8x8 | 4x4 | 4 | 35 | 0 | 29.896 | 0.50000 | 0.00000 | 0.00209 | 34 | 31 |
| phase4-smooth-edges-96x64-4f-yuv420p8 | 27 | 8x8 | 4x4 | 4 | 35 | 0 | 29.896 | 0.50000 | 0.00000 | 0.00209 | 34 | 31 |
| phase4-smooth-edges-96x64-4f-yuv420p8 | 27 | 8x8 | 4x4 | 4 | 35 | 0 | 29.896 | 0.50000 | 0.00000 | 0.00209 | 34 | 31 |
| phase4-smooth-edges-96x64-4f-yuv420p8 | 27 | 8x8 | 4x4 | 4 | 35 | 0 | 29.896 | 0.50000 | 0.00000 | 0.00209 | 34 | 31 |
| phase4-smooth-edges-96x64-4f-yuv420p8 | 27 | 8x8 | 8x8 | 4 | 35 | 0 | 25.625 | 0.50000 | 0.00000 | 0.00052 | 34 | 31 |

Failure evidence is limited to deterministic synthetic All-Intra traces. It does not establish behavior on natural-camera noise, standard HEVC classes, inter prediction, 10-bit content, or other chroma formats.
