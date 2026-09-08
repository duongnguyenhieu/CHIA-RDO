#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HM_DIR="${HM_DIR:-${ROOT}/software/third_party/HM}"
HM_REPOSITORY="https://vcgit.hhi.fraunhofer.de/jvet/HM.git"
HM_TAG="HM-16.20"
HM_REVISION="22178e370178133438c0339f57b3b3a29f112909"
PATCH="${ROOT}/software/patches/hm-16.20-chia-rdo.patch"

if [[ ! -d "${HM_DIR}/.git" ]]; then
  mkdir -p "$(dirname "${HM_DIR}")"
  git clone --branch "${HM_TAG}" --depth 1 "${HM_REPOSITORY}" "${HM_DIR}"
fi

actual_revision="$(git -C "${HM_DIR}" rev-parse HEAD)"
if [[ "${actual_revision}" != "${HM_REVISION}" ]]; then
  printf 'HM revision mismatch: expected %s, got %s\n' "${HM_REVISION}" "${actual_revision}" >&2
  exit 2
fi

if git -C "${HM_DIR}" apply --reverse --check "${PATCH}" >/dev/null 2>&1; then
  printf 'CHIA-RDO HM patch already applied\n'
else
  git -C "${HM_DIR}" apply --check "${PATCH}"
  git -C "${HM_DIR}" apply "${PATCH}"
fi

make -C "${HM_DIR}/build/linux" -j"${JOBS:-8}" release \
  RELEASE_CPPFLAGS="-O3 -Wuninitialized -Wno-error"

test -x "${HM_DIR}/bin/TAppEncoderStatic"
test -x "${HM_DIR}/bin/TAppDecoderStatic"
printf 'HM %s ready at %s\n' "${HM_TAG}" "${HM_DIR}"
