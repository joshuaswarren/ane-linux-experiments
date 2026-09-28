ifneq ($(KERNELRELEASE),)
	obj-m := ane_t6021.o ane_t6021_rtclient.o
	ane_t6021-objs := ane_t6021_drv.o ane_t6021_rtkit.o ane_t6021_fwload.o ane_t6021_boot.o
	# The rtclient links the shared boot/fwload contract units so the
	# fenced fw_start path runs the exact sequence core the legacy
	# module and the host trace test exercise (kbuild compiles the
	# shared objects once and links them into both modules). The
	# probe file is _main.c so no object shares the module name
	# (composite/single-object collision).
	ane_t6021_rtclient-objs := ane_t6021_rtclient_main.o ane_t6021_fwload.o ane_t6021_boot.o
	ccflags-y += -DANE_T6021_MODULE_VERSION='"$(shell git -C $(src) describe --always --dirty 2>/dev/null || echo unknown)"'
else
	KERNELDIR ?= /lib/modules/$(shell uname -r)/build
 	PWD := $(shell pwd)

# Same out-of-tree contract as the H13 ane module: plain module build,
# no installation, no modprobe. Cross build for the jw14m2 kernel tree:
#   make KERNELDIR=.../omarchy-linux ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu-
default: modules

modules:
	$(MAKE) -C $(KERNELDIR) M=$(PWD) modules

clean:
	$(MAKE) -C $(KERNELDIR) M=$(PWD) clean
	rm -f test/test_anet6021_fwload_options_ok

# Executable predicate test (host-side, x86_64). Mirrors the kernel-side
# ane_t6021_fwload_options_ok / ane_t6021_diag_options_ok inputs and runs
# the boundary matrix (16 MiB cap, 4 KiB alignment, reserved-alias
# coupling, 24 MiB pre-alloc rejection). Independent of the kernel tree.
test/test_anet6021_fwload_options_ok: ../../test/test_anet6021_fwload_options_ok.c
	$(CC) -O2 -Wall -Wextra -o $@ $<

.PHONY: default modules check test clean
check: test/test_anet6021_fwload_options_ok
	./$<

endif
