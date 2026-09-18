#!/usr/bin/env bash
set -euo pipefail

export INSTANCE_NAME="${INSTANCE_NAME:-chia-rdo-phase2}"
export EXPERIMENT_ID="${EXPERIMENT_ID:-phase2-adaptive-k-sweep}"
source "$(dirname "${BASH_SOURCE[0]}")/gcp_common.sh"
require_command gcloud
require_command git

stop_after_failure() {
  status=$?
  if (( status != 0 )); then
    "${ROOT}/cloud/shutdown_vm.sh" || true
  fi
  exit "${status}"
}
trap stop_after_failure EXIT

if ! instance_exists; then
  printf 'instance does not exist: %s\n' "${INSTANCE_NAME}" >&2
  exit 2
fi
status="$(gcloud compute instances describe "${INSTANCE_NAME}" --project="${PROJECT_ID}" \
  --zone="${ZONE}" --format='value(status)')"
if [[ "${status}" == "TERMINATED" ]]; then
  gcloud compute instances start "${INSTANCE_NAME}" --project="${PROJECT_ID}" --zone="${ZONE}" --quiet
fi
ready=0
for _ in {1..24}; do
  if gcloud compute ssh "${INSTANCE_NAME}" --project="${PROJECT_ID}" --zone="${ZONE}" \
    --quiet --command=true >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 5
done
if (( ! ready )); then
  printf 'SSH did not become ready within 120 seconds\n' >&2
  exit 3
fi

bundle="/tmp/opencode/chia-rdo-phase2.bundle"
git -C "${ROOT}" bundle create "${bundle}" HEAD
gcloud compute scp "${bundle}" "${INSTANCE_NAME}:~/chia-rdo.bundle" \
  --project="${PROJECT_ID}" --zone="${ZONE}" --quiet
gcloud compute ssh "${INSTANCE_NAME}" --project="${PROJECT_ID}" --zone="${ZONE}" --quiet \
  --command='rm -rf "$HOME/chia"; git clone "$HOME/chia-rdo.bundle" "$HOME/chia"'

remote_root="${INSTANCE_NAME}:~/chia/CHIA-RDO"
for relative in \
  scripts/setup_hm.sh \
  software/run_baseline.py \
  software/run_policy.py \
  software/patches/hm-16.20-phase2-k-policy.patch; do
  gcloud compute scp "${ROOT}/${relative}" "${remote_root}/${relative}" \
    --project="${PROJECT_ID}" --zone="${ZONE}" --quiet
done
reference_dir="results/baseline/tiny64-all-intra-full-rdo-qp32-faed5f414b11"
gcloud compute scp "${ROOT}/${reference_dir}/intra-rdo.jsonl" \
  "${remote_root}/${reference_dir}/intra-rdo.jsonl" \
  --project="${PROJECT_ID}" --zone="${ZONE}" --quiet

remote_command=$(cat <<'REMOTE'
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update
sudo apt-get install -y build-essential git python3
cd "$HOME/chia/CHIA-RDO"
JOBS=2 ./scripts/setup_hm.sh
timeout 25m python3 software/run_policy.py --policy adaptive_v0 --medium-threshold 0.045 --high-threshold 0.088 --high-k 4 --medium-k 8 --low-k 16
timeout 25m python3 software/run_policy.py --policy adaptive_v0 --medium-threshold 0.02 --high-threshold 0.088 --high-k 4 --medium-k 8 --low-k 35
timeout 25m python3 software/run_policy.py --policy adaptive_v0 --medium-threshold 0.02 --high-threshold 0.045 --high-k 8 --medium-k 16 --low-k 35
timeout 25m python3 software/run_policy.py --policy adaptive_v0 --medium-threshold 0.045 --high-threshold 0.15 --high-k 8 --medium-k 16 --low-k 35
REMOTE
)
gcloud compute ssh "${INSTANCE_NAME}" --project="${PROJECT_ID}" --zone="${ZONE}" \
  --quiet --command="${remote_command}"
trap - EXIT
