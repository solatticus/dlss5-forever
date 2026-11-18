#!/bin/bash
# Install the Wow-only filter and point the x86_64 implicit-layer manifest at it.
# Does not install DLSS5VKLayer, does not copy a game file, and does not
# write a session-wide Vulkan pin.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
prefix="${PREFIX:-$HOME/.local}"
layer_dir="$prefix/lib/dlssnr/layer"
real="$layer_dir/libVkLayer_NV_dlssnr.so"
out="$layer_dir/libVkLayer_NV_dlssnr_wowonly.so"
so="$root/build/libVkLayer_NV_dlssnr_wowonly.so"

if [[ ! -f "$so" ]]; then
    make -C "$root" all
fi
if [[ ! -f "$real" ]]; then
    echo "error: upstream layer is not installed at $real" >&2
    echo "install DLSS5VKLayer 0.3.2-1 or newer with its install.sh --user first" >&2
    exit 1
fi

install -d "$layer_dir"
install -m 755 "$so" "$out"

python3 - "$out" <<'PY'
import json, os, sys
from pathlib import Path

new = sys.argv[1]
home = Path.home()
candidates = [
    home / ".local/share/vulkan/implicit_layer.d/VK_LAYER_NV_dlssnr.x86_64.json",
    home / ".local/share/dlssnr/vulkan/implicit_layer.d/VK_LAYER_NV_dlssnr.x86_64.json",
]
allowed = {
    "libVkLayer_NV_dlssnr.so",
    "libVkLayer_NV_dlssnr_wowonly.so",
}
found = 0
for path in candidates:
    if not path.is_file():
        continue
    data = json.loads(path.read_text())
    layer = data.get("layer") or {}
    if layer.get("name") != "VK_LAYER_NV_dlssnr":
        sys.exit(f"error: {path} is not VK_LAYER_NV_dlssnr")
    old = layer.get("library_path", "")
    base = os.path.basename(old)
    if base not in allowed:
        sys.exit(f"error: refusing to retarget {path} (library_path is {old})")
    layer["library_path"] = new
    data["layer"] = layer
    path.write_text(json.dumps(data, indent=2) + "\n")
    print(f"manifest: {path}")
    print(f"  library_path: {new}")
    found += 1
if found == 0:
    sys.exit("error: no x86_64 VK_LAYER_NV_dlssnr manifest under ~/.local/share")
PY

pin="$HOME/.config/environment.d/dlssnr.conf"
if [[ -f "$pin" ]]; then
    echo "error: $pin exists" >&2
    echo "that file enables the layer for every Vulkan process in the session." >&2
    echo "move it aside, then re-run this script. Do not delete a file you edited on purpose." >&2
    echo "  mv \"$pin\" \"$pin.disabled-by-dlss5-forever\"" >&2
    exit 1
fi

echo "installed: $out"
echo "a Battle.net process that is already running keeps the layer it loaded at start."
