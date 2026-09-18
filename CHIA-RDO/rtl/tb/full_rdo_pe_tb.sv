module full_rdo_pe_tb;
  localparam integer GROUP_COUNT = 2500;
  localparam integer CANDIDATE_COUNT = 10000;
  logic clk;
  logic rst_n = 0;
  logic start = 0;
  logic start_ready;
  logic [5:0] block_size;
  logic [2:0] candidate_count;
  logic [23:0] candidate_modes;
  logic [95:0] candidate_rate_bits;
  logic [5:0] qp;
  logic [31:0] lambda_q;
  logic [135:0] references;
  logic [127:0] original;
  logic candidate_valid;
  logic candidate_ready = 1;
  logic candidate_supported;
  logic [1:0] candidate_rank;
  logic [5:0] candidate_mode;
  logic [5:0] candidate_qp;
  logic [127:0] candidate_prediction;
  logic [143:0] candidate_residual;
  logic [511:0] candidate_transformed;
  logic [255:0] candidate_quantized;
  logic [255:0] candidate_dequantized;
  logic [255:0] candidate_inverse_residual;
  logic [127:0] candidate_reconstruction;
  logic [31:0] candidate_distortion;
  logic [23:0] candidate_bits;
  logic [55:0] candidate_cost_q;
  logic done;
  logic winner_supported;
  logic [1:0] winner_rank;
  logic [5:0] winner_mode;
  logic [55:0] winner_cost_q;
  logic [15:0] group_cycles;
  logic [15:0] stall_cycles;
  logic [15:0] pe_active_cycles;
  logic [7:0] candidate_latency_cycles;
  logic [7:0] candidate_launch_interval;
  logic [7:0] comparator_latency_cycles;

  logic [135:0] group_references [0:GROUP_COUNT-1];
  logic [127:0] group_original [0:GROUP_COUNT-1];
  logic [5:0] group_qp [0:GROUP_COUNT-1];
  logic [31:0] group_lambda [0:GROUP_COUNT-1];
  logic [23:0] group_modes [0:GROUP_COUNT-1];
  logic [95:0] group_rates [0:GROUP_COUNT-1];
  logic [1:0] expected_winner_rank [0:GROUP_COUNT-1];
  logic [5:0] expected_winner_mode [0:GROUP_COUNT-1];
  logic [55:0] expected_winner_cost [0:GROUP_COUNT-1];
  logic [5:0] expected_mode [0:CANDIDATE_COUNT-1];
  logic [127:0] expected_prediction [0:CANDIDATE_COUNT-1];
  logic [143:0] expected_residual [0:CANDIDATE_COUNT-1];
  logic [511:0] expected_transform [0:CANDIDATE_COUNT-1];
  logic [255:0] expected_quantized [0:CANDIDATE_COUNT-1];
  logic [255:0] expected_dequantized [0:CANDIDATE_COUNT-1];
  logic [255:0] expected_inverse [0:CANDIDATE_COUNT-1];
  logic [127:0] expected_reconstruction [0:CANDIDATE_COUNT-1];
  logic [31:0] expected_distortion [0:CANDIDATE_COUNT-1];
  logic [23:0] expected_bits [0:CANDIDATE_COUNT-1];
  logic [55:0] expected_cost [0:CANDIDATE_COUNT-1];

  integer cycle;
  integer group_index;
  integer candidate_index;
  integer rank_in_group;
  integer accepted_cycle;
  integer prediction_fail = 0;
  integer residual_fail = 0;
  integer transform_fail = 0;
  integer quantized_fail = 0;
  integer dequantized_fail = 0;
  integer inverse_fail = 0;
  integer reconstruction_fail = 0;
  integer distortion_fail = 0;
  integer bits_fail = 0;
  integer cost_fail = 0;
  integer winner_fail = 0;
  integer cycle_fail = 0;
  integer interface_fail = 0;
  integer stall_fail = 0;
  integer injected_stalls;
  logic [55:0] held_cost;
  integer total_fail;

  always #1 clk = ~clk;
  always @(posedge clk) cycle <= cycle + 1;

  full_rdo_pe dut (.*);

  task automatic load_group(input integer index);
    begin
      if (index < 0 || index >= GROUP_COUNT) $fatal(1, "invalid group index");
      block_size = 4;
      candidate_count = 4;
      candidate_modes = group_modes[index];
      candidate_rate_bits = group_rates[index];
      qp = group_qp[index];
      lambda_q = group_lambda[index];
      references = group_references[index];
      original = group_original[index];
    end
  endtask

  task automatic run_stalled_group;
    begin
      while (!start_ready) @(negedge clk);
      load_group(0);
      start = 1'b1;
      @(negedge clk);
      start = 1'b0;
      rank_in_group = 0;
      injected_stalls = 0;
      while (!done) begin
        @(negedge clk);
        if (candidate_valid && rank_in_group == 0 && injected_stalls < 2) begin
          if (injected_stalls == 0) held_cost = candidate_cost_q;
          else if (candidate_cost_q != held_cost) stall_fail = stall_fail + 1;
          candidate_ready = 1'b0;
          injected_stalls = injected_stalls + 1;
        end else begin
          candidate_ready = 1'b1;
          if (candidate_valid) begin
            check_candidate(rank_in_group, 2'(rank_in_group));
            rank_in_group = rank_in_group + 1;
          end
        end
      end
      if (rank_in_group != 4 || stall_cycles != 2 || group_cycles != 18
          || pe_active_cycles != 18 || winner_rank != expected_winner_rank[0]
          || winner_mode != expected_winner_mode[0] || winner_cost_q != expected_winner_cost[0])
        stall_fail = stall_fail + 1;
      candidate_ready = 1'b1;
      @(negedge clk);
    end
  endtask

  task automatic check_candidate(input integer index, input logic [1:0] rank);
    begin
      if (index < 0 || index >= CANDIDATE_COUNT) $fatal(1, "invalid candidate index");
      if (!candidate_supported || candidate_rank != rank || candidate_mode != expected_mode[index]
          || candidate_qp != group_qp[group_index])
        interface_fail = interface_fail + 1;
      if (candidate_prediction !== expected_prediction[index]) prediction_fail = prediction_fail + 1;
      if (candidate_residual !== expected_residual[index]) residual_fail = residual_fail + 1;
      if (candidate_transformed !== expected_transform[index]) transform_fail = transform_fail + 1;
      if (candidate_quantized !== expected_quantized[index]) quantized_fail = quantized_fail + 1;
      if (candidate_dequantized !== expected_dequantized[index]) dequantized_fail = dequantized_fail + 1;
      if (candidate_inverse_residual !== expected_inverse[index]) inverse_fail = inverse_fail + 1;
      if (candidate_reconstruction !== expected_reconstruction[index]) reconstruction_fail = reconstruction_fail + 1;
      if (candidate_distortion !== expected_distortion[index]) distortion_fail = distortion_fail + 1;
      if (candidate_bits !== expected_bits[index]) bits_fail = bits_fail + 1;
      if (candidate_cost_q !== expected_cost[index]) cost_fail = cost_fail + 1;
    end
  endtask

  task automatic run_group(input integer index);
    begin
      while (!start_ready) @(negedge clk);
      load_group(index);
      start = 1'b1;
      @(negedge clk);
      accepted_cycle = cycle;
      start = 1'b0;
      rank_in_group = 0;
      while (!done) begin
        @(negedge clk);
        if (candidate_valid && candidate_ready) begin
          check_candidate(candidate_index, 2'(rank_in_group));
          candidate_index = candidate_index + 1;
          rank_in_group = rank_in_group + 1;
        end
      end
      if (rank_in_group != 4) interface_fail = interface_fail + 1;
      if (!winner_supported || winner_rank != expected_winner_rank[index]
          || winner_mode != expected_winner_mode[index] || winner_cost_q != expected_winner_cost[index])
        winner_fail = winner_fail + 1;
      if (cycle - accepted_cycle != 16 || group_cycles != 16 || stall_cycles != 0
          || pe_active_cycles != 16 || candidate_latency_cycles != 2
          || candidate_launch_interval != 4 || comparator_latency_cycles != 1)
        cycle_fail = cycle_fail + 1;
      @(negedge clk);
    end
  endtask

  initial begin
    clk = 1'b0;
    cycle = 0;
    $readmemh("group_references.mem", group_references);
    $readmemh("group_original.mem", group_original);
    $readmemh("group_qp.mem", group_qp);
    $readmemh("group_lambda.mem", group_lambda);
    $readmemh("group_modes.mem", group_modes);
    $readmemh("group_rates.mem", group_rates);
    $readmemh("winner_rank.mem", expected_winner_rank);
    $readmemh("winner_mode.mem", expected_winner_mode);
    $readmemh("winner_cost.mem", expected_winner_cost);
    $readmemh("candidate_mode.mem", expected_mode);
    $readmemh("prediction.mem", expected_prediction);
    $readmemh("residual.mem", expected_residual);
    $readmemh("transform.mem", expected_transform);
    $readmemh("quantized.mem", expected_quantized);
    $readmemh("dequantized.mem", expected_dequantized);
    $readmemh("inverse.mem", expected_inverse);
    $readmemh("reconstruction.mem", expected_reconstruction);
    $readmemh("distortion.mem", expected_distortion);
    $readmemh("bits.mem", expected_bits);
    $readmemh("cost.mem", expected_cost);
    repeat (3) @(negedge clk);
    rst_n = 1'b1;
    candidate_index = 0;
    for (group_index = 0; group_index < GROUP_COUNT; group_index = group_index + 1)
      run_group(group_index);
    group_index = 0;
    run_stalled_group();

    while (!start_ready) @(negedge clk);
    load_group(0);
    block_size = 8;
    start = 1'b1;
    @(negedge clk);
    start = 1'b0;
    if (!done || winner_supported || group_cycles != 0) interface_fail = interface_fail + 1;
    @(negedge clk);
    block_size = 16;
    start = 1'b1;
    @(negedge clk);
    start = 1'b0;
    if (!done || winner_supported || group_cycles != 0) interface_fail = interface_fail + 1;

    total_fail = prediction_fail + residual_fail + transform_fail + quantized_fail
      + dequantized_fail + inverse_fail + reconstruction_fail + distortion_fail + bits_fail
      + cost_fail + winner_fail + cycle_fail + interface_fail;
    total_fail = total_fail + stall_fail;
    $display("{\"groups\":2500,\"candidates\":10000,\"prediction_fail\":%0d,\"residual_fail\":%0d,\"transform_fail\":%0d,\"quantized_fail\":%0d,\"dequantized_fail\":%0d,\"inverse_fail\":%0d,\"reconstruction_fail\":%0d,\"distortion_fail\":%0d,\"bits_fail\":%0d,\"cost_fail\":%0d,\"winner_fail\":%0d,\"cycle_fail\":%0d,\"interface_fail\":%0d,\"stall_fail\":%0d,\"candidate_result_latency_cycles\":2,\"cycles_per_candidate\":4,\"cycles_per_group\":16,\"pipeline_stalls\":0,\"injected_stall_cycles\":2,\"stalled_group_cycles\":18,\"pe_utilization_percent\":100,\"comparator_latency_cycles\":1,\"total_fail\":%0d}", prediction_fail, residual_fail, transform_fail, quantized_fail, dequantized_fail, inverse_fail, reconstruction_fail, distortion_fail, bits_fail, cost_fail, winner_fail, cycle_fail, interface_fail, stall_fail, total_fail);
    if (total_fail != 0) $fatal(1, "Phase-5.2 Full-RDO PE gate failed");
    $finish;
  end
endmodule
