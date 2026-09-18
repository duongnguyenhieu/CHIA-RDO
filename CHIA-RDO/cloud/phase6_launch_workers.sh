#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! "${ROOT}/cloud/phase6_preflight.sh"; then
  printf 'Phase-6 launch blocked by fail-closed billing guard.\n' >&2
  exit 3
fi

printf 'Preflight unexpectedly passed, but worker creation is intentionally not automated until a verified campaign manifest is approved.\n' >&2
exit 4
