#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/gcp_common.sh"

CURRENT_VERIFIED_SPEND="${CURRENT_VERIFIED_SPEND:-}"
CURRENT_VERIFIED_REMAINING_CREDIT="${CURRENT_VERIFIED_REMAINING_CREDIT:-}"
BILLING_DATA_STATUS="${BILLING_DATA_STATUS:-unverified}"
VERIFICATION_SOURCE="${VERIFICATION_SOURCE:-none}"
WORKER_COUNT="${WORKER_COUNT:-1}"
CAMPAIGN_CLASS="${CAMPAIGN_CLASS:-high-information}"
OUTPUT_PATH=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --current-verified-spend) CURRENT_VERIFIED_SPEND="$2"; shift 2 ;;
    --current-verified-remaining-credit) CURRENT_VERIFIED_REMAINING_CREDIT="$2"; shift 2 ;;
    --billing-data-status) BILLING_DATA_STATUS="$2"; shift 2 ;;
    --verification-source) VERIFICATION_SOURCE="$2"; shift 2 ;;
    --worker-count) WORKER_COUNT="$2"; shift 2 ;;
    --campaign-class) CAMPAIGN_CLASS="$2"; shift 2 ;;
    --output) OUTPUT_PATH="$2"; shift 2 ;;
    *) printf 'unknown argument: %s\n' "$1" >&2; exit 2 ;;
  esac
done

payload="$(python3 - "${CURRENT_VERIFIED_SPEND}" "${CURRENT_VERIFIED_REMAINING_CREDIT}" \
  "${BILLING_DATA_STATUS}" "${VERIFICATION_SOURCE}" "${WORKER_COUNT}" "${CAMPAIGN_CLASS}" \
  "${VM_HOURLY_USD}" \
  "${DISK_GB_HOURLY_USD}" "${DISK_SIZE_GB}" "${IPV4_HOURLY_USD}" \
  "${MAX_LIFETIME_MINUTES}" "${HARD_STOP_USD}" "${EXPERIMENT_ID}" \
  "${PROJECT_ID}" "${ZONE}" "${MACHINE_TYPE}" "${TRIAL_CREDIT_USD}" \
  "${PREVIOUS_AUTHORIZED_LIMIT_USD}" "${SAFETY_RESERVE_USD}" <<'PY'
import json
import sys
from datetime import datetime, timedelta, timezone

(current_text, remaining_text, billing_status, verification_source, worker_count,
 campaign_class, vm_hourly, disk_gb_hourly, disk_gb, ipv4_hourly, lifetime,
 hard_stop, experiment_id, project, zone, machine, trial_credit, previous_limit,
 safety_reserve) = sys.argv[1:]
current = float(current_text) if current_text else None
remaining = float(remaining_text) if remaining_text else None
worker_count = int(worker_count)
vm_hourly = float(vm_hourly)
disk_hourly = float(disk_gb_hourly) * int(disk_gb)
ipv4_hourly = float(ipv4_hourly)
lifetime = int(lifetime)
hard_stop = float(hard_stop)
trial_credit = float(trial_credit)
previous_limit = float(previous_limit)
safety_reserve = float(safety_reserve)
if billing_status not in {"verified", "unverified", "delayed"}:
    raise SystemExit("billing data status must be verified, unverified, or delayed")
if campaign_class not in {"high-information", "reduced-sweep", "broad-sweep"}:
    raise SystemExit("invalid campaign class")
values = [vm_hourly, disk_hourly, ipv4_hourly, hard_stop, trial_credit, previous_limit, safety_reserve]
if current is not None:
    values.append(current)
if remaining is not None:
    values.append(remaining)
if min(values) < 0 or not 1 <= lifetime <= 360 or not 1 <= worker_count <= 32:
    raise SystemExit("invalid cost or lifetime input")
verified = billing_status == "verified" and current is not None and remaining is not None
hours = lifetime / 60
expected = (vm_hourly + disk_hourly + ipv4_hourly) * hours * worker_count
projected = current + expected if current is not None else None
if remaining is None:
    mode, mode_worker_limit = "unverified", 0
elif remaining < 20:
    mode, mode_worker_limit = "stop", 0
