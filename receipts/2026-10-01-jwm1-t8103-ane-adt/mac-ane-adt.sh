#!/bin/bash
# Read-only ANE/ASC/reserved-memory ADT + IOService capture on jwm1 macOS (T8103).
set -u
O=/tmp/h1/adt-out
mkdir -p "$O"
uname -a > "$O/uname.txt"
sw_vers > "$O/sw_vers.txt" 2>&1
# full device tree as XML plist (large, filtered offline) and as text
ioreg -a -p IODeviceTree -l > "$O/iodevicetree.plist" 2> "$O/iodevicetree.err"
ioreg -p IODeviceTree -l -w0 > "$O/iodevicetree.txt" 2>> "$O/iodevicetree.err"
# ANE service plane
ioreg -a -c AppleH11ANEInterface -l > "$O/ane-interface.plist" 2> "$O/ane-interface.err"
ioreg -c AppleH11ANEInterface -l -w0 > "$O/ane-interface.txt" 2>> "$O/ane-interface.err"
ioreg -l -w0 -p IOService | grep -i -E "ane|neural" > "$O/ioservice-ane-grep.txt" 2>&1
# iop / asc / mailbox / reserved memory nodes
ioreg -p IODeviceTree -l -w0 | grep -i -E "iop-|-asc|mailbox|reserved|carveout|firmware" > "$O/iop-asc-grep.txt" 2>&1
ls -la /usr/standalone/firmware /System/Library/Frameworks/Foundation.framework 2>/dev/null | head -5 > "$O/fw-ls.txt"
find /usr/standalone/firmware -maxdepth 2 -iname "*ane*" 2>/dev/null > "$O/fw-ane-find.txt"
find /System/Library/Extensions/AppleH11ANEInterface.kext -maxdepth 3 2>/dev/null > "$O/ane-kext-find.txt"
sysctl -a 2>/dev/null | grep -i -E "ane|neural" > "$O/sysctl-ane.txt"
ls -la "$O" > "$O/ls.txt"
echo CAPTURE-DONE
