#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/gcp_common.sh"
require_command gcloud
require_command python3

checkpointed=0
finish_collection() {
  status=$?
  if (( checkpointed )); then
    "${ROOT}/cloud/cleanup.sh" || status=$?
  else
    "${ROOT}/cloud/shutdown_vm.sh" || true
  fi
  exit "${status}"
}
trap finish_collection EXIT

mkdir -p "${RESULT_DIR}"
remote_result="results/baseline/${EXPERIMENT_ID}"
gcloud compute scp --recurse \
  "${INSTANCE_NAME}:~/chia/CHIA-RDO/${remote_result}" "${RESULT_DIR}/baseline" \
  --project="${PROJECT_ID}" --zone="${ZONE}" --quiet
gcloud compute scp --recurse \
  "${INSTANCE_NAME}:~/chia/CHIA-RDO/logs/baseline/${EXPERIMENT_ID}" "${RESULT_DIR}/logs" \
  --project="${PROJECT_ID}" --zone="${ZONE}" --quiet
checkpointed=1

python3 - "${ROOT}" "${RESULT_DIR}" <<'PY'
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

root, result_dir = map(Path, sys.argv[1:])
local = json.loads((root / "results/baseline/tiny64-all-intra-full-rdo-qp32-faed5f414b11/result.json").read_text())
remote = json.loads((result_dir / "baseline/result.json").read_text())
metric_keys = sorted(set(local["metrics"]) | set(remote["metrics"]))
metric_differences = {key: [local["metrics"].get(key), remote["metrics"].get(key)]
                      for key in metric_keys if local["metrics"].get(key) != remote["metrics"].get(key)}
artifact_keys = ["bitstream_sha256", "reconstruction_sha256"]
artifact_differences = {key: [local["artifacts"].get(key), remote["artifacts"].get(key)]
                        for key in artifact_keys if local["artifacts"].get(key) != remote["artifacts"].get(key)}
trace = result_dir / "baseline/intra-rdo.jsonl"
trace_hash = hashlib.sha256(trace.read_bytes()).hexdigest()
comparison = {
    "schema_version": "chia-rdo.local-gcp-parity.v1",
    "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "status": "pass" if not metric_differences and not artifact_differences else "fail",
    "local_experiment_id": local["experiment_id"],
    "remote_experiment_id": remote["experiment_id"],
    "metric_differences": metric_differences,
    "artifact_differences": artifact_differences,
    "remote_trace_sha256": trace_hash,
    "timing_compared": False,
    "timing_exclusion_reason": "Wall and CPU timing are host-dependent telemetry, not parity criteria.",
}
(result_dir / "parity.json").write_text(json.dumps(comparison, indent=2, sort_keys=True) + "\n")
print(json.dumps(comparison, indent=2, sort_keys=True))
if comparison["status"] != "pass":
    raise SystemExit(3)
PY
