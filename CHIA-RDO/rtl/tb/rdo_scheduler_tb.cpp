#include "Vrdo_scheduler.h"
#include "verilated.h"

#include <cstdint>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

struct Candidate { unsigned id; uint64_t cost; };
struct Vector { std::vector<Candidate> candidates; unsigned expected_id; uint64_t expected_cost; };

static void tick(Vrdo_scheduler& dut) {
  dut.clk = 0; dut.eval();
  dut.clk = 1; dut.eval();
}

static std::vector<Vector> load_vectors(const std::string& path) {
  std::ifstream input(path);
  if (!input) throw std::runtime_error("cannot open vectors");
  std::vector<Vector> vectors;
  std::string line;
  while (std::getline(input, line)) {
    std::istringstream stream(line);
    unsigned count;
    Vector vector;
    stream >> count >> vector.expected_id >> vector.expected_cost;
    for (unsigned index = 0; index < count; ++index) {
      Candidate candidate{};
      stream >> candidate.id >> candidate.cost;
      vector.candidates.push_back(candidate);
    }
    if (!stream || vector.candidates.size() != count) throw std::runtime_error("invalid vector line");
    vectors.push_back(vector);
  }
  return vectors;
}

int main(int argc, char** argv) {
  Verilated::commandArgs(argc, argv);
  if (argc != 3) return 2;
  const unsigned parallelism = std::stoul(argv[2]);
  const auto vectors = load_vectors(argv[1]);
  Vrdo_scheduler dut;
  dut.rst_n = 0; dut.start = 0; dut.candidate_valid = 0; tick(dut); tick(dut);
  dut.rst_n = 1; tick(dut);
  unsigned passed = 0;
  for (const auto& vector : vectors) {
    dut.candidate_count = vector.candidates.size(); dut.start = 1; tick(dut); dut.start = 0;
    for (const auto& candidate : vector.candidates) {
      if (!dut.candidate_ready) return 3;
      dut.candidate_id = candidate.id; dut.candidate_cost = candidate.cost;
      dut.candidate_valid = 1; tick(dut);
    }
    dut.candidate_valid = 0;
    unsigned timeout = 200;
    while (!dut.done && timeout--) tick(dut);
    const unsigned expected_batches = (vector.candidates.size() + parallelism - 1) / parallelism;
    if (!dut.done || dut.best_id != vector.expected_id || dut.best_cost != vector.expected_cost || dut.batch_count != expected_batches) {
      std::cerr << "FAIL P=" << parallelism << " expected id/cost/batches " << vector.expected_id << "/"
                << vector.expected_cost << "/" << expected_batches << " got " << unsigned(dut.best_id) << "/"
                << uint64_t(dut.best_cost) << "/" << unsigned(dut.batch_count) << "\n";
      return 1;
    }
    ++passed;
    tick(dut);
  }
  std::cout << "{\"p\":" << parallelism << ",\"pass\":" << passed << ",\"fail\":0}" << std::endl;
  return 0;
}
