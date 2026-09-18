module full_rdo_mvp_4x4_tb;
  localparam integer VECTOR_COUNT = 256;
  logic clk;
  logic rst_n = 0;
  logic in_valid = 0;
  logic in_ready;
  logic [5:0] in_mode;
  logic [5:0] in_qp;
  logic [135:0] in_references;
  logic [127:0] in_original;
  logic [23:0] in_rate_bits;
  logic [31:0] in_lambda_q;
  logic out_valid;
  logic out_ready = 1;
  logic out_supported;
  logic [5:0] out_mode;
  logic [5:0] out_qp;
  logic [127:0] out_prediction;
  logic [143:0] out_residual;
  logic [511:0] out_transformed;
  logic [255:0] out_quantized;
  logic [255:0] out_dequantized;
  logic [255:0] out_inverse_residual;
  logic [127:0] out_reconstruction;
  logic [31:0] out_distortion;
  logic [23:0] out_rate_bits;
  logic [55:0] out_rd_cost_q;
  logic out_overflow;
  logic [7:0] out_latency_cycles;

  logic [135:0] references_mem [0:VECTOR_COUNT-1];
  logic [127:0] original_mem [0:VECTOR_COUNT-1];
  logic [5:0] qp_mem [0:VECTOR_COUNT-1];
  logic [23:0] rate_mem [0:VECTOR_COUNT-1];
  logic [31:0] lambda_mem [0:VECTOR_COUNT-1];
  logic [127:0] prediction_mem [0:VECTOR_COUNT-1];
  logic [143:0] residual_mem [0:VECTOR_COUNT-1];
  logic [511:0] transform_mem [0:VECTOR_COUNT-1];
  logic [255:0] quantized_mem [0:VECTOR_COUNT-1];
  logic [255:0] dequantized_mem [0:VECTOR_COUNT-1];
  logic [255:0] inverse_mem [0:VECTOR_COUNT-1];
  logic [127:0] reconstruction_mem [0:VECTOR_COUNT-1];
  logic [31:0] distortion_mem [0:VECTOR_COUNT-1];
  logic [55:0] cost_mem [0:VECTOR_COUNT-1];

  integer cycle;
  integer vector_index;
  integer accepted_cycle;
  integer prediction_fail = 0;
  integer residual_fail = 0;
  integer transform_fail = 0;
  integer quantized_fail = 0;
  integer dequantized_fail = 0;
  integer inverse_fail = 0;
  integer reconstruction_fail = 0;
  integer distortion_fail = 0;
  integer cost_fail = 0;
  integer interface_fail = 0;
  integer total_fail;

  always #1 clk = ~clk;
  always @(posedge clk) cycle <= cycle + 1;

  full_rdo_mvp_4x4 dut (.*);

  task automatic submit_vector(input integer index);
    begin
      if (index < 0 || index >= VECTOR_COUNT) $fatal(1, "invalid vector index");
      while (!in_ready) @(negedge clk);
      in_mode = 6'd1;
      in_qp = qp_mem[index];
      in_references = references_mem[index];
      in_original = original_mem[index];
      in_rate_bits = rate_mem[index];
      in_lambda_q = lambda_mem[index];
      in_valid = 1'b1;
      @(negedge clk);
      accepted_cycle = cycle;
      in_valid = 1'b0;
      while (!out_valid) @(negedge clk);
      if (!out_supported || out_mode != 1 || out_qp != qp_mem[index] ||
          out_rate_bits != rate_mem[index] || out_latency_cycles != 2 ||
          cycle - accepted_cycle != 2 || out_overflow) interface_fail = interface_fail + 1;
      if (out_prediction !== prediction_mem[index]) prediction_fail = prediction_fail + 1;
      if (out_residual !== residual_mem[index]) residual_fail = residual_fail + 1;
      if (out_transformed !== transform_mem[index]) transform_fail = transform_fail + 1;
      if (out_quantized !== quantized_mem[index]) quantized_fail = quantized_fail + 1;
      if (out_dequantized !== dequantized_mem[index]) dequantized_fail = dequantized_fail + 1;
      if (out_inverse_residual !== inverse_mem[index]) inverse_fail = inverse_fail + 1;
      if (out_reconstruction !== reconstruction_mem[index]) reconstruction_fail = reconstruction_fail + 1;
      if (out_distortion !== distortion_mem[index]) distortion_fail = distortion_fail + 1;
      if (out_rd_cost_q !== cost_mem[index]) cost_fail = cost_fail + 1;
      @(negedge clk);
    end
  endtask

  initial begin
    clk = 1'b0;
    cycle = 0;
    $readmemh("references.mem", references_mem);
    $readmemh("original.mem", original_mem);
    $readmemh("qp.mem", qp_mem);
    $readmemh("rate.mem", rate_mem);
    $readmemh("lambda.mem", lambda_mem);
    $readmemh("prediction.mem", prediction_mem);
    $readmemh("residual.mem", residual_mem);
    $readmemh("transform.mem", transform_mem);
    $readmemh("quantized.mem", quantized_mem);
    $readmemh("dequantized.mem", dequantized_mem);
    $readmemh("inverse.mem", inverse_mem);
    $readmemh("reconstruction.mem", reconstruction_mem);
    $readmemh("distortion.mem", distortion_mem);
    $readmemh("cost.mem", cost_mem);
    repeat (3) @(negedge clk);
    rst_n = 1'b1;
    for (vector_index = 0; vector_index < VECTOR_COUNT; vector_index = vector_index + 1)
      submit_vector(vector_index);

    while (!in_ready) @(negedge clk);
    in_mode = 6'd35;
    in_qp = 6'd22;
    in_valid = 1'b1;
    @(negedge clk);
    in_valid = 1'b0;
    while (!out_valid) @(negedge clk);
    if (out_supported) interface_fail = interface_fail + 1;
    @(negedge clk);

    while (!in_ready) @(negedge clk);
    in_mode = 6'd1;
    in_qp = 6'd23;
    in_valid = 1'b1;
    @(negedge clk);
    in_valid = 1'b0;
    while (!out_valid) @(negedge clk);
    if (out_supported) interface_fail = interface_fail + 1;
    @(negedge clk);

    total_fail = prediction_fail + residual_fail + transform_fail + quantized_fail +
                 dequantized_fail + inverse_fail + reconstruction_fail + distortion_fail +
                 cost_fail + interface_fail;
    $display("{\"vectors\":256,\"unsupported_cases\":2,\"latency_cycles\":2,\"prediction_fail\":%0d,\"residual_fail\":%0d,\"transform_fail\":%0d,\"quantized_fail\":%0d,\"dequantized_fail\":%0d,\"inverse_fail\":%0d,\"reconstruction_fail\":%0d,\"distortion_fail\":%0d,\"cost_fail\":%0d,\"interface_fail\":%0d,\"total_fail\":%0d}", prediction_fail, residual_fail, transform_fail, quantized_fail, dequantized_fail, inverse_fail, reconstruction_fail, distortion_fail, cost_fail, interface_fail, total_fail);
    if (total_fail != 0) $fatal(1, "full-RDO exact-match gate failed");
    $finish;
  end
endmodule
