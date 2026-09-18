#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/gcp_common.sh"
require_command gcloud
require_command python3

DRY_RUN=0
CURRENT_VERIFIED_SPEND="${CURRENT_VERIFIED_SPEND:-}"
CURRENT_VERIFIED_REMAINING_CREDIT="${CURRENT_VERIFIED_REMAINING_CREDIT:-}"
BILLING_DATA_STATUS="${BILLING_DATA_STATUS:-unverified}"
VERIFICATION_SOURCE="${VERIFICATION_SOURCE:-none}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --current-verified-spend) CURRENT_VERIFIED_SPEND="$2"; shift 2 ;;
    --current-verified-remaining-credit) CURRENT_VERIFIED_REMAINING_CREDIT="$2"; shift 2 ;;
    --billing-data-status) BILLING_DATA_STATUS="$2"; shift 2 ;;
    --verification-source) VERIFICATION_SOURCE="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    *) printf 'unknown argument: %s\n' "$1" >&2; exit 2 ;;
  esac
done

mkdir -p "${RESULT_DIR}"
CURRENT_VERIFIED_SPEND="${CURRENT_VERIFIED_SPEND}" \
CURRENT_VERIFIED_REMAINING_CREDIT="${CURRENT_VERIFIED_REMAINING_CREDIT}" \
BILLING_DATA_STATUS="${BILLING_DATA_STATUS}" VERIFICATION_SOURCE="${VERIFICATION_SOURCE}" \
"${ROOT}/cloud/estimate_cost.sh" \
  --output "${LAUNCH_RECORD}"

if instance_exists; then
  printf 'instance already exists: %s (%s)\n' "${INSTANCE_NAME}" "${ZONE}"
  exit 0
fi
if (( DRY_RUN )); then
  printf 'dry run: preflight passed; no resource created\n'
  exit 0
fi

expiry="$(python3 - "${MAX_LIFETIME_MINUTES}" <<'PY'
from datetime import datetime, timedelta, timezone
import sys
print((datetime.now(timezone.utc) + timedelta(minutes=int(sys.argv[1]))).strftime("%Y%m%dt%H%M%Sz").lower())
PY
)"
gcloud compute instances create "${INSTANCE_NAME}" \
  --project="${PROJECT_ID}" \
  --zone="${ZONE}" \
  --machine-type="${MACHINE_TYPE}" \
  --image-family=ubuntu-2404-lts-amd64 \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size="${DISK_SIZE_GB}GB" \
  --boot-disk-type=pd-standard \
  --labels="project=chia-rdo,experiment=${EXPERIMENT_LABEL},purpose=${RESOURCE_PURPOSE},expiry=${expiry}" \
  --metadata="max-lifetime-minutes=${MAX_LIFETIME_MINUTES}" \
  --metadata-from-file="startup-script=${ROOT}/cloud/startup_shutdown.sh" \
  --no-service-account \
  --no-scopes

python3 - "${LAUNCH_RECORD}" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

path = Path(sys.argv[1])
record = json.loads(path.read_text())
record["launch_utc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
record["status"] = "running"
path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
PY

printf 'created %s; hardware auto-shutdown is scheduled in %s minutes\n' \
  "${INSTANCE_NAME}" "${MAX_LIFETIME_MINUTES}"
