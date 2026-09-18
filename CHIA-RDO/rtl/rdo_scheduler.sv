module rdo_scheduler #(
  parameter int P = 4,
  parameter int PIPELINE_DEPTH = 2,
  parameter int COST_WIDTH = 48,
  parameter int BUFFER_DEPTH = 35
) (
  input  logic                  clk,
  input  logic                  rst_n,
  input  logic                  start,
  input  logic [5:0]            candidate_count,
  input  logic                  candidate_valid,
  input  logic [5:0]            candidate_id,
  input  logic [COST_WIDTH-1:0] candidate_cost,
  output logic                  candidate_ready,
  output logic                  done,
  output logic [5:0]            best_id,
  output logic [COST_WIDTH-1:0] best_cost,
  output logic [5:0]            batch_count
);
  typedef enum logic [1:0] {IDLE, LOAD, PROCESS, DRAIN} state_t;
  state_t state;
  logic [5:0] ids [0:BUFFER_DEPTH-1];
  logic [COST_WIDTH-1:0] costs [0:BUFFER_DEPTH-1];
  integer active_count;
  integer load_index;
  integer process_index;
  integer drain_count;
  logic [5:0] next_best_id;
  logic [COST_WIDTH-1:0] next_best_cost;
  integer lane;

  assign candidate_ready = state == LOAD;

  always_comb begin
    next_best_id = best_id;
    next_best_cost = best_cost;
    for (lane = 0; lane < P; lane = lane + 1) begin
      if (process_index + lane < active_count && costs[process_index + lane] < next_best_cost) begin
        next_best_cost = costs[process_index + lane];
        next_best_id = ids[process_index + lane];
      end
    end
  end

  always_ff @(posedge clk) begin
    if (!rst_n) begin
      state <= IDLE;
      done <= 1'b0;
      best_id <= '0;
      best_cost <= {COST_WIDTH{1'b1}};
      batch_count <= '0;
      active_count <= 0;
      load_index <= 0;
      process_index <= 0;
      drain_count <= 0;
    end else begin
      done <= 1'b0;
      case (state)
        IDLE: if (start && candidate_count > 0 && int'(candidate_count) <= BUFFER_DEPTH) begin
          active_count <= int'(candidate_count);
          load_index <= 0;
          best_id <= '0;
          best_cost <= {COST_WIDTH{1'b1}};
          batch_count <= '0;
          state <= LOAD;
        end
        LOAD: if (candidate_valid) begin
          ids[load_index] <= candidate_id;
          costs[load_index] <= candidate_cost;
          if (load_index + 1 == active_count) begin
            process_index <= 0;
            state <= PROCESS;
          end else begin
            load_index <= load_index + 1'b1;
          end
        end
        PROCESS: begin
          best_id <= next_best_id;
          best_cost <= next_best_cost;
          batch_count <= batch_count + 1'b1;
          if (process_index + P >= active_count) begin
            drain_count <= PIPELINE_DEPTH;
            state <= DRAIN;
          end else begin
            process_index <= process_index + P;
          end
        end
        DRAIN: begin
          if (drain_count == 0) begin
            done <= 1'b1;
            state <= IDLE;
          end else begin
            drain_count <= drain_count - 1'b1;
          end
        end
        default: state <= IDLE;
      endcase
    end
  end
endmodule
