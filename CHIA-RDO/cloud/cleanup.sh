#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/gcp_common.sh"
require_command gcloud

creation_timestamp=""
if instance_exists; then
  creation_timestamp="$(gcloud compute instances describe "${INSTANCE_NAME}" \
    --project="${PROJECT_ID}" --zone="${ZONE}" --format='value(creationTimestamp)')"
  gcloud compute instances delete "${INSTANCE_NAME}" \
    --project="${PROJECT_ID}" --zone="${ZONE}" --delete-disks=all --quiet
else
  printf 'instance absent; nothing to delete\n'
fi

leftovers="$(gcloud compute instances list --project="${PROJECT_ID}" \
  --filter='labels.project=chia-rdo' --format='value(name)')"
if [[ -n "${leftovers}" ]]; then
  printf 'CHIA-RDO instances remain after cleanup:\n%s\n' "${leftovers}" >&2
  exit 3
fi
disk_leftovers="$(gcloud compute disks list --project="${PROJECT_ID}" \
  --filter="name=${INSTANCE_NAME}" --format='value(name)')"
if [[ -n "${disk_leftovers}" ]]; then
  printf 'CHIA-RDO disks remain after cleanup:\n%s\n' "${disk_leftovers}" >&2
  exit 3
fi

if [[ -n "${creation_timestamp}" && -f "${LAUNCH_RECORD}" ]]; then
  python3 - "${LAUNCH_RECORD}" "${creation_timestamp}" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

path = Path(sys.argv[1])
started = datetime.fromisoformat(sys.argv[2].replace("Z", "+00:00"))
ended = datetime.now(timezone.utc)
record = json.loads(path.read_text())
hours = max(60, (ended - started).total_seconds()) / 3600
rates = record["price_assumptions_usd_per_hour"]
record["terminated_utc"] = ended.isoformat().replace("+00:00", "Z")
record["wall_elapsed_hours"] = round(hours, 6)
record["estimated_cost_upper_bound_usd"] = round(sum(rates.values()) * hours, 6)
record["limitations"].append(
    "The cost upper bound charges every resource for the full wall interval, including stopped periods; actual billed cost requires a delayed Billing report."
)
record["status"] = "cleaned"
path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
PY
fi
printf 'cleanup verified: no CHIA-RDO instance or boot disk remains\n'
