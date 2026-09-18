module full_rdo_pway #(
  parameter integer P = 4,
  parameter integer MAX_CANDIDATES = 35
) (
  input  logic         clk,
  input  logic         rst_n,
  input  logic         start,
  output logic         start_ready,
  input  logic [5:0]   candidate_count,
  input  logic [MAX_CANDIDATES*6-1:0] candidate_modes,
  input  logic [MAX_CANDIDATES*24-1:0] candidate_rate_bits,
  input  logic [5:0]   qp,
  input  logic [31:0]  lambda_q,
  input  logic [135:0] references,
  input  logic [127:0] original,
  output logic [P-1:0] retire_valid,
  input  logic         retire_ready,
  output logic [P-1:0] retire_supported,
  output logic [P-1:0][5:0] retire_rank,
  output logic [P-1:0][5:0] retire_mode,
  output logic [P-1:0][55:0] retire_cost_q,
  output logic         done,
  output logic         winner_supported,
  output logic [5:0]   winner_rank,
  output logic [5:0]   winner_mode,
  output logic [55:0]  winner_cost_q,
  output logic [15:0]  event_cycles,
  output logic [7:0]   batches_model,
  output logic [7:0]   batches_rtl,
  output logic [15:0]  stall_cycles,
  output logic [23:0]  lane_active_cycles
);
  logic active;
  logic [5:0] count_reg;
  logic [MAX_CANDIDATES*6-1:0] modes_reg;
  logic [MAX_CANDIDATES*24-1:0] rates_reg;
  logic [5:0] qp_reg;
  logic [31:0] lambda_reg;
  logic [135:0] references_reg;
  logic [127:0] original_reg;
  logic [6:0] launched_count;
  logic [6:0] completed_count;
  logic [P-1:0] lane_in_valid;
  logic [P-1:0] lane_in_ready;
  logic [P-1:0] lane_out_valid;
  logic [P-1:0] lane_out_supported;
  logic [P-1:0] lane_out_overflow;
  logic [P-1:0][5:0] lane_out_mode;
  logic [P-1:0][55:0] lane_out_cost;
  logic [P-1:0][5:0] lane_rank;
  logic [P-1:0] lane_inflight;
  logic lanes_ready;
  logic launch_batch;
  logic [6:0] launch_increment;
  logic [6:0] completion_increment;
  logic [7:0] lane_active_increment;
  logic reduced_valid;
  logic [5:0] reduced_rank;
  logic [5:0] reduced_mode;
  logic [55:0] reduced_cost;
  logic reduced_better;
  logic best_valid;
  logic [15:0] live_event_cycles;
  logic [7:0] live_batches;
  logic [15:0] live_stalls;
  logic [23:0] live_lane_active_cycles;
  integer lane_comb;
  integer lane_seq;

  assign start_ready = !active;
  assign lanes_ready = &lane_in_ready;
  assign launch_batch = active && lanes_ready && launched_count < {1'b0, count_reg};
  assign retire_valid = lane_out_valid;
  assign retire_supported = lane_out_supported & ~lane_out_overflow;
  assign retire_rank = lane_rank;
  assign retire_mode = lane_out_mode;
  assign retire_cost_q = lane_out_cost;
  assign reduced_better = reduced_valid && (!best_valid || reduced_cost < winner_cost_q
                            || (reduced_cost == winner_cost_q && reduced_rank < winner_rank));

  always_comb begin
    launch_increment = '0;
    completion_increment = '0;
    lane_active_increment = '0;
    reduced_valid = 1'b0;
    reduced_rank = '0;
    reduced_mode = '0;
    reduced_cost = {56{1'b1}};
    for (lane_comb = 0; lane_comb < P; lane_comb = lane_comb + 1) begin
      lane_in_valid[lane_comb] = launch_batch
                         && int'(launched_count) + lane_comb < int'(count_reg);
      if (lane_in_valid[lane_comb]) launch_increment = launch_increment + 1'b1;
      if (lane_inflight[lane_comb] || lane_in_valid[lane_comb])
        lane_active_increment = lane_active_increment + 1'b1;
      if (lane_out_valid[lane_comb] && retire_ready) begin
        completion_increment = completion_increment + 1'b1;
        if (retire_supported[lane_comb] && (!reduced_valid || lane_out_cost[lane_comb] < reduced_cost
            || (lane_out_cost[lane_comb] == reduced_cost && lane_rank[lane_comb] < reduced_rank))) begin
          reduced_valid = 1'b1;
          reduced_rank = lane_rank[lane_comb];
          reduced_mode = lane_out_mode[lane_comb];
          reduced_cost = lane_out_cost[lane_comb];
        end
      end
    end
  end

  generate
    genvar pe;
    for (pe = 0; pe < P; pe = pe + 1) begin : candidate_lanes
      wire [6:0] descriptor_index = launched_count + pe;
      wire [5:0] safe_index = descriptor_index < {1'b0, count_reg} ? descriptor_index[5:0] : 6'd0;
      /* verilator lint_off PINCONNECTEMPTY */
      full_rdo_mvp_4x4 lane_pe (
        .clk(clk), .rst_n(rst_n), .in_valid(lane_in_valid[pe]), .in_ready(lane_in_ready[pe]),
        .in_mode(modes_reg[safe_index*6 +: 6]), .in_qp(qp_reg),
        .in_references(references_reg), .in_original(original_reg),
        .in_rate_bits(rates_reg[safe_index*24 +: 24]), .in_lambda_q(lambda_reg),
        .out_valid(lane_out_valid[pe]), .out_ready(retire_ready),
        .out_supported(lane_out_supported[pe]), .out_mode(lane_out_mode[pe]), .out_qp(),
        .out_prediction(), .out_residual(), .out_transformed(), .out_quantized(),
        .out_dequantized(), .out_inverse_residual(), .out_reconstruction(), .out_distortion(),
        .out_rate_bits(), .out_rd_cost_q(lane_out_cost[pe]), .out_overflow(lane_out_overflow[pe]),
        .out_latency_cycles()
      );
      /* verilator lint_on PINCONNECTEMPTY */
    end
  endgenerate

  always_ff @(posedge clk) begin
    if (!rst_n) begin
      active <= 1'b0;
      count_reg <= '0;
      modes_reg <= '0;
      rates_reg <= '0;
      qp_reg <= '0;
      lambda_reg <= '0;
      references_reg <= '0;
      original_reg <= '0;
      launched_count <= '0;
      completed_count <= '0;
      lane_rank <= '0;
      lane_inflight <= '0;
      done <= 1'b0;
      winner_supported <= 1'b0;
      winner_rank <= '0;
      winner_mode <= '0;
      winner_cost_q <= {56{1'b1}};
      event_cycles <= '0;
      batches_model <= '0;
      batches_rtl <= '0;
      stall_cycles <= '0;
      lane_active_cycles <= '0;
      best_valid <= 1'b0;
      live_event_cycles <= '0;
      live_batches <= '0;
      live_stalls <= '0;
      live_lane_active_cycles <= '0;
    end else begin
      done <= 1'b0;
      if (!active) begin
        if (start && candidate_count > 0 && int'(candidate_count) <= MAX_CANDIDATES
            && (qp == 22 || qp == 27 || qp == 32 || qp == 37)) begin
          active <= 1'b1;
          count_reg <= candidate_count;
          modes_reg <= candidate_modes;
          rates_reg <= candidate_rate_bits;
          qp_reg <= qp;
          lambda_reg <= lambda_q;
          references_reg <= references;
          original_reg <= original;
          launched_count <= '0;
          completed_count <= '0;
          lane_rank <= '0;
          lane_inflight <= '0;
          winner_supported <= 1'b0;
          winner_rank <= '0;
          winner_mode <= '0;
          winner_cost_q <= {56{1'b1}};
          best_valid <= 1'b0;
          live_event_cycles <= '0;
          live_batches <= '0;
          live_stalls <= '0;
          live_lane_active_cycles <= '0;
          batches_model <= 8'((int'(candidate_count) + P - 1) / P);
        end
      end else begin
        live_event_cycles <= live_event_cycles + 1'b1;
        if ((|lane_out_valid) && !retire_ready) live_stalls <= live_stalls + 1'b1;
        live_lane_active_cycles <= live_lane_active_cycles + 24'(lane_active_increment);
        if (launch_batch) begin
          launched_count <= launched_count + launch_increment;
          live_batches <= live_batches + 1'b1;
          for (lane_seq = 0; lane_seq < P; lane_seq = lane_seq + 1) begin
            if (lane_in_valid[lane_seq]) begin
              lane_rank[lane_seq] <= 6'(int'(launched_count) + lane_seq);
              lane_inflight[lane_seq] <= 1'b1;
            end
          end
        end
        if (completion_increment != 0) begin
          completed_count <= completed_count + completion_increment;
          for (lane_seq = 0; lane_seq < P; lane_seq = lane_seq + 1)
            if (lane_out_valid[lane_seq] && retire_ready) lane_inflight[lane_seq] <= 1'b0;
          if (reduced_better) begin
            best_valid <= 1'b1;
            winner_rank <= reduced_rank;
            winner_mode <= reduced_mode;
            winner_cost_q <= reduced_cost;
          end
          if (completed_count + completion_increment == {1'b0, count_reg}) begin
            active <= 1'b0;
            done <= 1'b1;
            winner_supported <= best_valid || reduced_valid;
            if (reduced_better) begin
              winner_rank <= reduced_rank;
              winner_mode <= reduced_mode;
              winner_cost_q <= reduced_cost;
            end
            event_cycles <= live_event_cycles + 1'b1;
            batches_rtl <= live_batches;
            stall_cycles <= live_stalls;
            lane_active_cycles <= live_lane_active_cycles + 24'(lane_active_increment);
          end
        end
      end
    end
  end

  initial begin
    if (P != 1 && P != 2 && P != 4 && P != 8) $fatal(1, "P must be 1, 2, 4, or 8");
  end
endmodule
