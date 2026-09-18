"""Integer reference model for the explicitly supported HM 4x4 DC profile."""

from __future__ import annotations


DST = (
    (29, 55, 74, 84),
    (74, 74, 0, -74),
    (84, -29, -74, 55),
    (55, -84, 74, -29),
)
QUANT_SCALES = (26214, 23302, 20560, 18396, 16384, 14564)
INV_QUANT_SCALES = (40, 45, 51, 57, 64, 72)
SUPPORTED_MODES = tuple(range(35))


def clip(value: int, minimum: int, maximum: int) -> int:
    return min(maximum, max(minimum, value))


def prediction_dc(references: list[int]) -> list[int]:
    if len(references) != 9:
        raise ValueError("4x4 DC prediction requires top-left, four top, and four left references")
    _, top, left = references[0], references[1:5], references[5:9]
    dc = (sum(top) + sum(left) + 4) >> 3
    result = [dc] * 16
    result[0] = (top[0] + left[0] + 2 * dc + 2) >> 2
    for x in range(1, 4):
        result[x] = (top[x] + 3 * dc + 2) >> 2
    for y in range(1, 4):
        result[y * 4] = (left[y] + 3 * dc + 2) >> 2
    return result


def prediction_4x4(references: list[int], mode: int) -> list[int]:
    """Return HM's 4x4 luma prediction for the Phase-5.2 mode subset."""
    if len(references) != 17:
        raise ValueError("4x4 prediction requires top-left, eight top, and eight left references")
    if mode not in SUPPORTED_MODES:
        raise ValueError(f"unsupported intra mode: {mode}")
    top_left = references[0]
    top = references[1:9]
    left = references[9:17]
    if mode == 0:
        top_right = top[4]
        bottom_left = left[4]
        return [
            ((3 - x) * left[y] + (x + 1) * top_right +
             (3 - y) * top[x] + (y + 1) * bottom_left + 4) >> 3
            for y in range(4) for x in range(4)
        ]
    if mode == 1:
        return prediction_dc([top_left, *top[:4], *left[:4]])
    vertical = mode >= 18
    angle_mode = mode - 26 if vertical else -(mode - 10)
    angle_table = (0, 2, 5, 9, 13, 17, 21, 26, 32)
    inverse_angle_table = (0, 4096, 1638, 910, 630, 482, 390, 315, 256)
    angle = (-1 if angle_mode < 0 else 1) * angle_table[abs(angle_mode)]
    main_source = [top_left, *(top if vertical else left)]
    side_source = [top_left, *(left if vertical else top)]
    main = {index: value for index, value in enumerate(main_source)}
    if angle < 0:
        inverse_sum = 128
        lower = (4 * angle) >> 5
        for index in range(-1, lower, -1):
            inverse_sum += inverse_angle_table[abs(angle_mode)]
            main[index] = side_source[inverse_sum >> 8]
    temporary = [[0] * 4 for _ in range(4)]
    for y in range(4):
        delta_position = (y + 1) * angle
        delta_integer = delta_position >> 5
        delta_fraction = delta_position & 31
        for x in range(4):
            first = main[x + delta_integer + 1]
            if delta_fraction:
                second = main[x + delta_integer + 2]
                temporary[y][x] = ((32 - delta_fraction) * first + delta_fraction * second + 16) >> 5
            else:
                temporary[y][x] = first
    if angle == 0:
        for y in range(4):
            temporary[y][0] = clip(temporary[y][0] + ((side_source[y + 1] - side_source[0]) >> 1), 0, 255)
    if vertical:
        return [temporary[y][x] for y in range(4) for x in range(4)]
    return [temporary[x][y] for y in range(4) for x in range(4)]


def residual(original: list[int], prediction: list[int]) -> list[int]:
    return [source - predicted for source, predicted in zip(original, prediction)]