elif remaining < 30:
    mode, mode_worker_limit = "strict", 1
elif remaining < 60:
    mode, mode_worker_limit = "cautious", 2
elif remaining < 100:
    mode, mode_worker_limit = "reduced", 4
else:
    mode, mode_worker_limit = "standard", 8
available_after_reserve = max(0.0, remaining - safety_reserve) if remaining is not None else None
authorization_headroom = max(0.0, hard_stop - current) if current is not None else None
affordable_campaign_cost = (min(available_after_reserve, authorization_headroom)
                            if verified else None)
class_allowed = not (mode in {"strict", "cautious"} and campaign_class != "high-information")
launch_allowed = bool(
    verified and expected <= affordable_campaign_cost and worker_count <= mode_worker_limit
    and class_allowed and mode != "stop"
)
now = datetime.now(timezone.utc)
record = {
    "schema_version": "chia-rdo.gcp-cost-estimate.v2",
    "created_utc": now.isoformat().replace("+00:00", "Z"),
    "experiment_id": experiment_id,
    "project_id": project,
    "zone": zone,
    "machine_type": machine,
    "worker_count": worker_count,
    "campaign_class": campaign_class,
    "spot": False,
    "spot_unavailable_reason": "regional PREEMPTIBLE_CPUS quota is 0",
    "maximum_lifetime_minutes": lifetime,
    "estimated_runtime_hours": hours,
    "cleanup_deadline_utc": (now + timedelta(minutes=lifetime)).isoformat().replace("+00:00", "Z"),
    "output_directory": f"results/cloud/{experiment_id}",
    "price_assumptions_usd_per_hour": {
        "vm": vm_hourly,
        "persistent_disk": disk_hourly,
        "external_ipv4": ipv4_hourly,
    },
    "current_verified_spend": current if verified else None,
    "current_verified_remaining_credit": remaining if verified else None,
    "estimated_campaign_cost": round(expected, 6),
    "authorized_campaign_limit": hard_stop,
    "previous_authorized_limit": previous_limit,
    "safety_reserve": safety_reserve,
    "approximate_original_trial_credit": trial_credit,
    "projected_cumulative_spend": round(projected, 6) if verified else None,
    "available_campaign_credit_after_reserve": round(available_after_reserve, 6) if verified else None,
    "affordable_campaign_cost": round(affordable_campaign_cost, 6) if verified else None,
    "billing_data_status": billing_status,
    "verification_source": verification_source,
    "budget_mode": mode,
    "mode_worker_limit": mode_worker_limit,
    "actual_billed_spend": {"status": "verified" if verified else "unverified", "value_usd": current if verified else None},
    "estimated_spend": {"status": "estimated", "value_usd": round(expected, 6)},
    "promotional_free_credit_consumption": {"status": "unverified", "value_usd": None},
    "unconfirmed_billing_data": not verified,
    "launch_allowed": launch_allowed,
    "gate_reasons": [reason for condition, reason in (
        (not verified, "current spend and remaining promotional credit are not verified"),
        (mode == "stop", "remaining credit is below the USD 20 safety reserve"),
        (worker_count > mode_worker_limit, "worker count exceeds the active budget-mode limit"),
        (not class_allowed, "campaign class is forbidden by the active budget mode"),
        (verified and expected > affordable_campaign_cost, "estimated campaign cost exceeds verified affordable headroom"),
    ) if condition],
    "limitations": [
        "A launch requires verified current spend and remaining promotional credit; estimates never satisfy this requirement.",
        "Prices are conservative public list-price assumptions and exclude tax.",
        "Promotional-credit consumption is not inferred from the approximate original trial-credit amount.",
    ],
}
print(json.dumps(record, indent=2, sort_keys=True))
PY
)"

printf '%s\n' "${payload}"
if [[ -n "${OUTPUT_PATH}" ]]; then
  mkdir -p "$(dirname "${OUTPUT_PATH}")"
  printf '%s\n' "${payload}" >"${OUTPUT_PATH}"
fi
if [[ "$(python3 -c 'import json,sys; print(json.load(sys.stdin)["launch_allowed"])' <<<"${payload}")" != "True" ]]; then
  exit 3
fi
