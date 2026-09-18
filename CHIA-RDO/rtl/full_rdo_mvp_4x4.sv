module full_rdo_mvp_4x4 (
  input  logic         clk,
  input  logic         rst_n,
  input  logic         in_valid,
  output logic         in_ready,
  input  logic [5:0]   in_mode,
  input  logic [5:0]   in_qp,
  input  logic [135:0] in_references,
  input  logic [127:0] in_original,
  input  logic [23:0]  in_rate_bits,
  input  logic [31:0]  in_lambda_q,
  output logic         out_valid,
  input  logic         out_ready,
  output logic         out_supported,
  output logic [5:0]   out_mode,
  output logic [5:0]   out_qp,
  output logic [127:0] out_prediction,
  output logic [143:0] out_residual,
  output logic [511:0] out_transformed,
  output logic [255:0] out_quantized,
  output logic [255:0] out_dequantized,
  output logic [255:0] out_inverse_residual,
  output logic [127:0] out_reconstruction,
  output logic [31:0]  out_distortion,
  output logic [23:0]  out_rate_bits,
  output logic [55:0]  out_rd_cost_q,
  output logic         out_overflow,
  output logic [7:0]   out_latency_cycles
);
  logic codec_supported;
  logic [127:0] codec_prediction;
  logic [143:0] codec_residual;
  logic [511:0] codec_transformed;
  logic [255:0] codec_quantized;
  logic [255:0] codec_dequantized;
  logic [255:0] codec_inverse_residual;
  logic [127:0] codec_reconstruction;
  logic [31:0] codec_distortion;
  logic busy;
  logic launch_pending;
  logic rd_in_ready;
  logic rd_out_valid;
  logic [31:0] lambda_reg;
  logic [5:0] mode_reg;

  full_rdo_codec_4x4 codec (
    .references(in_references), .original(in_original), .mode(in_mode), .qp(in_qp),
    .supported(codec_supported), .prediction(codec_prediction), .residual(codec_residual),
    .transformed(codec_transformed), .quantized(codec_quantized), .dequantized(codec_dequantized),
    .inverse_residual(codec_inverse_residual), .reconstruction(codec_reconstruction),
    .distortion(codec_distortion)
  );

  rdo_pe #(.PIPELINE_DEPTH(2), .COST_WIDTH(56)) rd_cost (
    .clk(clk), .rst_n(rst_n), .in_valid(launch_pending), .in_ready(rd_in_ready),
    .in_candidate_id(mode_reg), .in_distortion(out_distortion), .in_rate_bits(out_rate_bits),
    .in_lambda_q(lambda_reg), .out_valid(rd_out_valid), .out_ready(out_ready),
    .out_candidate_id(out_mode), .out_rd_cost_q(out_rd_cost_q), .out_overflow(out_overflow)
  );

  assign in_ready = !busy;
  assign out_valid = rd_out_valid;
  assign out_latency_cycles = 8'd2;

  always_ff @(posedge clk) begin
    if (!rst_n) begin
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
    end else begin
      if (in_valid && in_ready) begin
        busy <= 1'b1;
        launch_pending <= 1'b1;
        out_supported <= codec_supported;
        mode_reg <= in_mode;
        out_qp <= in_qp;
        out_prediction <= codec_prediction;
        out_residual <= codec_residual;
        out_transformed <= codec_transformed;
        out_quantized <= codec_quantized;
        out_dequantized <= codec_dequantized;
        out_inverse_residual <= codec_inverse_residual;
        out_reconstruction <= codec_reconstruction;
        out_distortion <= codec_distortion;
        out_rate_bits <= in_rate_bits;
        lambda_reg <= in_lambda_q;
      end
      if (launch_pending && rd_in_ready) launch_pending <= 1'b0;
      if (rd_out_valid && out_ready) busy <= 1'b0;
    end
  end
endmodule
