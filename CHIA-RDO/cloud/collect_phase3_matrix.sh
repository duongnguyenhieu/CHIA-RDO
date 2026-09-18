#!/usr/bin/env bash
set -euo pipefail

export INSTANCE_NAME="${INSTANCE_NAME:-chia-rdo-phase3}"
export EXPERIMENT_ID="${EXPERIMENT_ID:-phase3-matched-matrix}"
source "$(dirname "${BASH_SOURCE[0]}")/gcp_common.sh"
mkdir -p "${RESULT_DIR}/remote"
if instance_exists; then
  gcloud compute scp --recurse "${INSTANCE_NAME}:~/chia/CHIA-RDO/results/baseline" "${RESULT_DIR}/remote/" --project="${PROJECT_ID}" --zone="${ZONE}" --quiet || true
  gcloud compute scp --recurse "${INSTANCE_NAME}:~/chia/CHIA-RDO/results/policy" "${RESULT_DIR}/remote/" --project="${PROJECT_ID}" --zone="${ZONE}" --quiet || true
  gcloud compute scp --recurse "${INSTANCE_NAME}:~/chia/CHIA-RDO/results/experiments" "${RESULT_DIR}/remote/" --project="${PROJECT_ID}" --zone="${ZONE}" --quiet || true
fi
"${ROOT}/cloud/cleanup.sh"
