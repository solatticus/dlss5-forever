#!/bin/bash
# Pattern for the existing Battle.net launcher. Copy these exports and the
# trap into the script the desktop icon already runs. Do not point this at
# Wow.exe. Play has to come from Battle.net so the game receives a launch ticket.
#
#   UMU_CONFIG=/path/to/battlenet.toml ./scripts/battlenet-launch.sh
#
# The toml keeps the Proton that already runs the game. The helper uses a
# different runner, set in ~/.config/dlssnr/config.ini. See README.md.
set -u

if [[ "${1:-}" == *Wow.exe* ]] || [[ "${UMU_CONFIG:-}" == *Wow.exe* ]]; then
    echo "refusing to launch Wow.exe directly" >&2
    exit 1
fi

: "${UMU_CONFIG:?set UMU_CONFIG to the toml that already launches Battle.net}"

export DISPLAY="${DISPLAY:-:0}"
export VKLayer_DLSS5=1
export VKLAYER_DLSS5=1
export DLSSNR_TIME=1
export DLSSNR_LOG="${XDG_STATE_HOME:-$HOME/.local/state}/dlssnr/layer.log"

cleanup() {
    dlssnr-helper stop || true
}
trap cleanup EXIT

dlssnr-helper start

umu="${UMU_RUN:-$HOME/.local/bin/umu-run}"
exec "$umu" --config "$UMU_CONFIG"
