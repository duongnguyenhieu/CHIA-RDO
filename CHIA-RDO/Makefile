PYTHON ?= python3

.PHONY: environment hm dataset baseline phase1-gate fixed-pilot adaptive-pilot test

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

fixed-pilot:
	for k in 2 4 8 16 35; do $(PYTHON) software/run_policy.py --policy fixed --k $$k; done

adaptive-pilot:
	$(PYTHON) software/run_policy.py --policy adaptive_v0

test:
	$(PYTHON) -m unittest discover -s tests -v
