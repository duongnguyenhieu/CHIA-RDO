module full_rdo_codec_4x4 (
  input  logic [135:0] references,
  input  logic [127:0] original,
  input  logic [5:0]   mode,
  input  logic [5:0]   qp,
  output logic         supported,
  output logic [127:0] prediction,
  output logic [143:0] residual,
  output logic [511:0] transformed,
  output logic [255:0] quantized,
  output logic [255:0] dequantized,
  output logic [255:0] inverse_residual,
  output logic [127:0] reconstruction,
  output logic [31:0]  distortion
);
  localparam integer DST [0:15] = '{29, 55, 74, 84, 74, 74, 0, -74,
                                    84, -29, -74, 55, 55, -84, 74, -29};
  localparam integer ANGLE [0:8] = '{0, 2, 5, 9, 13, 17, 21, 26, 32};
  localparam integer INV_ANGLE [0:8] = '{0, 4096, 1638, 910, 630, 482, 390, 315, 256};
  integer ref_sample [0:16];
  integer source_sample [0:15];
  integer predicted_sample [0:15];
  integer residual_sample [0:15];
  integer transform_temporary [0:15];
  integer transform_sample [0:15];
  integer quantized_sample [0:15];
  integer dequantized_sample [0:15];
  integer inverse_temporary [0:15];
  integer inverse_sample [0:15];
  integer reconstruction_sample [0:15];
  integer angular_temporary [0:15];
  integer reference_main [0:24];
  integer reference_side [0:24];
  integer dc_sum;
  integer dc_value;
  integer matrix_sum;
  integer quant_scale;
  integer inverse_scale;
  integer qbits;
  integer quant_rounding;
  integer inverse_left_shift;
  integer magnitude;
  integer error;
  integer row;
  integer column;
  integer output_index;
  integer angular_index;
  integer angle_mode;
  logic [3:0] absolute_angle_mode;
  integer prediction_angle;
  integer inverse_angle_sum;
  integer delta_position;
  integer delta_integer;
  integer delta_fraction;
  integer first_reference;
  integer second_reference;
  logic vertical_mode;
  longint signed product;

  function automatic integer clip16(input longint signed value);
    if (value < -32768) clip16 = -32768;
    else if (value > 32767) clip16 = 32767;
    else clip16 = integer'(value);
  endfunction

  function automatic integer clip8(input integer value);
    if (value < 0) clip8 = 0;
    else if (value > 255) clip8 = 255;
    else clip8 = value;
  endfunction

  always_comb begin
    for (row = 0; row < 17; row = row + 1) ref_sample[row] = {24'b0, references[row*8 +: 8]};
    for (row = 0; row < 16; row = row + 1) source_sample[row] = {24'b0, original[row*8 +: 8]};
    vertical_mode = 1'b0;
    angle_mode = 0;
    absolute_angle_mode = 0;
    prediction_angle = 0;
    inverse_angle_sum = 0;
    delta_position = 0;
    delta_integer = 0;
    delta_fraction = 0;
    first_reference = 0;
    second_reference = 0;
    for (angular_index = 0; angular_index < 25; angular_index = angular_index + 1) begin
      reference_main[angular_index] = 0;
      reference_side[angular_index] = 0;
    end
    for (angular_index = 0; angular_index < 16; angular_index = angular_index + 1)
      angular_temporary[angular_index] = 0;

    dc_sum = 4;
    for (column = 1; column <= 4; column = column + 1) dc_sum = dc_sum + ref_sample[column];
    for (row = 9; row <= 12; row = row + 1) dc_sum = dc_sum + ref_sample[row];
    dc_value = dc_sum >>> 3;
    for (row = 0; row < 16; row = row + 1) predicted_sample[row] = dc_value;
    case (mode)
      6'd0: begin
        for (row = 0; row < 4; row = row + 1)
          for (column = 0; column < 4; column = column + 1)
            predicted_sample[row*4+column] = ((3-column)*ref_sample[9+row]
              + (column+1)*ref_sample[5] + (3-row)*ref_sample[1+column]
              + (row+1)*ref_sample[13] + 4) >>> 3;
      end
      6'd1: begin
        predicted_sample[0] = (ref_sample[1] + ref_sample[9] + 2*dc_value + 2) >>> 2;
        for (column = 1; column < 4; column = column + 1)
          predicted_sample[column] = (ref_sample[1+column] + 3*dc_value + 2) >>> 2;
        for (row = 1; row < 4; row = row + 1)
          predicted_sample[row*4] = (ref_sample[9+row] + 3*dc_value + 2) >>> 2;
      end
      6'd10: begin
        for (row = 0; row < 4; row = row + 1)
          for (column = 0; column < 4; column = column + 1)
            predicted_sample[row*4+column] = ref_sample[9+row];
        for (column = 0; column < 4; column = column + 1)
          predicted_sample[column] = clip8(ref_sample[9] + ((ref_sample[1+column] - ref_sample[0]) >>> 1));
      end
      6'd26: begin
        for (row = 0; row < 4; row = row + 1)
          for (column = 0; column < 4; column = column + 1)
            predicted_sample[row*4+column] = ref_sample[1+column];
        for (row = 0; row < 4; row = row + 1)
          predicted_sample[row*4] = clip8(ref_sample[1] + ((ref_sample[9+row] - ref_sample[0]) >>> 1));
      end
      default: begin
        if (mode <= 34) begin
          vertical_mode = mode >= 18;
          angle_mode = vertical_mode ? integer'(mode) - 26 : -(integer'(mode) - 10);
          absolute_angle_mode = 4'(angle_mode < 0 ? -angle_mode : angle_mode);
          prediction_angle = (angle_mode < 0 ? -1 : 1) * ANGLE[absolute_angle_mode];
          for (angular_index = 0; angular_index <= 8; angular_index = angular_index + 1) begin
            if (angular_index == 0) begin
              reference_main[8] = ref_sample[0];
              reference_side[8] = ref_sample[0];
            end else if (vertical_mode != 0) begin
              reference_main[8+angular_index] = ref_sample[angular_index];
              reference_side[8+angular_index] = ref_sample[8+angular_index];
            end else begin
              reference_main[8+angular_index] = ref_sample[8+angular_index];
              reference_side[8+angular_index] = ref_sample[angular_index];
            end
          end
          if (prediction_angle < 0) begin
            inverse_angle_sum = 128;
            for (angular_index = -1; angular_index > ((4*prediction_angle) >>> 5);
                 angular_index = angular_index - 1) begin
              inverse_angle_sum = inverse_angle_sum + INV_ANGLE[absolute_angle_mode];
              reference_main[8+angular_index] = reference_side[8+(inverse_angle_sum >>> 8)];
            end
          end
          for (row = 0; row < 4; row = row + 1) begin
            delta_position = (row+1) * prediction_angle;
            delta_integer = delta_position >>> 5;
            delta_fraction = delta_position & 31;
            for (column = 0; column < 4; column = column + 1) begin
              first_reference = reference_main[8+column+delta_integer+1];
              if (delta_fraction != 0) begin
                second_reference = reference_main[8+column+delta_integer+2];
                angular_temporary[row*4+column] = ((32-delta_fraction)*first_reference
                  + delta_fraction*second_reference + 16) >>> 5;
              end else begin
                angular_temporary[row*4+column] = first_reference;
              end
            end
          end
          if (prediction_angle == 0) begin
            for (row = 0; row < 4; row = row + 1)
              angular_temporary[row*4] = clip8(angular_temporary[row*4]
                + ((reference_side[9+row] - reference_side[8]) >>> 1));
          end
          for (row = 0; row < 4; row = row + 1)
            for (column = 0; column < 4; column = column + 1)
              predicted_sample[row*4+column] = vertical_mode != 0
                ? angular_temporary[row*4+column] : angular_temporary[column*4+row];
        end
      end
    endcase

    for (row = 0; row < 16; row = row + 1) residual_sample[row] = source_sample[row] - predicted_sample[row];

    for (row = 0; row < 4; row = row + 1) begin
      for (output_index = 0; output_index < 4; output_index = output_index + 1) begin
        matrix_sum = 0;
        for (column = 0; column < 4; column = column + 1)
          matrix_sum = matrix_sum + residual_sample[row*4+column] * DST[output_index*4+column];
        transform_temporary[output_index*4+row] = (matrix_sum + 1) >>> 1;
      end
    end
    for (row = 0; row < 4; row = row + 1) begin
      for (output_index = 0; output_index < 4; output_index = output_index + 1) begin
        matrix_sum = 0;
        for (column = 0; column < 4; column = column + 1)
          matrix_sum = matrix_sum + transform_temporary[row*4+column] * DST[output_index*4+column];
        transform_sample[output_index*4+row] = (matrix_sum + 128) >>> 8;
      end
    end

    supported = mode <= 34;
    // Unsupported QPs still use bounded defaults so no invalid shift can occur.
    quant_scale = 16384;
    inverse_scale = 64;
    qbits = 22;
    inverse_left_shift = 2;
    case (qp)
      6'd22: begin quant_scale = 16384; inverse_scale = 64; qbits = 22; inverse_left_shift = 2; end
      6'd27: begin quant_scale = 18396; inverse_scale = 57; qbits = 23; inverse_left_shift = 3; end
      6'd32: begin quant_scale = 20560; inverse_scale = 51; qbits = 24; inverse_left_shift = 4; end
      6'd37: begin quant_scale = 23302; inverse_scale = 45; qbits = 25; inverse_left_shift = 5; end
      default: supported = 1'b0;
    endcase
    quant_rounding = 171 <<< (qbits - 9);
    for (row = 0; row < 16; row = row + 1) begin
      magnitude = transform_sample[row] < 0 ? -transform_sample[row] : transform_sample[row];
      product = longint'(magnitude);
      product = product * quant_scale + longint'(quant_rounding);
      magnitude = integer'(product >>> qbits);
      quantized_sample[row] = clip16(transform_sample[row] < 0 ? -longint'(magnitude) : longint'(magnitude));
      product = longint'(quantized_sample[row]);
      product = product * inverse_scale;
      dequantized_sample[row] = clip16(product <<< inverse_left_shift);
    end

    for (row = 0; row < 4; row = row + 1) begin
      for (output_index = 0; output_index < 4; output_index = output_index + 1) begin
        matrix_sum = 0;
        for (column = 0; column < 4; column = column + 1)
          matrix_sum = matrix_sum + dequantized_sample[column*4+row] * DST[column*4+output_index];
        inverse_temporary[row*4+output_index] = clip16((longint'(matrix_sum) + 64) >>> 7);
      end
    end
    for (row = 0; row < 4; row = row + 1) begin
      for (output_index = 0; output_index < 4; output_index = output_index + 1) begin
        matrix_sum = 0;
        for (column = 0; column < 4; column = column + 1)
          matrix_sum = matrix_sum + inverse_temporary[column*4+row] * DST[column*4+output_index];
        inverse_sample[row*4+output_index] = clip16((longint'(matrix_sum) + 2048) >>> 12);
      end
    end

    distortion = '0;
    for (row = 0; row < 16; row = row + 1) begin
      reconstruction_sample[row] = clip8(predicted_sample[row] + inverse_sample[row]);
      error = source_sample[row] - reconstruction_sample[row];
      distortion = distortion + error * error;
      prediction[row*8 +: 8] = 8'(predicted_sample[row]);
      residual[row*9 +: 9] = 9'(residual_sample[row]);
      transformed[row*32 +: 32] = transform_sample[row];
      quantized[row*16 +: 16] = 16'(quantized_sample[row]);
      dequantized[row*16 +: 16] = 16'(dequantized_sample[row]);
      inverse_residual[row*16 +: 16] = 16'(inverse_sample[row]);
      reconstruction[row*8 +: 8] = 8'(reconstruction_sample[row]);
    end
  end
endmodule
