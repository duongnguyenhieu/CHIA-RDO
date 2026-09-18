# Phase 7B Width Analysis

Measured 8,960 frozen golden vectors across QP 22/27/32/37 and modes 0..34. These bounds qualify the corpus only; they are not a formal proof for arbitrary inputs.

| Signal | Minimum | Maximum | Interpretation | Required observed bits |
|---|---:|---:|---|---:|
| prediction | 0 | 255 | unsigned | 8 |
| residual | -255 | 255 | signed | 9 |
| transform | -25791 | 14478 | signed | 16 |
| quantized | -98 | 56 | signed | 8 |
| dequantized | -25920 | 14400 | signed | 16 |
| inverse_residual | -284 | 276 | signed | 10 |
| reconstruction | 0 | 255 | unsigned | 8 |
| distortion | 14 | 5631 | unsigned | 13 |
| rate_bits | 1 | 138 | unsigned | 8 |
| lambda_q16 | 376520 | 12048642 | unsigned | 24 |
| rd_cost_q16 | 6205480 | 1312532898 | unsigned | 31 |

The minimum corpus-safe unsigned RD-cost width is **31 bits**. Any narrower configuration must be rejected before RTL promotion; production width reduction still requires analytical range proof beyond this corpus.
