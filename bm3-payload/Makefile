CROSS ?= aarch64-linux-gnu-
CC := $(CROSS)gcc
CFLAGS := -ffreestanding -nostdlib -Os -fno-stack-protector -fno-pic -fno-pie \
          -mgeneral-regs-only -Wall -Wextra

payload.bin: payload.elf
	$(CROSS)objcopy -O binary $< $@

payload.elf: entry.o main.o
	$(CC) $(CFLAGS) -static -Wl,-Ttext=0,--build-id=none -o $@ entry.o main.o

%.o: %.c
	$(CC) $(CFLAGS) -c -o $@ $<
entry.o: entry.S
	$(CC) $(CFLAGS) -c -o $@ $<

clean:
	rm -f entry.o main.o payload.elf payload.bin
.PHONY: clean
