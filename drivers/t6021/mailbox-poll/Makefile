ifneq ($(KERNELRELEASE),)
obj-m := ane_mailbox_poll.o
ane_mailbox_poll-objs := mailbox_poll.o
ccflags-y += -I$(src)
else
KERNELDIR ?= /lib/modules/$(shell uname -r)/build
PWD := $(shell pwd)

default: modules

modules:
	$(MAKE) -C $(KERNELDIR) M=$(PWD) modules

clean:
	$(MAKE) -C $(KERNELDIR) M=$(PWD) clean

.PHONY: default modules clean
endif
