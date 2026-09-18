module full_rdo_pway_optimized_tb #(
  parameter integer P = 1,
  parameter integer PIPELINE_DEPTH = 2,
  parameter integer COST_WIDTH = 56,
  parameter integer GROUP_COUNT = 64
);
  localparam integer MAX_CANDIDATES = 35;
  localparam integer CANDIDATE_LATENCY = 113 + PIPELINE_DEPTH
                                         + (PIPELINE_DEPTH >= 3 ? 16 : 0);
  // The wrapper spends one cycle launching and one cycle retiring each lane batch.
  localparam integer BATCH_CYCLES = CANDIDATE_LATENCY + 2;

  logic clk;
  logic rst_n = 0;
  logic start = 0;
  logic start_ready;
  logic [5:0] candidate_count;
  logic [MAX_CANDIDATES*6-1:0] candidate_modes;
  logic [MAX_CANDIDATES*24-1:0] candidate_rate_bits;
  logic [5:0] qp;
  logic [31:0] lambda_q;
  logic [135:0] references;
  logic [127:0] original;
  logic [P-1:0] retire_valid;
  logic retire_ready = 1;
  logic [P-1:0] retire_supported;
  logic [P-1:0][5:0] retire_rank;
  logic [P-1:0][5:0] retire_mode;
  logic [P-1:0][COST_WIDTH-1:0] retire_cost_q;
  logic done;
  logic winner_supported;
  logic [5:0] winner_rank;
  logic [5:0] winner_mode;
  logic [COST_WIDTH-1:0] winner_cost_q;
  logic [15:0] event_cycles;
  logic [7:0] batches_model;
  logic [7:0] batches_rtl;
  logic [15:0] stall_cycles;
  logic [23:0] lane_active_cycles;

  logic [135:0] references_mem [0:GROUP_COUNT-1];
  logic [127:0] original_mem [0:GROUP_COUNT-1];
  logic [5:0] qp_mem [0:GROUP_COUNT-1];
  logic [31:0] lambda_mem [0:GROUP_COUNT-1];
  logic [MAX_CANDIDATES*6-1:0] modes_mem [0:GROUP_COUNT-1];
  logic [MAX_CANDIDATES*24-1:0] rates_mem [0:GROUP_COUNT-1];
  logic [MAX_CANDIDATES*56-1:0] costs_mem [0:GROUP_COUNT-1];
  logic [5:0] winner_rank_k4 [0:GROUP_COUNT-1];
  logic [5:0] winner_rank_k16 [0:GROUP_COUNT-1];
  logic [5:0] winner_rank_k35 [0:GROUP_COUNT-1];
  logic [5:0] winner_mode_k4 [0:GROUP_COUNT-1];
  logic [5:0] winner_mode_k16 [0:GROUP_COUNT-1];
  logic [5:0] winner_mode_k35 [0:GROUP_COUNT-1];
  logic [55:0] winner_cost_k4 [0:GROUP_COUNT-1];
  logic [55:0] winner_cost_k16 [0:GROUP_COUNT-1];
  logic [55:0] winner_cost_k35 [0:GROUP_COUNT-1];

  logic [MAX_CANDIDATES-1:0] seen;
  integer cycle;
  integer group_index;
  integer lane_index;
  integer accepted_cycle;
  integer retired_count;
  integer expected_batches;
  integer expected_event_cycles;
  integer candidate_fail = 0;
  integer duplicate_fail = 0;
  integer dropped_fail = 0;
  integer winner_fail = 0;
  integer cycle_fail = 0;
  integer interface_fail = 0;
  integer backpressure_events = 0;
  integer observed_stall_cycles = 0;
  integer total_fail;

  always #1 clk = ~clk;
  always @(posedge clk) cycle <= cycle + 1;

  full_rdo_pway_optimized #(
    .P(P), .PIPELINE_DEPTH(PIPELINE_DEPTH),
    .MAX_CANDIDATES(MAX_CANDIDATES), .COST_WIDTH(COST_WIDTH)
  ) dut (.*);

  task automatic run_event(input integer index, input integer k, input integer slot,
                           input logic use_backpressure);
    integer rank;
    logic [5:0] expected_winner_rank;
    logic [5:0] expected_winner_mode;
    logic [55:0] expected_winner_cost;
    begin
      while (!start_ready) @(negedge clk);
      candidate_count = 6'(k);
      candidate_modes = modes_mem[index];
      candidate_rate_bits = rates_mem[index];
      qp = qp_mem[index];
      lambda_q = lambda_mem[index];
      references = references_mem[index];
      original = original_mem[index];
      retire_ready = 1'b1;
      start = 1'b1;
      @(negedge clk);
      accepted_cycle = cycle;
      start = 1'b0;
      seen = '0;
      retired_count = 0;
      while (!done) begin
        @(negedge clk);
        retire_ready = !use_backpressure || (cycle % 7 >= 2);
        for (lane_index = 0; lane_index < P; lane_index = lane_index + 1) begin
          if (retire_valid[lane_index] && retire_ready) begin
            rank = integer'(retire_rank[lane_index]);
            if (rank < 0 || rank >= k || !retire_supported[lane_index])
              interface_fail = interface_fail + 1;
            else begin
              if (seen[rank]) duplicate_fail = duplicate_fail + 1;
              seen[rank] = 1'b1;
              if (retire_mode[lane_index] != modes_mem[index][rank*6 +: 6]
                  || retire_cost_q[lane_index] != COST_WIDTH'(costs_mem[index][rank*56 +: 56]))
                candidate_fail = candidate_fail + 1;
            end
            retired_count = retired_count + 1;
          end
        end
      end
      retire_ready = 1'b1;
      for (rank = 0; rank < k; rank = rank + 1)
        if (!seen[rank]) dropped_fail = dropped_fail + 1;
      if (retired_count != k) dropped_fail = dropped_fail + 1;
      if (slot == 0) begin
        expected_winner_rank = winner_rank_k4[index];
        expected_winner_mode = winner_mode_k4[index];
        expected_winner_cost = winner_cost_k4[index];
      end else if (slot == 1) begin
        expected_winner_rank = winner_rank_k16[index];
        expected_winner_mode = winner_mode_k16[index];
        expected_winner_cost = winner_cost_k16[index];
      end else begin
        expected_winner_rank = winner_rank_k35[index];
        expected_winner_mode = winner_mode_k35[index];
        expected_winner_cost = winner_cost_k35[index];
      end
      if (!winner_supported || winner_rank != expected_winner_rank
          || winner_mode != expected_winner_mode
          || winner_cost_q != COST_WIDTH'(expected_winner_cost))
        winner_fail = winner_fail + 1;
      expected_batches = (k + P - 1) / P;
      expected_event_cycles = BATCH_CYCLES * expected_batches + integer'(stall_cycles);
      if (batches_model != 8'(expected_batches) || batches_rtl != 8'(expected_batches)
          || integer'(event_cycles) != expected_event_cycles
          || cycle-accepted_cycle != expected_event_cycles) begin
        $display("cycle mismatch index=%0d k=%0d backpressure=%0d event=%0d wall=%0d expected=%0d batches_model=%0d batches_rtl=%0d stalls=%0d",
                 index, k, use_backpressure, event_cycles, cycle-accepted_cycle,
                 expected_event_cycles, batches_model, batches_rtl, stall_cycles);
        cycle_fail = cycle_fail + 1;
      end
      if (use_backpressure) begin
        backpressure_events = backpressure_events + 1;
        observed_stall_cycles = observed_stall_cycles + integer'(stall_cycles);
      end else if (stall_cycles != 0) cycle_fail = cycle_fail + 1;
      if (integer'(lane_active_cycles) < CANDIDATE_LATENCY*k)
        cycle_fail = cycle_fail + 1;
      @(negedge clk);
    end
  endtask

  initial begin
    clk = 1'b0;
    cycle = 0;
    $readmemh("references.mem", references_mem);
    $readmemh("original.mem", original_mem);
    $readmemh("qp.mem", qp_mem);
    $readmemh("lambda.mem", lambda_mem);
    $readmemh("modes.mem", modes_mem);
    $readmemh("rates.mem", rates_mem);
    $readmemh("costs.mem", costs_mem);
    $readmemh("winner_rank_k4.mem", winner_rank_k4);
    $readmemh("winner_rank_k16.mem", winner_rank_k16);
    $readmemh("winner_rank_k35.mem", winner_rank_k35);
    $readmemh("winner_mode_k4.mem", winner_mode_k4);
    $readmemh("winner_mode_k16.mem", winner_mode_k16);
    $readmemh("winner_mode_k35.mem", winner_mode_k35);
    $readmemh("winner_cost_k4.mem", winner_cost_k4);
    $readmemh("winner_cost_k16.mem", winner_cost_k16);
    $readmemh("winner_cost_k35.mem", winner_cost_k35);
    repeat (3) @(negedge clk);
    rst_n = 1'b1;
    for (group_index = 0; group_index < GROUP_COUNT; group_index = group_index + 1) begin
      run_event(group_index, 4, 0, group_index[0]);
      run_event(group_index, 16, 1, group_index[0]);
      run_event(group_index, 35, 2, group_index[0]);
    end
    total_fail = candidate_fail + duplicate_fail + dropped_fail + winner_fail
                 + cycle_fail + interface_fail;
    $display("{\"p\":%0d,\"pipeline_depth\":%0d,\"cost_width\":%0d,\"groups\":%0d,\"events\":%0d,\"candidate_evaluations\":%0d,\"candidate_latency_cycles\":%0d,\"batch_cycles\":%0d,\"backpressure_events\":%0d,\"observed_stall_cycles\":%0d,\"candidate_fail\":%0d,\"duplicate_fail\":%0d,\"dropped_fail\":%0d,\"winner_fail\":%0d,\"cycle_fail\":%0d,\"interface_fail\":%0d,\"total_fail\":%0d}",
             P, PIPELINE_DEPTH, COST_WIDTH, GROUP_COUNT, GROUP_COUNT*3, GROUP_COUNT*(4+16+35),
             CANDIDATE_LATENCY, BATCH_CYCLES, backpressure_events, observed_stall_cycles,
             candidate_fail, duplicate_fail, dropped_fail, winner_fail, cycle_fail,
             interface_fail, total_fail);
    if (total_fail != 0) $fatal(1, "optimized P-way regression failed");
    if (observed_stall_cycles == 0) $fatal(1, "backpressure coverage was not exercised");
    $finish;
  end
endmodule
