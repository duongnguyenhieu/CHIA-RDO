#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HM_DIR="${HM_DIR:-${ROOT}/software/third_party/HM}"
HM_REPOSITORY="https://vcgit.hhi.fraunhofer.de/jvet/HM.git"
HM_TAG="HM-16.20"
HM_REVISION="22178e370178133438c0339f57b3b3a29f112909"
PATCH="${ROOT}/software/patches/hm-16.20-chia-rdo.patch"
PHASE2_PATCH="${ROOT}/software/patches/hm-16.20-phase2-k-policy.patch"
HW_POLICY_PATCH="${ROOT}/software/patches/hm-16.20-phase2-hardware-policy.patch"
PHASE3_PATCH="${ROOT}/software/patches/hm-16.20-phase3-algorithms.patch"
PHASE5_PATCH="${ROOT}/software/patches/hm-16.20-phase5-rdo-vectors.patch"
FULL_RDO_PATCH="${ROOT}/software/patches/hm-16.20-phase5-full-rdo-mvp.patch"
FULL_RDO_PE_PATCH="${ROOT}/software/patches/hm-16.20-phase5.2-full-rdo-pe.patch"
PWAY_FULL_RDO_PATCH="${ROOT}/software/patches/hm-16.20-phase5.3-pway-full-rdo.patch"

if [[ ! -d "${HM_DIR}/.git" ]]; then
  mkdir -p "$(dirname "${HM_DIR}")"
  git clone --branch "${HM_TAG}" --depth 1 "${HM_REPOSITORY}" "${HM_DIR}"
fi

actual_revision="$(git -C "${HM_DIR}" rev-parse HEAD)"
if [[ "${actual_revision}" != "${HM_REVISION}" ]]; then
  printf 'HM revision mismatch: expected %s, got %s\n' "${HM_REVISION}" "${actual_revision}" >&2
  exit 2
fi

if git -C "${HM_DIR}" apply --reverse --check "${PHASE3_PATCH}" >/dev/null 2>&1; then
  printf 'CHIA-RDO Phase 1, Phase 2, and Phase 3 algorithm patches already applied\n'
elif git -C "${HM_DIR}" apply --reverse --check "${HW_POLICY_PATCH}" >/dev/null 2>&1; then
  printf 'CHIA-RDO Phase 1 and Phase 2 hardware-policy patches already applied\n'
else
  if git -C "${HM_DIR}" apply --reverse --check "${PHASE2_PATCH}" >/dev/null 2>&1; then
    printf 'CHIA-RDO Phase 1 and K-policy patches already applied\n'
  else
    if git -C "${HM_DIR}" apply --reverse --check "${PATCH}" >/dev/null 2>&1; then
      printf 'CHIA-RDO Phase 1 patch already applied\n'
    else
      git -C "${HM_DIR}" apply --check "${PATCH}"
      git -C "${HM_DIR}" apply "${PATCH}"
    fi
    git -C "${HM_DIR}" apply --check "${PHASE2_PATCH}"
    git -C "${HM_DIR}" apply "${PHASE2_PATCH}"
  fi
  git -C "${HM_DIR}" apply --check "${HW_POLICY_PATCH}"
  git -C "${HM_DIR}" apply "${HW_POLICY_PATCH}"
fi
if ! git -C "${HM_DIR}" apply --reverse --check "${PHASE3_PATCH}" >/dev/null 2>&1; then
  git -C "${HM_DIR}" apply --check "${PHASE3_PATCH}"
  git -C "${HM_DIR}" apply "${PHASE3_PATCH}"
fi
if ! git -C "${HM_DIR}" apply --reverse --check "${PHASE5_PATCH}" >/dev/null 2>&1; then
  git -C "${HM_DIR}" apply --check "${PHASE5_PATCH}"
  git -C "${HM_DIR}" apply "${PHASE5_PATCH}"
fi
if git -C "${HM_DIR}" apply --reverse --check "${PWAY_FULL_RDO_PATCH}" >/dev/null 2>&1; then
  printf 'CHIA-RDO Phase 5.3 P-way Full-RDO patch already applied\n'
else
  if ! git -C "${HM_DIR}" apply --reverse --check "${FULL_RDO_PE_PATCH}" >/dev/null 2>&1; then
    if ! git -C "${HM_DIR}" apply --reverse --check "${FULL_RDO_PATCH}" >/dev/null 2>&1; then
      git -C "${HM_DIR}" apply --check "${FULL_RDO_PATCH}"
      git -C "${HM_DIR}" apply "${FULL_RDO_PATCH}"
    fi
    git -C "${HM_DIR}" apply --check "${FULL_RDO_PE_PATCH}"
    git -C "${HM_DIR}" apply "${FULL_RDO_PE_PATCH}"
  fi
  git -C "${HM_DIR}" apply --check "${PWAY_FULL_RDO_PATCH}"
  git -C "${HM_DIR}" apply "${PWAY_FULL_RDO_PATCH}"
fi

make -C "${HM_DIR}/build/linux" -j"${JOBS:-8}" release \
  RELEASE_CPPFLAGS="-O3 -Wuninitialized -Wno-error"

test -x "${HM_DIR}/bin/TAppEncoderStatic"
test -x "${HM_DIR}/bin/TAppDecoderStatic"
printf 'HM %s ready at %s\n' "${HM_TAG}" "${HM_DIR}"
