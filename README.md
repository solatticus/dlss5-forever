# dlss5-forever

Glue that puts [DLSS5VKLayer](https://github.com/bmitch87/DLSS5VKLayer) on a Battle.net World of Warcraft client without letting the Battle.net window share the neural model. This repository is the filter, a settings window, and the launcher wiring. It is not a fork of the layer, and it contains no NVIDIA library.

`DLSS5VKLayer/` is the layer, helper, `dlssnr-shmctl`, GUI, and installer source, imported from upstream tag `0.3.2-1` (commit `c77b64c`). Edit it in this repo. It stays under the GNU AGPL v3 in `DLSS5VKLayer/LICENSE`. The MIT license here does not cover it. A clone of this repo includes that source. No submodule step.

Tested once: RTX 5090, driver 615.71.10, DLSS5VKLayer 0.3.2-1, helper on Proton Experimental, WoW Forever (D3D12 through vkd3d-proton) on GE-Proton10-34, SDR 3440×1440. Treat the version notes as that run, not as a promise about the next driver.

## For an agent

Do these in order. Stop at the first failure and report the command and its output. Do not improvise a second Battle.net, a direct `Wow.exe` launch, or a file inside the game directory.

1. Confirm the layer is installed for the user (`~/.local/bin/dlssnr-helper`, `~/.local/lib/dlssnr/layer/libVkLayer_NV_dlssnr.so`). If it is missing, build it from `DLSS5VKLayer/` in this repo and install the **public** tarball. Do not install the personal package. See [Install the layer](#install-the-layer).
2. If `~/.config/environment.d/dlssnr.conf` exists, move it aside. Upstream's installer writes it, and it turns the layer on for every Vulkan process. This setup enables the layer only on the Battle.net launcher.
3. Put `nvngx_dlssnr.dll` in `~/.local/share/dlssnr/binaries/` with `dlssnr-helper import-binaries`. The file stays on that machine. Do not copy it into this repo, a commit, or the game directory. `nvngx.dll` and `nvapi64.dll` stay out of the repo too.
4. Point the **helper** at Proton Experimental. Leave the **game's** Proton alone. See [Helper runner](#helper-runner).
5. From this repo: `make check && make install`.
6. Add the environment and the exit trap to the script that already launches Battle.net. See [Battle.net launcher](#battlenet-launcher).
7. Start Battle.net from that script. In the client, press Play. Do not start `Wow.exe` yourself.
8. Run the checks in [Confirm](#confirm).

## What is here

| Path | Role |
|---|---|
| `DLSS5VKLayer/` | Layer, helper, shmctl, GUI, and installer source. Imported from tag `0.3.2-1`. GNU AGPL v3. This repo's Makefile does not build it. |
| `wowonly/dlssnr-wowonly.c` | Vulkan loader entry. Forwards the real layer only when `/proc/self/cmdline` contains `Wow.exe`. Any other process gets `-3` and the game or launcher presents its own frames. |
| `scripts/install.sh` | Builds that filter, installs it beside the upstream `.so`, and retargets the x86_64 implicit-layer manifest. |
| `scripts/dlssnr-panel.py` | Settings window. It only calls `dlssnr-shmctl`. It does not stop the helper. |
| `scripts/battlenet-launch.sh` | The exports and exit trap to put on the existing launcher. |
| `scripts/toggle-dlssnr.sh` | Flips `enabled` while the helper is running. |
| `scripts/check-wowonly.py` | A non-Wow process must get `-3` from the filter. |

`Wow.exe` is the retail, classic, and Forever executable name. A game whose process is not named `Wow.exe` does not match, and the filter will not load the layer for it. Battle.net's own process does not match, which is the point.

## Install the layer

The source to build is `DLSS5VKLayer/` in this repo. Dependencies and the build are in `DLSS5VKLayer/README.md` under "Building From Source". From that directory:

```bash
tools/meson-build.sh
./packaging/make-dist.sh tar
tar -xzf dist/dlssnr-[0-9]*-linux-x86_64.tar.gz
cd dlssnr-*-linux-x86_64
./install.sh --user
```

Use the `dlssnr-<version>` tarball. Do not install `dlssnr-personal-*`. That variant bundles NVIDIA DLLs, and this repo does not ship them.

That install can create `~/.config/environment.d/dlssnr.conf`. Move it aside before the next login:

```bash
mv ~/.config/environment.d/dlssnr.conf \
   ~/.config/environment.d/dlssnr.conf.disabled-by-dlss5-forever
```

Do not mix a 0.2.x helper with a 0.3.x layer. The shared-memory header versions differ.

The model DLL is not in the public tarball. Import one the machine is allowed to have:

```bash
dlssnr-helper import-binaries /path/to/directory-containing-nvngx_dlssnr.dll
```

On the tested machine, a 310.8 `nvngx_dlssnr.dll` created feature 18. The 310.9.16 DLL from RTX Remix 1.6.1 returned `0xbad00001` (feature not supported) in 0 ms under the same driver and helper. Do not substitute a DLL whose signature does not match its contents.

## Compile and install the filter

Requires `gcc` and Python 3.

```bash
make check
make install
```

`make check` loads `build/libVkLayer_NV_dlssnr_wowonly.so` into the current Python process and expects `vkNegotiateLoaderLayerInterfaceVersion` to return `-3`.

`make install` copies the filter to `~/.local/lib/dlssnr/layer/libVkLayer_NV_dlssnr_wowonly.so` and sets `library_path` in:

- `~/.local/share/vulkan/implicit_layer.d/VK_LAYER_NV_dlssnr.x86_64.json`
- `~/.local/share/dlssnr/vulkan/implicit_layer.d/VK_LAYER_NV_dlssnr.x86_64.json`, if that copy exists

It refuses a manifest that is not `VK_LAYER_NV_dlssnr`, or whose `library_path` is not already the upstream layer or this filter. It does not touch the i686 manifest. `DLSSNR_REAL_LAYER` overrides the `.so` the filter opens.

Steam's pressure-vessel copies implicit-layer manifests when the container starts. A Battle.net process that is already running keeps the layer it mapped. Quit it, then launch again with the script below. Do not start a second Battle.net against the same prefix.

## Helper runner

The helper is a Windows process. It is not the Proton that runs the game.

`dlssnr-helper init` scores GE-Proton above Proton Experimental and will pick GE if both are installed. GE-Proton 10 and 11 are wine-staging, and the 0.3.2 helper stack-overflows during load under that staging. System Wine starts the helper, then feature creation fails because that path loads a vendored `nvapi64.dll`.

After init, set the runner to the Proton Experimental **file** named `proton`, not the directory:

```ini
runner_type=proton
runner_path=/path/to/steamapps/common/Proton - Experimental/proton
```

The file is `~/.config/dlssnr/config.ini`. A directory path fails `dlssnr-helper start` with "Is a directory". The helper's own prefix is `~/.local/share/dlssnr/prefix`. Do not point it at the Battle.net prefix.

Leave the game's umu toml, its Proton, and its prefix as they are. On the tested machine the game stayed on GE-Proton10-34 while the helper used Proton Experimental.

`dlssnr-helper start` exports `PROTON_ENABLE_NVAPI=1` and `DLSSNR_SKIP_NVAPI=1` on the proton runner. Those two are what let feature 18 come back on this GPU. Do not unset them.

## Battle.net launcher

The desktop entry that starts Battle.net has to export the layer token before umu, start the helper, and stop the helper when that process exits. Wine copies the Linux environment into the Windows process at start. A token added after Battle.net is already running does not reach Play.

Add this to the existing launcher. Keep its umu config and its log redirection.

```bash
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
```

`scripts/battlenet-launch.sh` is the same pattern as a standalone script. It requires `UMU_CONFIG` and refuses a command line that contains `Wow.exe`.

```bash
UMU_CONFIG=/path/to/the-existing-battlenet.toml ./scripts/battlenet-launch.sh
```

Play from the Battle.net window. The client hands the game a launch ticket. Starting `Wow.exe` from outside the client skips that ticket and the game asks for a login even when the launcher is signed in.

The token is on the whole client, so any game that client launches inherits it. The filter then loads the real layer only for `Wow.exe`. The next start is the first start that uses the filter. Until then, a visible Battle.net window and the game share one helper, and every launcher frame rebuilds the game-sized model. That rebuild is a hitch of a few hundred milliseconds on the present thread.

Do not set `DLSSNR_TOGGLE_KEY`. A bound hotkey reads `/dev/input`, and older builds stall the present thread about once a second when a key is bound. Leave `togglekey` at 0. Use `scripts/toggle-dlssnr.sh` or the panel.

## Settings

```bash
python3 scripts/dlssnr-panel.py
```

The window reads and writes `/tmp/dlssnr-$UID/shm.bin`. Style is 0 Default, 1 Natural, 2 Cinematic. Passes are a pair of buttons from 1 to 5, because a spinbox in a focused window treats the mouse wheel as clicks and climbs the count. Detail and Colour apply only when "Model picture" is unchecked (`bypass=0`). Style, intensity, local tone, local structure, and passes rebuild the model. Each extra pass is another full run.

Closing the panel leaves the helper running. Closing the upstream `dlssnr-gui` asks the helper to stop. Do not open that GUI against a live game unless that is what you want.

Quitting the game runs the launcher's exit trap, which stops the helper. The shared-memory file remains, and the next launch of that same script resumes the sliders. `/tmp` is tmpfs here, so a reboot clears the file and the next launch comes up as Default, one pass, raw model picture.

`dlssnr-shmctl /tmp/dlssnr-$UID/shm.bin set <name> <value>` is the same write the panel makes. `dlssnr-shmctl … reset` restores defaults. Do not send `quit` unless you mean to stop the pass.

## Confirm

Helper:

```bash
dlssnr-helper status
```

The first line is `helper running`.

Filter, from any shell that is not Wow:

```bash
make check
```

After Play, the layer log named by `DLSSNR_LOG` should show `VULKAN_CreateFeature(18)` at the game's resolution and `-> 0x1`. A following line for the Battle.net window size (1000×640 on the tested client) means this Battle.net process loaded the real layer instead of the filter. Quit the client and launch it again so pressure-vessel copies the updated manifest.

A present-thread time around 10–15 ms is one full-frame pass at 3440×1440 on the tested GPU. Four passes cost more. The frame rate cap inside the game is still the display cap. A heavier pass can miss it.

Settings survive the quit:

```bash
dlssnr-shmctl /tmp/dlssnr-$UID/shm.bin settings
```

`quit=1` after the launcher exits is expected. The next `dlssnr-helper start` clears it and keeps the other values when the header is already initialised.

## Licenses

Files written in this repo are MIT. See `LICENSE`.

`DLSS5VKLayer/` is GNU AGPL v3, imported from tag `0.3.2-1` (`c77b64c`). Changes in that directory stay AGPL, and the source has to ship with any copy you give out. Do not move those files into the MIT part of the tree or delete `DLSS5VKLayer/LICENSE`. `third_party/dxvk/2.7.1/x64/vulkan-1.dll` is the DXVK loader that upstream already tracked. It is not NVIDIA's model.

## Do not

- Commit or publish `nvngx_dlssnr.dll`, `nvngx.dll`, `nvapi64.dll`, the helper prefix, the Battle.net prefix, or logs.
- Copy a DLL into the game directory. The layer stays outside it.
- Launch `Wow.exe` except by pressing Play in Battle.net.
- Change the Proton in the game's umu toml to Proton Experimental, or point the helper at GE-Proton or system Wine.
- Re-enable a `VK_LAYER_NV_dlssnr*.json.disabled*` left behind by an older install.
- Open a second Battle.net while this client's wineserver is still up. They share a prefix.
- Bind `DLSSNR_TOGGLE_KEY`.
