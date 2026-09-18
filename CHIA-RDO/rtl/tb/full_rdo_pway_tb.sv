module full_rdo_pway_tb #(
  parameter integer P = 4
);
  localparam integer GROUP_COUNT = 256;
  logic clk;
  logic rst_n = 0;
  logic start = 0;
  logic start_ready;
  logic [5:0] candidate_count;
  logic [209:0] candidate_modes;
  logic [839:0] candidate_rate_bits;
  logic [5:0] qp;
  logic [31:0] lambda_q;
  logic [135:0] references;
  logic [127:0] original;
  logic [P-1:0] retire_valid;
  logic retire_ready = 1;
  logic [P-1:0] retire_supported;
  logic [P-1:0][5:0] retire_rank;
  logic [P-1:0][5:0] retire_mode;
  logic [P-1:0][55:0] retire_cost_q;
  logic done;
  logic winner_supported;
  logic [5:0] winner_rank;
  logic [5:0] winner_mode;
  logic [55:0] winner_cost_q;
  logic [15:0] event_cycles;
  logic [7:0] batches_model;
  logic [7:0] batches_rtl;
  logic [15:0] stall_cycles;
  logic [23:0] lane_active_cycles;

  logic [135:0] references_mem [0:GROUP_COUNT-1];
  logic [127:0] original_mem [0:GROUP_COUNT-1];
  logic [5:0] qp_mem [0:GROUP_COUNT-1];
  logic [31:0] lambda_mem [0:GROUP_COUNT-1];
  logic [209:0] modes_mem [0:GROUP_COUNT-1];
  logic [839:0] rates_mem [0:GROUP_COUNT-1];
  logic [1959:0] costs_mem [0:GROUP_COUNT-1];
  logic [5:0] winner_rank_k4 [0:GROUP_COUNT-1];
  logic [5:0] winner_rank_k16 [0:GROUP_COUNT-1];
  logic [5:0] winner_rank_k35 [0:GROUP_COUNT-1];
  logic [5:0] winner_mode_k4 [0:GROUP_COUNT-1];
  logic [5:0] winner_mode_k16 [0:GROUP_COUNT-1];
  logic [5:0] winner_mode_k35 [0:GROUP_COUNT-1];
  logic [55:0] winner_cost_k4 [0:GROUP_COUNT-1];
  logic [55:0] winner_cost_k16 [0:GROUP_COUNT-1];
  logic [55:0] winner_cost_k35 [0:GROUP_COUNT-1];

  logic [34:0] seen;
  integer cycle;
  integer group_index;
  integer lane_index;
  integer retired_count;
  integer accepted_cycle;
  integer expected_batches;
  integer candidate_fail = 0;
  integer duplicate_fail = 0;
  integer dropped_fail = 0;
  integer winner_fail = 0;
  integer cycle_fail = 0;
  integer interface_fail = 0;
  integer cycles_k4 = 0;
  integer cycles_k16 = 0;
  integer cycles_k35 = 0;
  integer lane_active_k4 = 0;
  integer lane_active_k16 = 0;
  integer lane_active_k35 = 0;
  integer total_fail;

  always #1 clk = ~clk;
  always @(posedge clk) cycle <= cycle + 1;

  full_rdo_pway #(.P(P)) dut (.*);

  task automatic run_event(input integer index, input integer k, input integer slot);
    integer rank;
    logic [5:0] expected_winner_rank;
    logic [5:0] expected_winner_mode;
    logic [55:0] expected_winner_cost;
    begin
      if (index < 0 || index >= GROUP_COUNT || k < 1 || k > 35 || slot < -1 || slot > 2)
        $fatal(1, "invalid event arguments");
      while (!start_ready) @(negedge clk);
      candidate_count = 6'(k);
      candidate_modes = modes_mem[index];
      candidate_rate_bits = rates_mem[index];
      qp = qp_mem[index];
      lambda_q = lambda_mem[index];
      references = references_mem[index];
      original = original_mem[index];
      start = 1'b1;
      @(negedge clk);
      accepted_cycle = cycle;
      start = 1'b0;
      seen = '0;
      retired_count = 0;
      while (!done) begin
        @(negedge clk);
        for (lane_index = 0; lane_index < P; lane_index = lane_index + 1) begin
          if (retire_valid[lane_index] && retire_ready) begin
            rank = integer'(retire_rank[lane_index]);
            if (rank < 0 || rank >= k || !retire_supported[lane_index]) interface_fail = interface_fail + 1;
            else begin
              if (seen[rank]) duplicate_fail = duplicate_fail + 1;
              seen[rank] = 1'b1;
              if (retire_mode[lane_index] != modes_mem[index][rank*6 +: 6]
                  || retire_cost_q[lane_index] != costs_mem[index][rank*56 +: 56])
                candidate_fail = candidate_fail + 1;
            end
            retired_count = retired_count + 1;
          end
        end
      end
      for (rank = 0; rank < k; rank = rank + 1)
        if (!seen[rank]) dropped_fail = dropped_fail + 1;
      if (retired_count != k) dropped_fail = dropped_fail + 1;
      if (slot == 0) begin expected_winner_rank = winner_rank_k4[index]; expected_winner_mode = winner_mode_k4[index]; expected_winner_cost = winner_cost_k4[index]; end
      else if (slot == 1) begin expected_winner_rank = winner_rank_k16[index]; expected_winner_mode = winner_mode_k16[index]; expected_winner_cost = winner_cost_k16[index]; end
      else if (slot == 2) begin expected_winner_rank = winner_rank_k35[index]; expected_winner_mode = winner_mode_k35[index]; expected_winner_cost = winner_cost_k35[index]; end
      else begin
        expected_winner_rank = 0;
        expected_winner_mode = modes_mem[index][0 +: 6];
        expected_winner_cost = costs_mem[index][0 +: 56];
        for (rank = 1; rank < k; rank = rank + 1) begin
          if (costs_mem[index][rank*56 +: 56] < expected_winner_cost) begin
            expected_winner_rank = 6'(rank);
            expected_winner_mode = modes_mem[index][rank*6 +: 6];
            expected_winner_cost = costs_mem[index][rank*56 +: 56];
          end
        end
      end
      if (!winner_supported || winner_rank != expected_winner_rank
          || winner_mode != expected_winner_mode || winner_cost_q != expected_winner_cost)
        winner_fail = winner_fail + 1;
      expected_batches = (k + P - 1) / P;
      if (batches_model != 8'(expected_batches) || batches_rtl != 8'(expected_batches)
          || event_cycles != 16'(4*expected_batches) || cycle-accepted_cycle != 4*expected_batches
          || lane_active_cycles != 24'(4*k) || stall_cycles != 0)
        cycle_fail = cycle_fail + 1;
      if (slot == 0) begin cycles_k4 = integer'(event_cycles); lane_active_k4 = integer'(lane_active_cycles); end
      else if (slot == 1) begin cycles_k16 = integer'(event_cycles); lane_active_k16 = integer'(lane_active_cycles); end
      else if (slot == 2) begin cycles_k35 = integer'(event_cycles); lane_active_k35 = integer'(lane_active_cycles); end
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
      run_event(group_index, 4, 0);
      run_event(group_index, 16, 1);
      run_event(group_index, 35, 2);
    end
    run_event(0, 1, -1);
    run_event(0, 3, -1);
    total_fail = candidate_fail + duplicate_fail + dropped_fail + winner_fail + cycle_fail + interface_fail;
    $display("{\"p\":%0d,\"events\":770,\"candidate_evaluations\":%0d,\"cycles_k4\":%0d,\"cycles_k16\":%0d,\"cycles_k35\":%0d,\"lane_active_k4\":%0d,\"lane_active_k16\":%0d,\"lane_active_k35\":%0d,\"candidate_fail\":%0d,\"duplicate_fail\":%0d,\"dropped_fail\":%0d,\"winner_fail\":%0d,\"cycle_fail\":%0d,\"interface_fail\":%0d,\"total_fail\":%0d}", P, 256*(4+16+35)+4, cycles_k4, cycles_k16, cycles_k35, lane_active_k4, lane_active_k16, lane_active_k35, candidate_fail, duplicate_fail, dropped_fail, winner_fail, cycle_fail, interface_fail, total_fail);
    if (total_fail != 0) $fatal(1, "P-way Full-RDO regression failed");
    $finish;
  end
endmodule
