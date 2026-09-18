#!/usr/bin/env bash
set -euo pipefail

metadata='http://metadata.google.internal/computeMetadata/v1/instance/attributes/max-lifetime-minutes'
minutes="$(curl --fail --silent --show-error -H 'Metadata-Flavor: Google' "${metadata}")"
if [[ ! "${minutes}" =~ ^[0-9]+$ ]] || (( minutes < 1 || minutes > 360 )); then
  minutes=55
fi
systemd-run --unit=chia-rdo-hard-stop --on-active="${minutes}m" /usr/sbin/poweroff
