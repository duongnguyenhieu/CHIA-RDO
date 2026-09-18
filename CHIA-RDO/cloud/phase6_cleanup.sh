#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/gcp_common.sh"
require_command gcloud

mapfile -t instances < <(gcloud compute instances list --project="${PROJECT_ID}" \
  --filter='labels.phase=phase6' --format='value(name,zone.basename())')
for entry in "${instances[@]}"; do
  read -r name zone <<<"${entry}"
  gcloud compute instances delete "${name}" --project="${PROJECT_ID}" --zone="${zone}" --delete-disks=all --quiet
done

remaining="$(gcloud compute instances list --project="${PROJECT_ID}" --filter='labels.phase=phase6' --format='value(name)')"
[[ -z "${remaining}" ]] || { printf 'Phase-6 instances remain: %s\n' "${remaining}" >&2; exit 3; }
printf 'Phase-6 cleanup verified: no labeled worker instances remain.\n'
