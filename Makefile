# Build the Wow-only filter. The upstream layer is installed separately.
PREFIX ?= $(HOME)/.local
CC ?= gcc

BUILD := build
SO := $(BUILD)/libVkLayer_NV_dlssnr_wowonly.so
SRC := wowonly/dlssnr-wowonly.c

.PHONY: all install check clean

all: $(SO)

$(SO): $(SRC)
	mkdir -p $(BUILD)
	$(CC) -shared -fPIC -O2 -fvisibility=hidden -o $@ $< -ldl

install: $(SO)
	./scripts/install.sh

check: $(SO)
	python3 scripts/check-wowonly.py $(SO)

clean:
	rm -rf $(BUILD)
