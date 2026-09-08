PYTHON ?= python3

.PHONY: environment hm dataset baseline phase1-gate test

environment:
	$(PYTHON) --version
	cmake --version
	verilator --version

hm:
	./scripts/setup_hm.sh

dataset:
	$(PYTHON) software/generate_sequence.py datasets/generated/tiny-64x64-4f-yuv420p8.yuv

baseline: hm
	$(PYTHON) software/run_baseline.py

phase1-gate: baseline
	$(PYTHON) scripts/validate_phase1.py

test:
	$(PYTHON) -m unittest discover -s tests -v
