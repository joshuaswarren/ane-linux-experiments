# Fleet SSH Conflict-Marker Sweep — 2026-09-17

Scope: unresolved git conflict markers and parse failures in SSH config material
across the fleet, including chezmoi source repos. Sweep script: `sh -s` per host,
scanning `~/.ssh/{config,known_hosts,authorized_keys}`, `~/.ssh/config.d/*`,
`/etc/ssh/{ssh,sshd}_config` + `.d/*`, and the chezmoi source (markers), plus
`ssh -G <probe>` parse check.

## Root cause and fix

The 2026-09-12 dual-boot restructure of the 16" M1 Max aliases left a stash
merge unresolved in jw14m2's `~/.ssh/config`, breaking all ssh parsing on that
host. The conflict had already been resolved in the dotfiles source of truth
(`joshuaswarren/dotfiles` commit `a6dcb11`, "ssh: resolve stash conflict on
16m1mbp dual-boot aliases") — jw14m2's working copy had drifted from it.

**Resolution applied (jw14m2):** the owner's upstream resolution — `Host
jw16mbp1-linux 16m1mbp jw16m2 16m1mbp-linux` → `192.168.10.244:22` (live Linux,
`HostKeyAlias 16m1mbp-omarchy`), plus `jw16mbp1-linux-ts` → `100.90.66.103`, and
`16m1mbp-macos` → `100.117.156.89:2222` (macOS slice). The stashed side's
`Host 16m1mbp jw16m2 → 100.117.156.89:2222` was dropped as superseded by the
owner's own dated 2026-09-12 comment in the upstream side — not a coin flip;
the union in `a6dcb11` also keeps the stashed side's `16m1mbp-linux` alias and
`HostKeyAlias`.

## Host-by-host table

| Host | Reachable | Files scanned | Markers | Parse | Action | Backup | Validation |
|---|---|---|---|---|---|---|---|
| jw14m2.rhino-beaver.ts.net | yes | ~/.ssh/config, known_hosts, auth_keys, /etc/ssh/* | **YES — config lines 443/453/457, 463/483/487** | FAIL (markers) | resolved → upstream `a6dcb11`, chezmoi apply --force | `~/.ssh/config.bak.20260917113038` (sha256 1a553033…) | ssh -G ok; `git ls-remote git@github.com:joshuaswarren/mlx-omarchy.git` → `2da5e05…` via ssh |
| this workstation (omp-studio-local) | n/a | ~/.ssh/config, known_hosts, auth_keys, /etc/ssh/* | none (config stale, see below) | ok | aligned 16m1mbp blocks to `a6dcb11` content | `~/.ssh/config.bak.20260917114107` (sha256 b3a2dd39…) | `ssh 16m1mbp hostname` → jw16mbp1-linux (was timing out on dead macOS IP); 16m1mbp-macos times out as documented |
| macstudio | yes | config, known_hosts, auth_keys, /etc/ssh/* + d | none | ok | none | — | — |
| jarvis | yes | config, known_hosts, auth_keys, /etc/ssh/* + d | none | ok | none | — | — |
| jarvis-ml | yes | config, known_hosts, auth_keys, /etc/ssh/* + d | none | ok | none | — | — |
| mesa-xbuild | yes | known_hosts, auth_keys, /etc/ssh/* (no user config) | none | ok | none | — | — |
| forgejo | **partial** — sshd runs a forced git command ("Forgejo: Too few arguments"); no shell, sweep script cannot execute | n/a | n/a | n/a | none | — | — |
| pbs | yes (root) | root ssh files, /etc/ssh/* + d | none | ok | none | — | — |
| ha (homeassistant) | yes (root) | root ssh files, /etc/ssh/* + d | none | ok | none | — | — |
| codex-a/b/c | yes | config, known_hosts, auth_keys, /etc/ssh/* + d | none; chezmoi source clean | ok | none | — | — |
| claude-a/b | yes | config, known_hosts, auth_keys, /etc/ssh/* + d | none; chezmoi source clean | ok | none | — | — |
| omp-a, omp-home | yes | config, known_hosts, auth_keys, /etc/ssh/* + d | none; chezmoi source clean | ok | none | — | — |
| claude-code-lxc | yes | known_hosts, auth_keys, /etc/ssh/* + d | none | ok | none | — | — |
| remnic-zai | yes | config, known_hosts, auth_keys, /etc/ssh/* + d | none; chezmoi source clean | ok | none | — | — |
| root@proxmox, proxmox2–5, proxmoxz1 | yes (all 6) | root ~/.ssh/config, known_hosts, auth_keys, /etc/ssh/* + d | none | ok (all) | none | — | — |
| jw16mbp1-linux (=16m1mbp) | yes | known_hosts, auth_keys, /etc/ssh/* + d (no user config) | none | ok | none | — | — |

## Chezmoi source status

- **jw14m2** `~/.local/share/chezmoi` (`git@github.com:joshuaswarren/dotfiles.git`):
  template `private_dot_ssh/private_config.tmpl` had the same markers; resolved
  locally (commit `d90e04f`), then discovered upstream resolution `a6dcb11`
  already on `origin/main`, rebased (duplicate commit dropped as empty), local
  main == `a6dcb11`, push: "Everything up-to-date". `chezmoi diff` clean (0
  lines). Backup: `~/.local/share/chezmoi.bak-path` → file backup at
  `~/.local/share/chezmoi/../chezmoi-private_config.tmpl.bak.20260917113109`
  (sha256 18460d14…).
  **Note:** commit signing via 1Password is BROKEN on jw14m2 ("1Password:
  failed to fill whole buffer", fatal: failed to write commit object). The
  interim commit was made with `commit.gpgsign=false` then dropped in rebase;
  `commit.gpgsign=true` restored after. Owner should fix the 1Password ssh
  agent there.
- **This workstation**: source at `a6dcb11`, clean. `~/.ssh/config` here is
  **not chezmoi-managed** — the repaired blocks were hand-aligned to `a6dcb11`
  content; consider adopting the template to stop drift.
- **codex-a/b/c, claude-a/b, omp-a, omp-home, remnic-zai, macstudio,
  jarvis-ml**: chezmoi source present and marker-free.
- Others: no chezmoi source on host.

## Hunks resolved

1. **jw14m2 config lines 443–457 and 463–487** (one logical conflict, both
   sides of the 16m1mbp dual-boot aliases). Resolved to upstream `a6dcb11`
   (rationale above). No hunks left for the owner — upstream already carried
   the owner's own resolution; no genuine semantic conflict remained.

## Hosts NOT checked

- **esper / esper-ts** — LAN (192.168.3.191) and Tailscale (100.86.213.92) both
  `Connection timed out`. Asleep or off; both names tried once each.
- **tyrell** — `No route to host` (192.168.3.190).
- **16m1mbp via the old `16m1mbp-macos` tailnet path pre-fix** — expected:
  macOS slice offline while Linux boots (documented in the config comment
  itself). Linux side checked via `jw16mbp1-linux`.
- **forgejo** — reachable but sshd is locked to a forced git command; no shell
  available to run the scan. Its ssh material is unchecked.
- **laptop** alias — same target as jw14m2 (checked via MagicDNS name).

## git assertion

`git merge-base --is-ancestor 63c1d3cf HEAD` fails in
ane-linux-experiments (`Not a valid object name`) — recorded as required before
push of this receipt.
