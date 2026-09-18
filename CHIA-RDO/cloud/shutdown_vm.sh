#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/gcp_common.sh"
require_command gcloud

if ! instance_exists; then
  printf 'instance absent; nothing to stop\n'
  exit 0
fi
status="$(gcloud compute instances describe "${INSTANCE_NAME}" \
  --project="${PROJECT_ID}" --zone="${ZONE}" --format='value(status)')"
if [[ "${status}" == "TERMINATED" ]]; then
  printf 'instance already stopped\n'
  exit 0
fi
gcloud compute instances stop "${INSTANCE_NAME}" \
  --project="${PROJECT_ID}" --zone="${ZONE}" --quiet
