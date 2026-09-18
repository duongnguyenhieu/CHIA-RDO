module full_rdo_mvp_4x4_serial #(
  parameter integer TRANSFORM_PARALLELISM = 1,
  parameter integer QUANT_PARALLELISM = 1,
  parameter integer MULTIPLIER_MODE = 0,
  parameter integer COST_WIDTH = 56,
  parameter integer PIPELINE_DEPTH = 2
) (
  input  logic                  clk,
  input  logic                  rst_n,
  input  logic                  in_valid,
  output logic                  in_ready,
  input  logic [5:0]            in_mode,
  input  logic [5:0]            in_qp,
  input  logic [135:0]          in_references,
  input  logic [127:0]          in_original,
  input  logic [23:0]           in_rate_bits,
  input  logic [31:0]           in_lambda_q,
  output logic                  out_valid,
  input  logic                  out_ready,
  output logic                  out_supported,
  output logic [5:0]            out_mode,
  output logic [5:0]            out_qp,
  output logic [127:0]          out_prediction,
  output logic [143:0]          out_residual,
  output logic [511:0]          out_transformed,
  output logic [255:0]          out_quantized,
  output logic [255:0]          out_dequantized,
  output logic [255:0]          out_inverse_residual,
  output logic [127:0]          out_reconstruction,
  output logic [31:0]           out_distortion,
  output logic [23:0]           out_rate_bits,
  output logic [COST_WIDTH-1:0] out_rd_cost_q,
  output logic                  out_overflow,
  output logic [7:0]            out_latency_cycles
);
  typedef enum logic [3:0] {
    IDLE, PRED_SETUP, PREDICT, FORWARD_1, FORWARD_2, QUANTIZE, DEQUANTIZE,
    INVERSE_1, INVERSE_2, RECONSTRUCT, WAIT_COST
  } state_t;

  // The first implementation shares one 4-tap transform dot-product and one
  // quant/dequant coefficient datapath across all sixteen block positions.
  localparam integer MULTIPLIER_SERIAL_DSP = 0;
  localparam integer PRED_SETUP_CYCLES = 1;
  localparam integer PREDICT_CYCLES = 16;
  localparam integer TRANSFORM_PASS_CYCLES = 16;
  localparam integer QUANTIZE_CYCLES = 16;
  localparam logic SPLIT_QUANT_DEQUANT = PIPELINE_DEPTH >= 3;
  localparam integer RECONSTRUCT_CYCLES = 16;
  localparam integer CODEC_CYCLES = PRED_SETUP_CYCLES + PREDICT_CYCLES
                                  + 4 * TRANSFORM_PASS_CYCLES
                                  + QUANTIZE_CYCLES + RECONSTRUCT_CYCLES
                                  + (SPLIT_QUANT_DEQUANT ? QUANTIZE_CYCLES : 0);
  localparam integer TOTAL_LATENCY_CYCLES = CODEC_CYCLES + PIPELINE_DEPTH;

  state_t state;
  logic busy;
  logic launch_pending;
  logic rd_in_ready;
  logic rd_out_valid;
  logic [5:0] mode_reg;
  logic [31:0] lambda_reg;
  logic signed [31:0] ref_sample [0:16];
  logic signed [31:0] source_sample [0:15];
  logic signed [31:0] predicted_sample [0:15];
  logic signed [31:0] residual_sample [0:15];
  logic signed [31:0] transform_temporary [0:15];
  logic signed [31:0] transform_sample [0:15];
  logic signed [31:0] quantized_sample [0:15];
  logic signed [31:0] dequantized_sample [0:15];
  logic signed [31:0] inverse_temporary [0:15];
  logic signed [31:0] inverse_sample [0:15];
  logic signed [31:0] reference_main [0:24];
  logic signed [31:0] dc_value;
  logic vertical_mode;
  logic signed [31:0] prediction_angle;
  logic [3:0] sample_index;
  logic [3:0] transform_index;
  logic [31:0] distortion_accumulator;
  integer quant_scale;
  integer inverse_scale;
  integer qbits;
  integer quant_rounding;
  integer inverse_left_shift;
  integer reset_index;

  function automatic integer dst(input integer row, input integer column);
    case (row * 4 + column)
      0: dst = 29;  1: dst = 55;   2: dst = 74;   3: dst = 84;
      4: dst = 74;  5: dst = 74;   6: dst = 0;    7: dst = -74;
      8: dst = 84;  9: dst = -29; 10: dst = -74; 11: dst = 55;
      12: dst = 55; 13: dst = -84; 14: dst = 74; 15: dst = -29;
      default: dst = 0;
    endcase
  endfunction

  function automatic integer angle(input integer absolute_mode);
    case (absolute_mode)
      0: angle = 0; 1: angle = 2; 2: angle = 5; 3: angle = 9; 4: angle = 13;
      5: angle = 17; 6: angle = 21; 7: angle = 26; 8: angle = 32;
      default: angle = 0;
    endcase
  endfunction

  function automatic integer inverse_angle(input integer absolute_mode);
    case (absolute_mode)
      0: inverse_angle = 0; 1: inverse_angle = 4096; 2: inverse_angle = 1638;
      3: inverse_angle = 910; 4: inverse_angle = 630; 5: inverse_angle = 482;
      6: inverse_angle = 390; 7: inverse_angle = 315; 8: inverse_angle = 256;
      default: inverse_angle = 0;
    endcase
  endfunction

  function automatic integer clip8(input longint signed value);
    if (value < 0) clip8 = 0;
    else if (value > 255) clip8 = 255;
    else clip8 = integer'(value);
  endfunction

  function automatic integer clip16(input longint signed value);
    if (value < -32768) clip16 = -32768;
    else if (value > 32767) clip16 = 32767;
    else clip16 = integer'(value);
  endfunction

  function automatic integer prediction_for(input integer index);
    integer row;
    integer column;
    integer angular_row;
    integer angular_column;
    integer delta_position;
    integer delta_integer;
    integer delta_fraction;
    integer first_reference;
    integer second_reference;
    integer value;
    begin
      row = index / 4;
      column = index % 4;
      value = dc_value;
      case (mode_reg)
        6'd0: value = ((3-column)*ref_sample[9+row] + (column+1)*ref_sample[5]
                    + (3-row)*ref_sample[1+column] + (row+1)*ref_sample[13] + 4) >>> 3;
        6'd1: begin
          if (row == 0 && column == 0)
            value = (ref_sample[1] + ref_sample[9] + 2*dc_value + 2) >>> 2;
          else if (row == 0)
            value = (ref_sample[1+column] + 3*dc_value + 2) >>> 2;
          else if (column == 0)
            value = (ref_sample[9+row] + 3*dc_value + 2) >>> 2;
        end
        6'd10: begin
          value = ref_sample[9+row];
          if (row == 0)
            value = clip8(ref_sample[9] + ((ref_sample[1+column] - ref_sample[0]) >>> 1));
        end
        6'd26: begin
          value = ref_sample[1+column];
          if (column == 0)
            value = clip8(ref_sample[1] + ((ref_sample[9+row] - ref_sample[0]) >>> 1));
        end
        default: begin
          if (mode_reg <= 34) begin
            angular_row = vertical_mode ? row : column;
            angular_column = vertical_mode ? column : row;
            delta_position = (angular_row + 1) * prediction_angle;
            delta_integer = delta_position >>> 5;
            delta_fraction = delta_position & 31;
            first_reference = reference_main[8+angular_column+delta_integer+1];
            if (delta_fraction != 0) begin
              second_reference = reference_main[8+angular_column+delta_integer+2];
              value = ((32-delta_fraction)*first_reference
                     + delta_fraction*second_reference + 16) >>> 5;
            end else value = first_reference;
            if (prediction_angle == 0 && angular_column == 0) begin
              if (vertical_mode)
                value = clip8(value + ((ref_sample[9+angular_row] - ref_sample[0]) >>> 1));
              else
                value = clip8(value + ((ref_sample[1+angular_row] - ref_sample[0]) >>> 1));
            end
          end
        end
      endcase
      prediction_for = value;
    end
  endfunction

  rdo_pe #(.PIPELINE_DEPTH(PIPELINE_DEPTH), .COST_WIDTH(COST_WIDTH)) rd_cost (
    .clk(clk), .rst_n(rst_n), .in_valid(launch_pending), .in_ready(rd_in_ready),
    .in_candidate_id(mode_reg), .in_distortion(out_distortion), .in_rate_bits(out_rate_bits),
    .in_lambda_q(lambda_reg), .out_valid(rd_out_valid), .out_ready(out_ready),
    .out_candidate_id(out_mode), .out_rd_cost_q(out_rd_cost_q), .out_overflow(out_overflow)
  );

  assign in_ready = !busy;
  assign out_valid = rd_out_valid;
  assign out_latency_cycles = 8'(TOTAL_LATENCY_CYCLES);

  always_ff @(posedge clk) begin : serial_datapath
    integer row;
    integer column;
    integer output_index;
    integer absolute_angle_mode;
    integer inverse_angle_sum;
    integer signed_angle_mode;
    integer dc_sum;
    integer predicted_value;
    integer residual_value;
    integer magnitude;
    integer error;
    integer reconstructed_value;
    longint signed sum;
    longint signed product;
    if (!rst_n) begin
      state <= IDLE;
      busy <= 1'b0;
      launch_pending <= 1'b0;
      out_supported <= 1'b0;
      mode_reg <= '0;
      out_qp <= '0;
      out_prediction <= '0;
      out_residual <= '0;
      out_transformed <= '0;
      out_quantized <= '0;
      out_dequantized <= '0;
      out_inverse_residual <= '0;
      out_reconstruction <= '0;
      out_distortion <= '0;
      out_rate_bits <= '0;
      lambda_reg <= '0;
      sample_index <= '0;
      transform_index <= '0;
      distortion_accumulator <= '0;
      dc_value <= '0;
      vertical_mode <= 1'b0;
      prediction_angle <= '0;
      quant_scale <= 16384;
      inverse_scale <= 64;
      qbits <= 22;
      quant_rounding <= 171 <<< 13;
      inverse_left_shift <= 2;
      for (reset_index = 0; reset_index < 25; reset_index = reset_index + 1)
        reference_main[reset_index] <= '0;
    end else begin
      if (launch_pending && rd_in_ready) launch_pending <= 1'b0;
      case (state)
        IDLE: begin
          if (in_valid && in_ready) begin
            busy <= 1'b1;
            mode_reg <= in_mode;
            out_qp <= in_qp;
            out_rate_bits <= in_rate_bits;
            lambda_reg <= in_lambda_q;
            out_supported <= in_mode <= 34
                          && (in_qp == 22 || in_qp == 27 || in_qp == 32 || in_qp == 37);
            out_prediction <= '0;
            out_residual <= '0;
            out_transformed <= '0;
            out_quantized <= '0;
            out_dequantized <= '0;
            out_inverse_residual <= '0;
            out_reconstruction <= '0;
            out_distortion <= '0;
            for (reset_index = 0; reset_index < 17; reset_index = reset_index + 1)
              ref_sample[reset_index] <= $signed({1'b0, in_references[reset_index*8 +: 8]});
            for (reset_index = 0; reset_index < 16; reset_index = reset_index + 1)
              source_sample[reset_index] <= $signed({1'b0, in_original[reset_index*8 +: 8]});
            case (in_qp)
              6'd22: begin quant_scale <= 16384; inverse_scale <= 64; qbits <= 22;
                             quant_rounding <= 171 <<< 13; inverse_left_shift <= 2; end
              6'd27: begin quant_scale <= 18396; inverse_scale <= 57; qbits <= 23;
                             quant_rounding <= 171 <<< 14; inverse_left_shift <= 3; end
              6'd32: begin quant_scale <= 20560; inverse_scale <= 51; qbits <= 24;
                             quant_rounding <= 171 <<< 15; inverse_left_shift <= 4; end
              6'd37: begin quant_scale <= 23302; inverse_scale <= 45; qbits <= 25;
                             quant_rounding <= 171 <<< 16; inverse_left_shift <= 5; end
              default: begin quant_scale <= 16384; inverse_scale <= 64; qbits <= 22;
                               quant_rounding <= 171 <<< 13; inverse_left_shift <= 2; end
            endcase
            state <= PRED_SETUP;
          end
        end

        PRED_SETUP: begin
          dc_sum = 4;
          for (column = 1; column <= 4; column = column + 1)
            dc_sum = dc_sum + ref_sample[column];
          for (row = 9; row <= 12; row = row + 1)
            dc_sum = dc_sum + ref_sample[row];
          dc_value <= dc_sum >>> 3;
          vertical_mode <= mode_reg >= 18;
          signed_angle_mode = mode_reg >= 18 ? integer'(mode_reg) - 26
                                             : -(integer'(mode_reg) - 10);
          absolute_angle_mode = signed_angle_mode < 0 ? -signed_angle_mode : signed_angle_mode;
          prediction_angle <= (signed_angle_mode < 0 ? -1 : 1) * angle(absolute_angle_mode);
          for (reset_index = 0; reset_index < 25; reset_index = reset_index + 1)
            reference_main[reset_index] <= '0;
          reference_main[8] <= ref_sample[0];
          for (reset_index = 1; reset_index <= 8; reset_index = reset_index + 1)
            reference_main[8+reset_index] <= mode_reg >= 18
              ? ref_sample[reset_index] : ref_sample[8+reset_index];
          if (((signed_angle_mode < 0 ? -1 : 1) * angle(absolute_angle_mode)) < 0) begin
            inverse_angle_sum = 128;
            if (-1 > ((4 * ((signed_angle_mode < 0 ? -1 : 1)
                       * angle(absolute_angle_mode))) >>> 5)) begin
              inverse_angle_sum = inverse_angle_sum + inverse_angle(absolute_angle_mode);
              reference_main[7] <= mode_reg >= 18
                ? ref_sample[8+(inverse_angle_sum >>> 8)]
                : ref_sample[inverse_angle_sum >>> 8];
            end
            if (-2 > ((4 * ((signed_angle_mode < 0 ? -1 : 1)
                       * angle(absolute_angle_mode))) >>> 5)) begin
              inverse_angle_sum = inverse_angle_sum + inverse_angle(absolute_angle_mode);
              reference_main[6] <= mode_reg >= 18
                ? ref_sample[8+(inverse_angle_sum >>> 8)]
                : ref_sample[inverse_angle_sum >>> 8];
            end
            if (-3 > ((4 * ((signed_angle_mode < 0 ? -1 : 1)
                       * angle(absolute_angle_mode))) >>> 5)) begin
              inverse_angle_sum = inverse_angle_sum + inverse_angle(absolute_angle_mode);
              reference_main[5] <= mode_reg >= 18
                ? ref_sample[8+(inverse_angle_sum >>> 8)]
                : ref_sample[inverse_angle_sum >>> 8];
            end
            if (-4 > ((4 * ((signed_angle_mode < 0 ? -1 : 1)
                       * angle(absolute_angle_mode))) >>> 5)) begin
              inverse_angle_sum = inverse_angle_sum + inverse_angle(absolute_angle_mode);
              reference_main[4] <= mode_reg >= 18
                ? ref_sample[8+(inverse_angle_sum >>> 8)]
                : ref_sample[inverse_angle_sum >>> 8];
            end
          end
          sample_index <= '0;
          state <= PREDICT;
        end

        PREDICT: begin
          predicted_value = prediction_for(sample_index);
          residual_value = source_sample[sample_index] - predicted_value;
          predicted_sample[sample_index] <= predicted_value;
          residual_sample[sample_index] <= residual_value;
          out_prediction[sample_index*8 +: 8] <= 8'(predicted_value);
          out_residual[sample_index*9 +: 9] <= 9'(residual_value);
          if (sample_index == 15) begin
            transform_index <= '0;
            state <= FORWARD_1;
          end else sample_index <= sample_index + 1'b1;
        end

        FORWARD_1: begin
          row = transform_index / 4;
          output_index = transform_index % 4;
          sum = 0;
          for (column = 0; column < 4; column = column + 1)
            sum = sum + longint'(residual_sample[row*4+column]) * dst(output_index, column);
          transform_temporary[output_index*4+row] <= integer'((sum + 1) >>> 1);
          if (transform_index == 15) begin
            transform_index <= '0;
            state <= FORWARD_2;
          end else transform_index <= transform_index + 1'b1;
        end

        FORWARD_2: begin
          row = transform_index / 4;
          output_index = transform_index % 4;
          sum = 0;
          for (column = 0; column < 4; column = column + 1)
            sum = sum + longint'(transform_temporary[row*4+column]) * dst(output_index, column);
          transform_sample[output_index*4+row] <= integer'((sum + 128) >>> 8);
          out_transformed[(output_index*4+row)*32 +: 32] <= 32'((sum + 128) >>> 8);
          if (transform_index == 15) begin
            sample_index <= '0;
            state <= QUANTIZE;
          end else transform_index <= transform_index + 1'b1;
        end

        QUANTIZE: begin
          magnitude = transform_sample[sample_index] < 0
                    ? integer'(-longint'(transform_sample[sample_index]))
                    : integer'(transform_sample[sample_index]);
          product = longint'(magnitude) * quant_scale + longint'(quant_rounding);
          magnitude = integer'(product >>> qbits);
          quantized_sample[sample_index] <= clip16(transform_sample[sample_index] < 0
                                             ? -longint'(magnitude) : longint'(magnitude));
          out_quantized[sample_index*16 +: 16] <= 16'(clip16(transform_sample[sample_index] < 0
                                                      ? -longint'(magnitude) : longint'(magnitude)));
          if (sample_index == 15) begin
            if (SPLIT_QUANT_DEQUANT) begin
              sample_index <= '0;
              state <= DEQUANTIZE;
            end else begin
              transform_index <= '0;
              state <= INVERSE_1;
            end
          end else sample_index <= sample_index + 1'b1;
          if (!SPLIT_QUANT_DEQUANT) begin
            product = longint'(clip16(transform_sample[sample_index] < 0
                               ? -longint'(magnitude) : longint'(magnitude))) * inverse_scale;
            dequantized_sample[sample_index] <= clip16(product <<< inverse_left_shift);
            out_dequantized[sample_index*16 +: 16] <= 16'(clip16(product <<< inverse_left_shift));
          end
        end

        DEQUANTIZE: begin
          product = longint'(quantized_sample[sample_index]) * inverse_scale;
          dequantized_sample[sample_index] <= clip16(product <<< inverse_left_shift);
          out_dequantized[sample_index*16 +: 16] <= 16'(clip16(product <<< inverse_left_shift));
          if (sample_index == 15) begin
            transform_index <= '0;
            state <= INVERSE_1;
          end else sample_index <= sample_index + 1'b1;
        end

        INVERSE_1: begin
          row = transform_index / 4;
          output_index = transform_index % 4;
          sum = 0;
          for (column = 0; column < 4; column = column + 1)
            sum = sum + longint'(dequantized_sample[column*4+row]) * dst(column, output_index);
          inverse_temporary[row*4+output_index] <= clip16((sum + 64) >>> 7);
          if (transform_index == 15) begin
            transform_index <= '0;
            state <= INVERSE_2;
          end else transform_index <= transform_index + 1'b1;
        end

        INVERSE_2: begin
          row = transform_index / 4;
          output_index = transform_index % 4;
          sum = 0;
          for (column = 0; column < 4; column = column + 1)
            sum = sum + longint'(inverse_temporary[column*4+row]) * dst(column, output_index);
          inverse_sample[row*4+output_index] <= clip16((sum + 2048) >>> 12);
          out_inverse_residual[(row*4+output_index)*16 +: 16] <= 16'(clip16((sum + 2048) >>> 12));
          if (transform_index == 15) begin
            sample_index <= '0;
            distortion_accumulator <= '0;
            state <= RECONSTRUCT;
          end else transform_index <= transform_index + 1'b1;
        end

        RECONSTRUCT: begin
          reconstructed_value = clip8(longint'(predicted_sample[sample_index])
                                    + longint'(inverse_sample[sample_index]));
          error = source_sample[sample_index] - reconstructed_value;
          out_reconstruction[sample_index*8 +: 8] <= 8'(reconstructed_value);
          distortion_accumulator <= distortion_accumulator + 32'(error * error);
          if (sample_index == 15) begin
            out_distortion <= distortion_accumulator + 32'(error * error);
            launch_pending <= 1'b1;
            state <= WAIT_COST;
          end else sample_index <= sample_index + 1'b1;
        end

        WAIT_COST: begin
          if (rd_out_valid && out_ready) begin
            busy <= 1'b0;
            state <= IDLE;
          end
        end

        default: state <= IDLE;
      endcase
    end
  end

  initial begin
    if (TRANSFORM_PARALLELISM != 1)
      $fatal(1, "only TRANSFORM_PARALLELISM=1 is supported");
    if (QUANT_PARALLELISM != 1)
      $fatal(1, "only QUANT_PARALLELISM=1 is supported");
    if (MULTIPLIER_MODE != MULTIPLIER_SERIAL_DSP)
      $fatal(1, "only MULTIPLIER_MODE=0 (serial DSP) is supported");
    if (PIPELINE_DEPTH < 1) $fatal(1, "PIPELINE_DEPTH must be positive");
    if (COST_WIDTH < 1 || COST_WIDTH > 56) $fatal(1, "COST_WIDTH must be in 1..56");
    if (TOTAL_LATENCY_CYCLES > 255)
      $fatal(1, "PIPELINE_DEPTH does not fit the 8-bit latency interface");
  end
endmodule
