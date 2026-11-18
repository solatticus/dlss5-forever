/* Load the neural-rendering layer only inside Wow.exe.
 *
 * Battle.net presents its own swapchain. One helper serves every process
 * that loaded the layer, and a second size rebuilds the model on the
 * game's present thread. This filter is what the Vulkan loader opens.
 * It forwards the real layer only when /proc/self/cmdline contains Wow.exe.
 *
 * DLSSNR_REAL_LAYER overrides the path. Otherwise the upstream layer is
 * ~/.local/lib/dlssnr/layer/libVkLayer_NV_dlssnr.so.
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int want_layer(void) {
    static int decided = -1;
    if (decided >= 0) return decided;
    decided = 0;
    FILE *f = fopen("/proc/self/cmdline", "rb");
    if (!f) return 0;
    char buf[8192];
    size_t n = fread(buf, 1, sizeof buf - 1, f);
    fclose(f);
    for (size_t i = 0; i < n; i++) {
        if (buf[i] == '\0') buf[i] = ' ';
    }
    buf[n] = '\0';
    decided = strstr(buf, "Wow.exe") != NULL;
    return decided;
}

static const char *real_layer_path(void) {
    const char *env = getenv("DLSSNR_REAL_LAYER");
    if (env && env[0]) return env;
    static char buf[4096];
    const char *home = getenv("HOME");
    if (!home || !home[0]) return NULL;
    int n = snprintf(buf, sizeof buf,
                     "%s/.local/lib/dlssnr/layer/libVkLayer_NV_dlssnr.so",
                     home);
    if (n < 0 || (size_t)n >= sizeof buf) return NULL;
    return buf;
}

static void *real_layer(void) {
    static void *handle;
    static int opened;
    if (opened) return handle;
    opened = 1;
    if (!want_layer()) return NULL;
    const char *path = real_layer_path();
    if (!path) return NULL;
    handle = dlopen(path, RTLD_NOW | RTLD_LOCAL);
    return handle;
}

__attribute__((visibility("default")))
int vkNegotiateLoaderLayerInterfaceVersion(void *version) {
    if (!want_layer()) return -3; /* VK_ERROR_INITIALIZATION_FAILED */
    void *handle = real_layer();
    if (!handle) return -3;
    int (*fn)(void *) = dlsym(handle, "vkNegotiateLoaderLayerInterfaceVersion");
    if (!fn) return -3;
    return fn(version);
}

__attribute__((visibility("default")))
void *vkGetInstanceProcAddr(void *instance, const char *name) {
    void *handle = real_layer();
    if (!handle) return NULL;
    void *(*fn)(void *, const char *) = dlsym(handle, "vkGetInstanceProcAddr");
    if (!fn) return NULL;
    return fn(instance, name);
}

__attribute__((visibility("default")))
void *vkGetDeviceProcAddr(void *device, const char *name) {
    void *handle = real_layer();
    if (!handle) return NULL;
    void *(*fn)(void *, const char *) = dlsym(handle, "vkGetDeviceProcAddr");
    if (!fn) return NULL;
    return fn(device, name);
}
