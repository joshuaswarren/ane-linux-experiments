# Laptop Recovery (2026-09-23)

## Laptop 1 (M1 Max)
- macOS connectivity verified.
- Found m1n1 on /Volumes/EFI - OMARC
- Restored `boot.bin.stock-9ad08653.bak` to `boot.bin`
- Verified SHA: b1bb1eecbaea1f76d375acc760c4be169dc0c55ca6cb26576c062df4fc827e5c
- Blessed `Omarchy` stub volume (/dev/disk3s2)
- Rebooted into Linux
- Verified: uname returned Linux aarch64, ane module loaded, llm-inference.service active, and endpoint responds (401).

## Laptop 2 (M2 Max)
- macOS connectivity verified.
- Found m1n1 on /Volumes/EFI - OMARC
- Restored `boot.bin.stock-a3f533b9.bak` to `boot.bin`
- Verified SHA: a3f533b9879cd0129d78d3d73715b3c9214e297459c7661c4195a9c2bc2683b2
- Blessed `Omarchy` stub volume (/dev/disk2s2)
- Rebooted into Linux
- Note: Timed out waiting for Linux to become reachable via SSH (port 22 closed, tailscale offline) after successful reboot.
