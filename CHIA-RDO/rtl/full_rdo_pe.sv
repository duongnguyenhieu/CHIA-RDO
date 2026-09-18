module full_rdo_pe #(
  parameter integer MAX_CANDIDATES = 4
) (
  input  logic         clk,
  input  logic         rst_n,
  input  logic         start,
  output logic         start_ready,
  input  logic [5:0]   block_size,
  input  logic [2:0]   candidate_count,
  input  logic [MAX_CANDIDATES*6-1:0] candidate_modes,
  input  logic [MAX_CANDIDATES*24-1:0] candidate_rate_bits,
  input  logic [5:0]   qp,
  input  logic [31:0]  lambda_q,
  input  logic [135:0] references,
  input  logic [127:0] original,
  output logic         candidate_valid,
  input  logic         candidate_ready,
  output logic         candidate_supported,
  output logic [1:0]   candidate_rank,
  output logic [5:0]   candidate_mode,
  output logic [5:0]   candidate_qp,
  output logic [127:0] candidate_prediction,
  output logic [143:0] candidate_residual,
  output logic [511:0] candidate_transformed,
  output logic [255:0] candidate_quantized,
  output logic [255:0] candidate_dequantized,
  output logic [255:0] candidate_inverse_residual,
  output logic [127:0] candidate_reconstruction,
  output logic [31:0]  candidate_distortion,
  output logic [23:0]  candidate_bits,
  output logic [55:0]  candidate_cost_q,
  output logic         done,
  output logic         winner_supported,
  output logic [1:0]   winner_rank,
  output logic [5:0]   winner_mode,
  output logic [55:0]  winner_cost_q,
  output logic [15:0]  group_cycles,
  output logic [15:0]  stall_cycles,
  output logic [15:0]  pe_active_cycles,
  output logic [7:0]   candidate_latency_cycles,
  output logic [7:0]   candidate_launch_interval,
  output logic [7:0]   comparator_latency_cycles
);
  logic active;
  logic [2:0] count_reg;
  logic [2:0] launched_count;
  logic [2:0] completed_count;
  logic [1:0] launch_index;
  logic [MAX_CANDIDATES*6-1:0] modes_reg;
  logic [MAX_CANDIDATES*24-1:0] rates_reg;
  logic [5:0] qp_reg;
  logic [31:0] lambda_reg;
  logic [135:0] references_reg;
  logic [127:0] original_reg;
  logic pe_in_valid;
  logic pe_in_ready;
  logic pe_out_valid;
  logic pe_out_supported;
  logic [5:0] pe_out_mode;
  logic pe_out_overflow;
  logic [7:0] pe_latency;
  logic candidate_inflight;
  logic best_valid;
  logic [15:0] live_group_cycles;
  logic [15:0] live_stall_cycles;
  logic [15:0] live_pe_active_cycles;
  logic retiring_better;
  logic start_supported;

  assign start_ready = !active;
  assign start_supported = block_size == 4 && candidate_count > 0
                        && int'(candidate_count) <= MAX_CANDIDATES
                        && (qp == 22 || qp == 27 || qp == 32 || qp == 37);
  assign pe_in_valid = active && launched_count < count_reg;
  assign launch_index = launched_count < count_reg ? launched_count[1:0] : 2'd0;
  assign candidate_valid = pe_out_valid;
  assign candidate_supported = pe_out_supported && !pe_out_overflow;
  assign retiring_better = candidate_supported && (!best_valid || candidate_cost_q < winner_cost_q);
  assign candidate_latency_cycles = pe_latency;
  assign candidate_launch_interval = 8'd4;
  assign comparator_latency_cycles = 8'd1;

  full_rdo_mvp_4x4 candidate_pe (
    .clk(clk), .rst_n(rst_n), .in_valid(pe_in_valid), .in_ready(pe_in_ready),
    .in_mode(modes_reg[launch_index*6 +: 6]), .in_qp(qp_reg),
    .in_references(references_reg), .in_original(original_reg),
    .in_rate_bits(rates_reg[launch_index*24 +: 24]), .in_lambda_q(lambda_reg),
    .out_valid(pe_out_valid), .out_ready(candidate_ready), .out_supported(pe_out_supported),
    .out_mode(pe_out_mode), .out_qp(candidate_qp), .out_prediction(candidate_prediction),
    .out_residual(candidate_residual), .out_transformed(candidate_transformed),
    .out_quantized(candidate_quantized), .out_dequantized(candidate_dequantized),
    .out_inverse_residual(candidate_inverse_residual), .out_reconstruction(candidate_reconstruction),
    .out_distortion(candidate_distortion), .out_rate_bits(candidate_bits),
    .out_rd_cost_q(candidate_cost_q), .out_overflow(pe_out_overflow),
    .out_latency_cycles(pe_latency)
  );

  assign candidate_mode = pe_out_mode;

  always_ff @(posedge clk) begin
    if (!rst_n) begin
      active <= 1'b0;
      count_reg <= '0;
      launched_count <= '0;
      completed_count <= '0;
      modes_reg <= '0;
      rates_reg <= '0;
      qp_reg <= '0;
      lambda_reg <= '0;
      references_reg <= '0;
      original_reg <= '0;
      candidate_rank <= '0;
      candidate_inflight <= 1'b0;
      best_valid <= 1'b0;
      done <= 1'b0;
      winner_supported <= 1'b0;
      winner_rank <= '0;
      winner_mode <= '0;
      winner_cost_q <= {56{1'b1}};
      group_cycles <= '0;
      stall_cycles <= '0;
      pe_active_cycles <= '0;
      live_group_cycles <= '0;
      live_stall_cycles <= '0;
      live_pe_active_cycles <= '0;
    end else begin
      done <= 1'b0;
      if (!active) begin
        if (start) begin
          if (start_supported) begin
            active <= 1'b1;
            count_reg <= candidate_count;
            launched_count <= '0;
            completed_count <= '0;
            modes_reg <= candidate_modes;
            rates_reg <= candidate_rate_bits;
            qp_reg <= qp;
            lambda_reg <= lambda_q;
            references_reg <= references;
            original_reg <= original;
            candidate_rank <= '0;
            candidate_inflight <= 1'b0;
            best_valid <= 1'b0;
            winner_supported <= 1'b0;
            winner_rank <= '0;
            winner_mode <= '0;
            winner_cost_q <= {56{1'b1}};
            live_group_cycles <= '0;
            live_stall_cycles <= '0;
            live_pe_active_cycles <= '0;
          end else begin
            done <= 1'b1;
            winner_supported <= 1'b0;
            group_cycles <= '0;
            stall_cycles <= '0;
            pe_active_cycles <= '0;
          end
        end
      end else begin
        live_group_cycles <= live_group_cycles + 1'b1;
        if (candidate_valid && !candidate_ready)
          live_stall_cycles <= live_stall_cycles + 1'b1;
        if (candidate_inflight || (pe_in_valid && pe_in_ready))
          live_pe_active_cycles <= live_pe_active_cycles + 1'b1;
        if (pe_in_valid && pe_in_ready) begin
          candidate_inflight <= 1'b1;
          launched_count <= launched_count + 1'b1;
        end
        if (candidate_valid && candidate_ready) begin
          candidate_inflight <= 1'b0;
          if (retiring_better) begin
            best_valid <= 1'b1;
            winner_rank <= candidate_rank;
            winner_mode <= candidate_mode;
            winner_cost_q <= candidate_cost_q;
          end
          completed_count <= completed_count + 1'b1;
          if (completed_count + 1'b1 == count_reg) begin
            active <= 1'b0;
            done <= 1'b1;
            winner_supported <= best_valid || candidate_supported;
            if (retiring_better) begin
              winner_rank <= candidate_rank;
              winner_mode <= candidate_mode;
              winner_cost_q <= candidate_cost_q;
            end
            group_cycles <= live_group_cycles + 1'b1;
            stall_cycles <= live_stall_cycles + (candidate_valid && !candidate_ready);
            pe_active_cycles <= live_pe_active_cycles + 1'b1;
          end else begin
            candidate_rank <= candidate_rank + 1'b1;
          end
        end
      end
    end
  end

  initial begin
    if (MAX_CANDIDATES != 4) $fatal(1, "Phase-5.2 Full-RDO PE requires MAX_CANDIDATES=4");
  end
endmodule
