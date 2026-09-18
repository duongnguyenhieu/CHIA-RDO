#!/usr/bin/env bash
set -euo pipefail

export INSTANCE_NAME="${INSTANCE_NAME:-chia-rdo-phase2}"
export EXPERIMENT_ID="${EXPERIMENT_ID:-phase2-adaptive-k-sweep}"
source "$(dirname "${BASH_SOURCE[0]}")/gcp_common.sh"
require_command gcloud

checkpointed=0
finish() {
  status=$?
  if (( checkpointed )); then
    "${ROOT}/cloud/cleanup.sh" || status=$?
  else
    "${ROOT}/cloud/shutdown_vm.sh" || true
  fi
  exit "${status}"
}
trap finish EXIT

mkdir -p "${RESULT_DIR}"
gcloud compute scp --recurse "${INSTANCE_NAME}:~/chia/CHIA-RDO/results/policy" \
  "${RESULT_DIR}/policy" --project="${PROJECT_ID}" --zone="${ZONE}" --quiet
gcloud compute scp --recurse "${INSTANCE_NAME}:~/chia/CHIA-RDO/logs/policy" \
  "${RESULT_DIR}/logs" --project="${PROJECT_ID}" --zone="${ZONE}" --quiet
checkpointed=1
