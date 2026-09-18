# RTL Scheduler Regression

Status: PASS

Verilator passed 2,000 cases with 0 failures. Each of P=1/2/4/8 ran 160 HM-derived and 340 deterministic randomized vectors covering K=2/4/8/16/35 and stable cost ties. The checked kernel covers buffering, candidate dispatch, ceil(K/P) batch accounting, pipeline drain, and best-candidate reduction; it is not a complete HEVC transform/quantization datapath.
