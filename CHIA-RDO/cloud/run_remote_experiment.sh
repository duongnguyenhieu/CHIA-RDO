#!/usr/bin/env bash
set -euo pipefail

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

instance_status="$(gcloud compute instances describe "${INSTANCE_NAME}" \
  --project="${PROJECT_ID}" --zone="${ZONE}" --format='value(status)')"
if [[ "${instance_status}" == "TERMINATED" ]]; then
  gcloud compute instances start "${INSTANCE_NAME}" \
    --project="${PROJECT_ID}" --zone="${ZONE}" --quiet
fi

ssh_ready=0
for _ in {1..24}; do
  if gcloud compute ssh "${INSTANCE_NAME}" --project="${PROJECT_ID}" --zone="${ZONE}" \
    --quiet --command=true >/dev/null 2>&1; then
    ssh_ready=1
    break
  fi
  sleep 5
done
if (( ! ssh_ready )); then
  printf 'SSH did not become ready within 120 seconds\n' >&2
  exit 3
fi

bundle="/tmp/opencode/chia-rdo-parity.bundle"
git -C "${ROOT}" bundle create "${bundle}" HEAD
gcloud compute scp "${bundle}" "${INSTANCE_NAME}:~/chia-rdo.bundle" \
  --project="${PROJECT_ID}" --zone="${ZONE}" --quiet
gcloud compute scp "${ROOT}/software/run_baseline.py" \
  "${INSTANCE_NAME}:~/run_baseline.py" \
  --project="${PROJECT_ID}" --zone="${ZONE}" --quiet

remote_command=$(cat <<'REMOTE'
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update
sudo apt-get install -y build-essential git python3
rm -rf "$HOME/chia"
git clone "$HOME/chia-rdo.bundle" "$HOME/chia"
cp "$HOME/run_baseline.py" "$HOME/chia/CHIA-RDO/software/run_baseline.py"
cd "$HOME/chia/CHIA-RDO"
JOBS=2 ./scripts/setup_hm.sh
timeout 20m env CHIA_RDO_CLOUD_BACKEND=gcp-compute \
  python3 software/run_baseline.py --config configs/baseline_smoke.json --replicate gcp-parity
REMOTE
)
gcloud compute ssh "${INSTANCE_NAME}" --project="${PROJECT_ID}" --zone="${ZONE}" \
  --quiet --command="${remote_command}"
trap - EXIT
