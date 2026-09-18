# GCP Phase 3 Usage

Status: PASS

Two guarded ephemeral `e2-standard-2` matrix runs produced 56 policy and 4 Full-RDO records. Every coding metric, bitstream, reconstruction, and policy trace hash matches the corresponding local run. Two additional guarded online-search runs on `e2-standard-2` and `e2-standard-8` each completed the same 12 configurations. Their coding metrics and artifact hashes match exactly across machine types, and all collected artifact contents match their recorded hashes. The conservative combined creation-to-deletion cost upper bound is USD 1.494844; actual delayed billing is unavailable. The first run checkpointed QP22/27 before a missing ignored QP32 trace exposed a cache-validity defect; its failure trap deleted the VM. The resumed run completed QP32/37. The `e2-standard-8` search auto-stopped at its hardware deadline after completing, was restarted for collection, and was then deleted. Final resource checks found no instances, disks, or reserved addresses.
