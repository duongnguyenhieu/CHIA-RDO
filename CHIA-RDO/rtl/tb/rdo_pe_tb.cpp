#include "Vrdo_pe.h"
#include "verilated.h"

#include <cstdint>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>

struct Vector {
  uint64_t distortion;
  uint64_t rate_bits;
  uint64_t lambda_q;
  uint64_t expected_cost;
  unsigned expected_overflow;
};

static void tick(Vrdo_pe& dut) {
  dut.clk = 0;
  dut.eval();
  dut.clk = 1;
  dut.eval();
}

int main(int argc, char** argv) {
  Verilated::commandArgs(argc, argv);
  if (argc != 2) return 2;
  std::ifstream input(argv[1]);
  if (!input) return 3;

  Vrdo_pe dut;
  dut.rst_n = 0;
  dut.in_valid = 0;
  dut.out_ready = 1;
  tick(dut);
  tick(dut);
  dut.rst_n = 1;
  tick(dut);

  std::string line;
  unsigned passed = 0;
  while (std::getline(input, line)) {
    std::istringstream stream(line);
    Vector vector{};
    stream >> vector.distortion >> vector.rate_bits >> vector.lambda_q
           >> vector.expected_cost >> vector.expected_overflow;
    if (!stream) return 4;

    dut.in_candidate_id = passed % 35;
    dut.in_distortion = vector.distortion;
    dut.in_rate_bits = vector.rate_bits;
    dut.in_lambda_q = vector.lambda_q;
    dut.in_valid = 1;
    dut.out_ready = 1;
    if (!dut.in_ready) return 5;
    tick(dut);
    dut.in_valid = 0;

    unsigned timeout = 20;
    if (passed % 11 == 0) {
      dut.out_ready = 0;
      tick(dut);
      tick(dut);
      dut.out_ready = 1;
    }
    while (!dut.out_valid && timeout--) tick(dut);
    if (!dut.out_valid || uint64_t(dut.out_rd_cost_q) != vector.expected_cost
        || unsigned(dut.out_overflow) != vector.expected_overflow
        || unsigned(dut.out_candidate_id) != passed % 35) {
      std::cerr << "FAIL vector " << passed << " expected cost/overflow "
                << vector.expected_cost << "/" << vector.expected_overflow << " got "
                << uint64_t(dut.out_rd_cost_q) << "/" << unsigned(dut.out_overflow) << "\n";
      return 1;
    }
    ++passed;
    tick(dut);
  }
  std::cout << "{\"pass\":" << passed << ",\"fail\":0}" << std::endl;
  return 0;
}
