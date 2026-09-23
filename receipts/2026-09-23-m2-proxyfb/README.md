# M2 proxy-with-fallback image (2026-09-23)

v1.6.1 + one-line config.h patch: EARLY_PROXY_TIMEOUT 5 -> 60.
Built in dg-alarm-py314:sep23 with M1N1_VERSION_TAG=v1.6.1.

- m1n1 part: 2ac417e7b34d1654f7c4bd7daf49b67ad9d5eca238f56b4c5341d62cb5d1110e
- stock m1n1 part: 9ad08653 (diff is the version tag path plus the timeout path only)
- stock boot.bin: a3f533b9 (first 1114112 bytes are 9ad08653, then STACKBOOT payloads)

Behavior: 60 s proxy wait with dots, then normal payload boot on timeout.
