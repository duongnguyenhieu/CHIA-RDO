#!/usr/bin/env bash

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_ID="${PROJECT_ID:-chia-rdo-project}"
ZONE="${ZONE:-us-central1-a}"
REGION="${ZONE%-*}"
INSTANCE_NAME="${INSTANCE_NAME:-chia-rdo-parity}"
MACHINE_TYPE="${MACHINE_TYPE:-e2-standard-2}"
DISK_SIZE_GB="${DISK_SIZE_GB:-15}"
MAX_LIFETIME_MINUTES="${MAX_LIFETIME_MINUTES:-55}"
EXPERIMENT_ID="${EXPERIMENT_ID:-tiny64-all-intra-full-rdo-qp32-faed5f414b11-gcp-parity}"
EXPERIMENT_LABEL="${EXPERIMENT_LABEL:-phase1-parity}"
RESOURCE_PURPOSE="${RESOURCE_PURPOSE:-validation}"
RESULT_DIR="${ROOT}/results/cloud/${EXPERIMENT_ID}"
LAUNCH_RECORD="${RESULT_DIR}/launch.json"

# Conservative public list-price assumptions for us-central1, checked 2026-09-08.
VM_HOURLY_USD="${VM_HOURLY_USD:-0.067012}"
DISK_GB_HOURLY_USD="${DISK_GB_HOURLY_USD:-0.0000548}"
IPV4_HOURLY_USD="${IPV4_HOURLY_USD:-0.005}"
TRIAL_CREDIT_USD="${TRIAL_CREDIT_USD:-300}"
PREVIOUS_AUTHORIZED_LIMIT_USD="${PREVIOUS_AUTHORIZED_LIMIT_USD:-220}"
HARD_STOP_USD="${HARD_STOP_USD:-280}"
SAFETY_RESERVE_USD="${SAFETY_RESERVE_USD:-20}"

require_command() {
  command -v "$1" >/dev/null 2>&1 || {
    printf 'required command not found: %s\n' "$1" >&2
    exit 2
  }
}

instance_exists() {
  gcloud compute instances describe "${INSTANCE_NAME}" \
    --project="${PROJECT_ID}" --zone="${ZONE}" >/dev/null 2>&1
}
