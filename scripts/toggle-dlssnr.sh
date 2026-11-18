#!/bin/bash
# Flip the neural pass on or off. The helper is started by the Battle.net launcher.
SHM="${DLSSNR_SHM:-/tmp/dlssnr-${UID}/shm.bin}"

status_out="$(dlssnr-helper status 2>/dev/null || true)"
case "$status_out" in
    "helper running"*) ;;
    *)
        echo "The helper isn't running. Open Battle.net from the launcher that starts it." >&2
        exit 1
        ;;
esac

if ! dlssnr-shmctl "$SHM" toggle enabled >/dev/null; then
    echo "The toggle failed." >&2
    exit 1
fi

state="$(dlssnr-shmctl "$SHM" settings | awk -F= '/^enabled=/{print $2; exit}')"
if [ "$state" = "1" ]; then
    echo "DLSS 5 on"
else
    echo "DLSS 5 off"
fi