def forward_dst(block: list[int]) -> list[int]:
    temporary = [0] * 16
    coefficients = [0] * 16
    for i in range(4):
        row = block[4 * i:4 * i + 4]
        for output_row in range(4):
            temporary[output_row * 4 + i] = (sum(row[column] * DST[output_row][column] for column in range(4)) + 1) >> 1
    for i in range(4):
        row = temporary[4 * i:4 * i + 4]
        for output_row in range(4):
            coefficients[output_row * 4 + i] = (sum(row[column] * DST[output_row][column] for column in range(4)) + 128) >> 8
    return coefficients


def quantize(coefficients: list[int], qp: int) -> list[int]:
    qp_per, qp_rem = divmod(qp, 6)
    qbits = 14 + qp_per + 5
    rounding = 171 << (qbits - 9)
    scale = QUANT_SCALES[qp_rem]
    return [
        clip((-1 if value < 0 else 1) * ((abs(value) * scale + rounding) >> qbits), -32768, 32767)
        for value in coefficients
    ]


def dequantize(coefficients: list[int], qp: int) -> list[int]:
    qp_per, qp_rem = divmod(qp, 6)
    right_shift = 6 - (5 + qp_per)
    scale = INV_QUANT_SCALES[qp_rem]
    if right_shift > 0:
        rounding = 1 << (right_shift - 1)
        return [clip((value * scale + rounding) >> right_shift, -32768, 32767) for value in coefficients]
    return [clip((value * scale) << -right_shift, -32768, 32767) for value in coefficients]


def inverse_dst(coefficients: list[int]) -> list[int]:
    temporary = [0] * 16
    block = [0] * 16
    for i in range(4):
        column = [coefficients[i], coefficients[4 + i], coefficients[8 + i], coefficients[12 + i]]
        for output_column in range(4):
            value = sum(column[row] * DST[row][output_column] for row in range(4))
            temporary[i * 4 + output_column] = clip((value + 64) >> 7, -32768, 32767)
    for i in range(4):
        column = [temporary[i], temporary[4 + i], temporary[8 + i], temporary[12 + i]]
        for output_column in range(4):
            value = sum(column[row] * DST[row][output_column] for row in range(4))
            block[i * 4 + output_column] = clip((value + 2048) >> 12, -32768, 32767)
    return block


def reconstruct(prediction: list[int], inverse_residual: list[int]) -> list[int]:
    return [clip(predicted + difference, 0, 255) for predicted, difference in zip(prediction, inverse_residual)]


def distortion(original: list[int], reconstruction: list[int]) -> int:
    return sum((source - rebuilt) ** 2 for source, rebuilt in zip(original, reconstruction))


def evaluate(references: list[int], original: list[int], qp: int) -> dict[str, list[int] | int]:
    predicted = prediction_dc(references)
    differences = residual(original, predicted)
    transformed = forward_dst(differences)
    quantized = quantize(transformed, qp)
    dequantized = dequantize(quantized, qp)
    inverse = inverse_dst(dequantized)
    rebuilt = reconstruct(predicted, inverse)
    return {"prediction": predicted, "residual": differences, "transform": transformed,
            "quantized": quantized, "dequantized": dequantized, "inverse_residual": inverse,
             "reconstruction": rebuilt, "distortion": distortion(original, rebuilt)}


def evaluate_candidate(references: list[int], original: list[int], mode: int, qp: int) -> dict[str, list[int] | int]:
    predicted = prediction_4x4(references, mode)
    differences = residual(original, predicted)
    transformed = forward_dst(differences)
    quantized = quantize(transformed, qp)
    dequantized = dequantize(quantized, qp)
    inverse = inverse_dst(dequantized)
    rebuilt = reconstruct(predicted, inverse)
    return {"prediction": predicted, "residual": differences, "transform": transformed,
            "quantized": quantized, "dequantized": dequantized, "inverse_residual": inverse,
            "reconstruction": rebuilt, "distortion": distortion(original, rebuilt)}
