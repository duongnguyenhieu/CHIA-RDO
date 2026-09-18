#!/usr/bin/env bash
set -euo pipefail

export INSTANCE_NAME="${INSTANCE_NAME:-chia-rdo-phase3}"
export EXPERIMENT_ID="${EXPERIMENT_ID:-phase3-matched-matrix}"
source "$(dirname "${BASH_SOURCE[0]}")/gcp_common.sh"

cleanup_on_failure() {
  status=$?
  if (( status != 0 )); then "${ROOT}/cloud/collect_phase3_matrix.sh" || "${ROOT}/cloud/cleanup.sh" || true; fi
  exit "${status}"
}
trap cleanup_on_failure EXIT

ready=0
for _ in {1..36}; do
  if gcloud compute ssh "${INSTANCE_NAME}" --project="${PROJECT_ID}" --zone="${ZONE}" --quiet --command=true >/dev/null 2>&1; then ready=1; break; fi
  sleep 5
done
if (( ! ready )); then printf 'SSH did not become ready within 180 seconds\n' >&2; exit 3; fi

bundle="/tmp/opencode/chia-rdo-phase3.bundle"
git -C "${ROOT}" bundle create "${bundle}" HEAD
gcloud compute scp "${bundle}" "${INSTANCE_NAME}:~/chia-rdo.bundle" --project="${PROJECT_ID}" --zone="${ZONE}" --quiet
gcloud compute ssh "${INSTANCE_NAME}" --project="${PROJECT_ID}" --zone="${ZONE}" --quiet \
  --command='rm -rf "$HOME/chia"; git clone "$HOME/chia-rdo.bundle" "$HOME/chia"'

remote_root="${INSTANCE_NAME}:~/chia/CHIA-RDO"
for relative in \
  scripts/setup_hm.sh \
  software/run_baseline.py software/run_policy.py software/policy_algorithms.py \
  software/patches/hm-16.20-phase2-k-policy.patch \
  software/patches/hm-16.20-phase2-hardware-policy.patch \
  software/patches/hm-16.20-phase3-algorithms.patch \
  configs/baseline_smoke.json configs/phase3_qp22.json configs/phase3_qp27.json configs/phase3_qp37.json \
  experiments/run_phase3_matrix.py experiments/run_phase3_search.py; do
  gcloud compute scp "${ROOT}/${relative}" "${remote_root}/${relative}" --project="${PROJECT_ID}" --zone="${ZONE}" --quiet
done

remote_command="$(cat <<'REMOTE'
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update
sudo apt-get install -y build-essential git python3
cd "$HOME/chia/CHIA-RDO"
export CHIA_RDO_CLOUD_BACKEND=gcp-compute-engine
JOBS=2 ./scripts/setup_hm.sh
timeout 35m __PHASE3_COMMAND__
REMOTE
)"
if [[ "${PHASE3_MODE:-matrix}" == "search" ]]; then
  phase3_command="python3 experiments/run_phase3_search.py"
else
  phase3_command="python3 experiments/run_phase3_matrix.py --qps ${PHASE3_QPS:-22 27 32 37}"
fi
remote_command="${remote_command/__PHASE3_COMMAND__/${phase3_command}}"
gcloud compute ssh "${INSTANCE_NAME}" --project="${PROJECT_ID}" --zone="${ZONE}" --quiet --command="${remote_command}"
trap - EXIT
printf 'remote Phase 3 matrix complete; run cloud/collect_phase3_matrix.sh\n'
