# Full-RDO Datapath MVP Architecture

## Scope

The Phase-5.1 MVP is one deterministic HEVC/HM-compatible luma RDO candidate path. It is not a complete HEVC encoder and does not support HM's default RDOQ path.

The initial supported profile is:

- 4x4 luma transform unit only.
- 8-bit internal pixel precision.
- Intra DC mode 1 only, including HM's 4x4 luma DC edge filtering.
- HEVC 4x4 integer DST in both directions.
- Scalar HM quantization with `RDOQ=0`, `RDOQTS=0`, transform skip disabled, sign-data hiding disabled, and flat scaling lists.
- Fixed QP values 22, 27, 32, and 37.
- HM SSE distortion for 8-bit luma.
- Exact HM entropy-coded candidate bit count supplied at the PE interface. Hardware CABAC context modeling is not implemented in this MVP.
- Existing Q16.16 `rdo_pe` for `J = D + lambda*R`.

The frozen `adaptive-threshold.v1` policy, thresholds `0.04/0.20`, and K set `{4,16,35}` are not inputs to this single-candidate datapath and remain unchanged.

## Interface

One input transaction contains:

- `mode`: 6 bits; only value 1 is accepted.
- `qp`: 6 bits; only 22, 27, 32, or 37 is accepted.
- `reference_top_left`: one unsigned 8-bit diagonal sample retained for trace provenance; DC mode does not consume it.
- `reference_top[0:3]`: four unsigned 8-bit reconstructed samples.
- `reference_left[0:3]`: four unsigned 8-bit reconstructed samples.
- `original[0:15]`: sixteen row-major unsigned 8-bit samples.
- `rate_bits`: unsigned 24-bit exact HM candidate entropy count.
- `lambda_q`: unsigned 32-bit Q16.16 lambda.
- `valid/ready`: one-candidate transaction handshake.

The result exposes mode, all supported intermediate blocks, 32-bit distortion, 24-bit bit cost, 56-bit Q16.16 RD cost, overflow, valid, and measured cycle latency.

## Arithmetic widths

| Quantity | Interface width | Arithmetic rule |
|---|---:|---|
| Reference/original/prediction | unsigned 8 | HM internal bit depth 8 |
| DC accumulation | unsigned 12 | Eight samples plus rounding constant |
| Residual | signed 9 | `original - prediction`, range -255..255 |
| DST multiply/accumulate | signed 32 | HM matrix coefficients and rounded arithmetic shifts |
| Forward transformed coefficient | signed 32 | HM `TCoeff`; observed 4x4 range retained without narrowing |
| Quantized coefficient | signed 16 | Clipped to HM transform dynamic range -32768..32767 |
| Dequantized coefficient | signed 16 | Clipped to the same transform range |
| Inverse-transform residual | signed 16 | HM `Pel` range after inverse DST |
| Reconstruction | unsigned 8 | `clip(prediction + inverse_residual, 0, 255)` |
| Squared-error accumulator | unsigned 32 | Exact sum of sixteen 8-bit squared errors |
| Bit cost | unsigned 24 | Integer HM CABAC count supplied externally |
| Lambda | unsigned 32 | Q16.16 |
| RD cost | unsigned 56 | Q16.16, existing saturating `rdo_pe` |

## Exact stage definitions

1. DC prediction computes `(sum(top)+sum(left)+4)>>3`, fills the block, then applies HM luma DC edge filtering to the top row and left column. The output at `(0,0)` uses `top[0]` and `left[0]`; the diagonal sample is not used by this mode.
2. Residual is exact signed subtraction.
3. Forward transform is the HM 4x4 integer DST matrix with first-pass shift 1 and second-pass shift 8. Each pass adds `1<<(shift-1)` before HM arithmetic right shift.
4. Scalar quantization uses HM tables `g_quantScales={26214,23302,20560,18396,16384,14564}`, `qBits=14+floor(QP/6)+5`, and I-slice rounding `171<<(qBits-9)`.
5. Inverse quantization uses `g_invQuantScales={40,45,51,57,64,72}` and `rightShift=6-(5+floor(QP/6))`, with HM rounding and clipping.
6. Inverse transform uses the HM inverse DST with shifts 7 and 12 and the corresponding signed clipping.
7. Reconstruction clips prediction plus inverse residual to 8-bit range.
8. Distortion is HM's 8-bit luma SSE: `sum((original-reconstruction)^2)`. The bit-depth precision adjustment is zero at 8 bits.
9. The existing RD PE forms Q16.16 cost from distortion, exact externally supplied HM bits, and lambda.

## Pipeline boundaries and latency

The first MVP keeps prediction through distortion as one combinational codec-stage kernel, followed by one registered stage that captures all intermediates. The existing RD-cost PE uses depth 2: registered multiplication followed by accumulation. With no backpressure, the transaction crosses three registering edges including its acceptance edge, and result valid is asserted two elapsed cycles after acceptance. Output backpressure globally stalls the RD PE as already documented.

This boundary minimizes new control logic while preserving observable stage outputs for exact regression. Future synthesis feedback may split prediction, DST, quantization, inverse DST, and distortion into separate registers without changing stage arithmetic.

## Golden-vector profile

HM-16.20 is run single-threaded on deterministic synthetic 64x64 material at QP 22/27/32/37 with the explicit scalar profile above. Instrumentation captures generated references, original, prediction, forward residual, transformed coefficients, quantized coefficients, dequantized coefficients, inverse residual, reconstruction, distortion, exact candidate bits, lambda, and RD cost. Vectors are accepted only when all fields belong to the same 4x4 mode-1 TU transaction.

Unsupported items include planar/angular modes, transform sizes other than 4x4, chroma, transform skip, RDOQ, sign-data hiding, scaling lists, transquant bypass, hardware CABAC bit estimation, and multi-candidate scheduling of this longer datapath.
