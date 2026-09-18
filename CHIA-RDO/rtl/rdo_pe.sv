module rdo_pe #(
  parameter int DIST_WIDTH = 32,
  parameter int RATE_WIDTH = 24,
  parameter int LAMBDA_WIDTH = 32,
  parameter int LAMBDA_FRACTION = 16,
  parameter int COST_WIDTH = 56,
  parameter int PIPELINE_DEPTH = 2
) (
  input  logic                    clk,
  input  logic                    rst_n,
  input  logic                    in_valid,
  output logic                    in_ready,
  input  logic [5:0]              in_candidate_id,
  input  logic [DIST_WIDTH-1:0]   in_distortion,
  input  logic [RATE_WIDTH-1:0]   in_rate_bits,
  input  logic [LAMBDA_WIDTH-1:0] in_lambda_q,
  output logic                    out_valid,
  input  logic                    out_ready,
  output logic [5:0]              out_candidate_id,
  output logic [COST_WIDTH-1:0]   out_rd_cost_q,
  output logic                    out_overflow
);
  localparam int PRODUCT_WIDTH = RATE_WIDTH + LAMBDA_WIDTH;
  localparam int DIST_SCALED_WIDTH = DIST_WIDTH + LAMBDA_FRACTION;
  localparam int MAX_TERM_WIDTH = PRODUCT_WIDTH > DIST_SCALED_WIDTH ? PRODUCT_WIDTH : DIST_SCALED_WIDTH;
  localparam int ACC_WIDTH = MAX_TERM_WIDTH + 1;

  logic advance;

  generate
    if (PIPELINE_DEPTH == 1) begin : single_stage
      logic [PRODUCT_WIDTH-1:0] rate_term;
      logic [DIST_SCALED_WIDTH-1:0] distortion_term;
      logic [ACC_WIDTH-1:0] raw_cost;

      assign rate_term = in_rate_bits * in_lambda_q;
      assign distortion_term = {in_distortion, {LAMBDA_FRACTION{1'b0}}};
      assign raw_cost = {{(ACC_WIDTH-DIST_SCALED_WIDTH){1'b0}}, distortion_term}
                      + {{(ACC_WIDTH-PRODUCT_WIDTH){1'b0}}, rate_term};
      always_ff @(posedge clk) begin
        if (!rst_n) begin
          out_valid <= 1'b0;
          out_candidate_id <= '0;
          out_rd_cost_q <= '0;
          out_overflow <= 1'b0;
        end else if (advance) begin
          out_valid <= in_valid;
          out_candidate_id <= in_candidate_id;
          out_rd_cost_q <= |raw_cost[ACC_WIDTH-1:COST_WIDTH]
                         ? {COST_WIDTH{1'b1}} : raw_cost[COST_WIDTH-1:0];
          out_overflow <= |raw_cost[ACC_WIDTH-1:COST_WIDTH];
        end
      end
    end else begin : multi_stage
      logic valid_pipe [0:PIPELINE_DEPTH-1];
      logic [5:0] id_pipe [0:PIPELINE_DEPTH-1];
      logic [COST_WIDTH-1:0] cost_pipe [0:PIPELINE_DEPTH-1];
      logic overflow_pipe [0:PIPELINE_DEPTH-1];
      logic [PRODUCT_WIDTH-1:0] rate_stage0;
      logic [DIST_SCALED_WIDTH-1:0] distortion_stage0;
      logic [ACC_WIDTH-1:0] stage0_cost;
      integer stage;

      assign stage0_cost = {{(ACC_WIDTH-DIST_SCALED_WIDTH){1'b0}}, distortion_stage0}
                         + {{(ACC_WIDTH-PRODUCT_WIDTH){1'b0}}, rate_stage0};
      assign out_valid = valid_pipe[PIPELINE_DEPTH-1];
      assign out_candidate_id = id_pipe[PIPELINE_DEPTH-1];
      assign out_rd_cost_q = cost_pipe[PIPELINE_DEPTH-1];
      assign out_overflow = overflow_pipe[PIPELINE_DEPTH-1];

      always_ff @(posedge clk) begin
        if (!rst_n) begin
          rate_stage0 <= '0;
          distortion_stage0 <= '0;
          for (stage = 0; stage < PIPELINE_DEPTH; stage = stage + 1) begin
            valid_pipe[stage] <= 1'b0;
            id_pipe[stage] <= '0;
            cost_pipe[stage] <= '0;
            overflow_pipe[stage] <= 1'b0;
          end
        end else if (advance) begin
          for (stage = PIPELINE_DEPTH - 1; stage > 1; stage = stage - 1) begin
            valid_pipe[stage] <= valid_pipe[stage-1];
            id_pipe[stage] <= id_pipe[stage-1];
            cost_pipe[stage] <= cost_pipe[stage-1];
            overflow_pipe[stage] <= overflow_pipe[stage-1];
          end
          valid_pipe[1] <= valid_pipe[0];
          id_pipe[1] <= id_pipe[0];
          cost_pipe[1] <= |stage0_cost[ACC_WIDTH-1:COST_WIDTH]
                        ? {COST_WIDTH{1'b1}} : stage0_cost[COST_WIDTH-1:0];
          overflow_pipe[1] <= |stage0_cost[ACC_WIDTH-1:COST_WIDTH];
          valid_pipe[0] <= in_valid;
          id_pipe[0] <= in_candidate_id;
          cost_pipe[0] <= '0;
          overflow_pipe[0] <= 1'b0;
          rate_stage0 <= in_rate_bits * in_lambda_q;
          distortion_stage0 <= {in_distortion, {LAMBDA_FRACTION{1'b0}}};
        end
      end
    end
  endgenerate

  assign advance = !out_valid || out_ready;
  assign in_ready = advance;

  initial begin
    if (PIPELINE_DEPTH < 1) $fatal(1, "PIPELINE_DEPTH must be positive");
    if (COST_WIDTH >= ACC_WIDTH) $fatal(1, "COST_WIDTH must be smaller than ACC_WIDTH");
  end
endmodule
