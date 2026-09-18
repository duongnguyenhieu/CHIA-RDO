module rdo_array_tb #(
  parameter int P = 4,
  parameter int PIPELINE_DEPTH = 2,
  parameter int COST_WIDTH = 56
);
  logic clk = 0;
  logic rst_n = 0;
  logic start = 0;
  logic [5:0] candidate_count;
  logic [P-1:0] candidate_valid;
  logic candidate_ready;
  logic [P-1:0][5:0] candidate_id;
  logic [P-1:0][31:0] candidate_distortion;
  logic [P-1:0][23:0] candidate_rate_bits;
  logic [P-1:0][31:0] candidate_lambda_q;
  logic done;
  logic [5:0] best_id;
  logic [COST_WIDTH-1:0] best_cost;
  logic overflow_seen;
  integer index;
  integer lane;

  always #1 clk = ~clk;

  rdo_array #(.P(P), .PIPELINE_DEPTH(PIPELINE_DEPTH), .COST_WIDTH(COST_WIDTH)) dut (.*);

  task automatic launch(input integer count, input integer special_id);
    begin
      candidate_count = 6'(count);
      @(negedge clk);
      start = 1;
      @(negedge clk);
      start = 0;
      index = 0;
      while (index < count) begin
        while (!candidate_ready) @(negedge clk);
        candidate_valid = '0;
        for (lane = 0; lane < P; lane = lane + 1) begin
          if (index + lane < count) begin
            candidate_valid[lane] = 1;
            candidate_id[lane] = 6'(index + lane);
            candidate_distortion[lane] = index + lane == special_id ? 0 : 1000 + index + lane;
            candidate_rate_bits[lane] = 24'(index + lane == special_id ? 0 : index + lane);
            candidate_lambda_q[lane] = 32'd65536;
          end
        end
        @(negedge clk);
        index = index + P;
      end
      candidate_valid = '0;
    end
  endtask

  initial begin
    candidate_valid = '0;
    candidate_id = '0;
    candidate_distortion = '0;
    candidate_rate_bits = '0;
    candidate_lambda_q = '0;
    candidate_count = '0;
    repeat (3) @(negedge clk);
    rst_n = 1;

    launch(35, 17);
    wait (done);
    if (best_id != 17 || best_cost != 0 || overflow_seen) $fatal(1, "35-candidate reduction failed");
    @(negedge clk);
    launch(3, 2);
    wait (done);
    if (best_id != 2 || best_cost != 0 || overflow_seen) $fatal(1, "tail-batch reduction failed");
    $display("{\"p\":%0d,\"pipeline_depth\":%0d,\"pass\":2,\"fail\":0}", P, PIPELINE_DEPTH);
    $finish;
  end
endmodule
