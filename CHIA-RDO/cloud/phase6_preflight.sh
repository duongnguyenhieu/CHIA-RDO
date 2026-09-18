#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/gcp_common.sh"
require_command gcloud
require_command python3

OUTPUT="${ROOT}/cloud/gcp_phase6_budget.json"
BILLING_INFO="$(gcloud billing projects describe "${PROJECT_ID}" --format=json)"
INSTANCES="$(gcloud compute instances list --project="${PROJECT_ID}" --filter='labels.phase=phase6' --format=json)"
DISKS="$(gcloud compute disks list --project="${PROJECT_ID}" --filter='labels.phase=phase6' --format=json)"
ADDRESSES="$(gcloud compute addresses list --project="${PROJECT_ID}" --filter='labels.phase=phase6' --format=json)"

python3 - "${OUTPUT}" "${PROJECT_ID}" "${ZONE}" "${BILLING_INFO}" "${INSTANCES}" "${DISKS}" "${ADDRESSES}" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

output, project, zone, billing_text, instances_text, disks_text, addresses_text = sys.argv[1:]
billing = json.loads(billing_text)
instances = json.loads(instances_text)
disks = json.loads(disks_text)
addresses = json.loads(addresses_text)
vm_hourly = 0.268048
disk_hourly = 15 * 0.0000548
ipv4_hourly = 0.005
pilot_cost = 4 * (55 / 60) * (vm_hourly + disk_hourly + ipv4_hourly)
record = {
    "schema_version": "chia-rdo.phase6-budget.v1",
    "updated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "project_id": project,
    "zone": zone,
    "billing_account": billing.get("billingAccountName"),
    "billing_enabled": billing.get("billingEnabled") is True,
    "authorized_limit_usd": 280.0,
    "safety_reserve_usd": 20.0,
    "verified_spend_usd": None,
    "verified_spend_status": "UNAVAILABLE",
    "verified_remaining_credit_usd": None,
    "verified_remaining_credit_status": "UNAVAILABLE",
    "estimated_spend_usd": 0.0,
    "estimated_spend_status": "ESTIMATED",
    "planned_pilot": {
        "worker_count": 4,
        "machine_type": "e2-standard-8",
        "maximum_lifetime_minutes": 55,
        "estimated_cost_usd": round(pilot_cost, 6),
        "price_assumptions_usd_per_hour": {
            "vm": vm_hourly,
            "persistent_disk_15gb": disk_hourly,
            "external_ipv4": ipv4_hourly
        }
    },
    "completed_cloud_experiments": 0,
    "active_workers": len(instances),
    "leftover_resources": {"instances": instances, "disks": disks, "addresses": addresses},
    "cleanup_verified": not instances and not disks and not addresses,
    "launch_allowed": False,
    "gate_reason": "Current billed spend and remaining promotional credit are not available from an authoritative query.",
    "verification_source": "gcloud billing project linkage and resource inventory; no Billing export or credit-balance API available",
}
Path(output).write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
print(json.dumps(record, indent=2, sort_keys=True))
PY

exit 3
