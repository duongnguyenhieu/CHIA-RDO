module rdo_array #(
  parameter int P = 4,
  parameter int PIPELINE_DEPTH = 2,
  parameter int COST_WIDTH = 56,
  parameter int MAX_CANDIDATES = 35
) (
  input  logic                     clk,
  input  logic                     rst_n,
  input  logic                     start,
  input  logic [5:0]               candidate_count,
  input  logic [P-1:0]             candidate_valid,
  output logic                     candidate_ready,
  input  logic [P-1:0][5:0]        candidate_id,
  input  logic [P-1:0][31:0]       candidate_distortion,
  input  logic [P-1:0][23:0]       candidate_rate_bits,
  input  logic [P-1:0][31:0]       candidate_lambda_q,
  output logic                     done,
  output logic [5:0]               best_id,
  output logic [COST_WIDTH-1:0]    best_cost,
  output logic                     overflow_seen
);
  logic active;
  logic [6:0] launched_count;
  logic [6:0] completed_count;
  logic [P-1:0] pe_ready;
  logic [P-1:0] pe_in_valid;
  logic [P-1:0] pe_out_valid;
  logic [P-1:0][5:0] pe_out_id;
  logic [P-1:0][COST_WIDTH-1:0] pe_out_cost;
  logic [P-1:0] pe_out_overflow;
  logic [6:0] launch_increment;
  logic [6:0] completion_increment;
  logic [5:0] reduced_id;
  logic [COST_WIDTH-1:0] reduced_cost;
  logic [COST_WIDTH-1:0] lane_min_cost;
  logic [5:0] lane_min_id;
  integer lane;

  assign candidate_ready = active && (&pe_ready) && launched_count < {1'b0, candidate_count};

  always_comb begin
    launch_increment = '0;
    completion_increment = '0;
    reduced_id = best_id;
    reduced_cost = best_cost;
    for (lane = 0; lane < P; lane = lane + 1) begin
      if (pe_in_valid[lane]) launch_increment = launch_increment + 1'b1;
      if (pe_out_valid[lane]) completion_increment = completion_increment + 1'b1;
    end
    if (lane_min_cost < reduced_cost) begin
      reduced_cost = lane_min_cost;
      reduced_id = lane_min_id;
    end
  end

  generate
    genvar pe;
    for (pe = 0; pe < P; pe = pe + 1) begin : rdo_lanes
      assign pe_in_valid[pe] = candidate_ready && candidate_valid[pe]
                              && launched_count + pe < {1'b0, candidate_count};
      rdo_pe #(.COST_WIDTH(COST_WIDTH), .PIPELINE_DEPTH(PIPELINE_DEPTH)) lane_pe (
        .clk(clk), .rst_n(rst_n),
        .in_valid(pe_in_valid[pe]), .in_ready(pe_ready[pe]),
        .in_candidate_id(candidate_id[pe]), .in_distortion(candidate_distortion[pe]),
        .in_rate_bits(candidate_rate_bits[pe]), .in_lambda_q(candidate_lambda_q[pe]),
        .out_valid(pe_out_valid[pe]), .out_ready(1'b1), .out_candidate_id(pe_out_id[pe]),
        .out_rd_cost_q(pe_out_cost[pe]), .out_overflow(pe_out_overflow[pe])
      );
    end
    if (P == 1) begin : reduction_p1
      assign lane_min_cost = pe_out_valid[0] ? pe_out_cost[0] : {COST_WIDTH{1'b1}};
      assign lane_min_id = pe_out_id[0];
    end else if (P == 2) begin : reduction_p2
      wire choose_left = !pe_out_valid[1] || (pe_out_valid[0] && pe_out_cost[0] <= pe_out_cost[1]);
      assign lane_min_cost = choose_left ? (pe_out_valid[0] ? pe_out_cost[0] : {COST_WIDTH{1'b1}}) : pe_out_cost[1];
      assign lane_min_id = choose_left ? pe_out_id[0] : pe_out_id[1];
    end else if (P == 4) begin : reduction_p4
      wire choose_01 = !pe_out_valid[1] || (pe_out_valid[0] && pe_out_cost[0] <= pe_out_cost[1]);
      wire choose_23 = !pe_out_valid[3] || (pe_out_valid[2] && pe_out_cost[2] <= pe_out_cost[3]);
      wire [COST_WIDTH-1:0] cost_01 = choose_01 ? (pe_out_valid[0] ? pe_out_cost[0] : {COST_WIDTH{1'b1}}) : pe_out_cost[1];
      wire [COST_WIDTH-1:0] cost_23 = choose_23 ? (pe_out_valid[2] ? pe_out_cost[2] : {COST_WIDTH{1'b1}}) : pe_out_cost[3];
      assign lane_min_cost = cost_01 <= cost_23 ? cost_01 : cost_23;
      assign lane_min_id = cost_01 <= cost_23 ? (choose_01 ? pe_out_id[0] : pe_out_id[1])
                                              : (choose_23 ? pe_out_id[2] : pe_out_id[3]);
    end else begin : reduction_p8
      wire choose_01 = !pe_out_valid[1] || (pe_out_valid[0] && pe_out_cost[0] <= pe_out_cost[1]);
      wire choose_23 = !pe_out_valid[3] || (pe_out_valid[2] && pe_out_cost[2] <= pe_out_cost[3]);
      wire choose_45 = !pe_out_valid[5] || (pe_out_valid[4] && pe_out_cost[4] <= pe_out_cost[5]);
      wire choose_67 = !pe_out_valid[7] || (pe_out_valid[6] && pe_out_cost[6] <= pe_out_cost[7]);
      wire [COST_WIDTH-1:0] cost_01 = choose_01 ? (pe_out_valid[0] ? pe_out_cost[0] : {COST_WIDTH{1'b1}}) : pe_out_cost[1];
      wire [COST_WIDTH-1:0] cost_23 = choose_23 ? (pe_out_valid[2] ? pe_out_cost[2] : {COST_WIDTH{1'b1}}) : pe_out_cost[3];
      wire [COST_WIDTH-1:0] cost_45 = choose_45 ? (pe_out_valid[4] ? pe_out_cost[4] : {COST_WIDTH{1'b1}}) : pe_out_cost[5];
      wire [COST_WIDTH-1:0] cost_67 = choose_67 ? (pe_out_valid[6] ? pe_out_cost[6] : {COST_WIDTH{1'b1}}) : pe_out_cost[7];
      wire choose_0123 = cost_01 <= cost_23;
      wire choose_4567 = cost_45 <= cost_67;
      wire [COST_WIDTH-1:0] cost_0123 = choose_0123 ? cost_01 : cost_23;
      wire [COST_WIDTH-1:0] cost_4567 = choose_4567 ? cost_45 : cost_67;
      wire [5:0] id_0123 = choose_0123 ? (choose_01 ? pe_out_id[0] : pe_out_id[1]) : (choose_23 ? pe_out_id[2] : pe_out_id[3]);
      wire [5:0] id_4567 = choose_4567 ? (choose_45 ? pe_out_id[4] : pe_out_id[5]) : (choose_67 ? pe_out_id[6] : pe_out_id[7]);
      assign lane_min_cost = cost_0123 <= cost_4567 ? cost_0123 : cost_4567;
      assign lane_min_id = cost_0123 <= cost_4567 ? id_0123 : id_4567;
    end
  endgenerate

  always_ff @(posedge clk) begin
    if (!rst_n) begin
      active <= 1'b0;
      launched_count <= '0;
      completed_count <= '0;
      done <= 1'b0;
      best_id <= '0;
      best_cost <= {COST_WIDTH{1'b1}};
      overflow_seen <= 1'b0;
    end else begin
      done <= 1'b0;
      if (!active) begin
        if (start && candidate_count > 0 && int'(candidate_count) <= MAX_CANDIDATES) begin
          active <= 1'b1;
          launched_count <= '0;
          completed_count <= '0;
          best_id <= '0;
          best_cost <= {COST_WIDTH{1'b1}};
          overflow_seen <= 1'b0;
        end
      end else begin
        if (candidate_ready) launched_count <= launched_count + launch_increment;
        if (completion_increment != 0) begin
          completed_count <= completed_count + completion_increment;
          best_id <= reduced_id;
          best_cost <= reduced_cost;
          overflow_seen <= overflow_seen || (|(pe_out_overflow & pe_out_valid));
          if (completed_count + completion_increment == {1'b0, candidate_count}) begin
            active <= 1'b0;
            done <= 1'b1;
          end
        end
      end
    end
  end

  initial begin
    if (P != 1 && P != 2 && P != 4 && P != 8) $fatal(1, "P must be 1, 2, 4, or 8");
  end
endmodule
