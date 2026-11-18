#!/usr/bin/env python3
"""A process whose command line is not Wow.exe must refuse the layer.

vkNegotiateLoaderLayerInterfaceVersion returns -3
(VK_ERROR_INITIALIZATION_FAILED) before the real layer is opened.
"""

import ctypes
import sys
from pathlib import Path

so = Path(sys.argv[1] if len(sys.argv) > 1 else "build/libVkLayer_NV_dlssnr_wowonly.so")
if not so.is_file():
    sys.exit(f"missing {so}; run make first")

lib = ctypes.CDLL(str(so.resolve()))
fn = lib.vkNegotiateLoaderLayerInterfaceVersion
fn.argtypes = [ctypes.c_void_p]
fn.restype = ctypes.c_int
rc = fn(None)
if rc != -3:
    sys.exit(f"expected -3 from a non-Wow process, got {rc}")
print(f"ok: {so} refused a non-Wow process ({rc})")
