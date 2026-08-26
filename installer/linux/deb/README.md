# Linux `.deb` package

Builds `datasentinel-agent_<version>_amd64.deb` from the PyInstaller-frozen
CLI binary (`agent/datasentinel-agent.spec`) — spec section 11's "practical
installation method" for the agent, install/upgrade/remove/purge tested for
real (not just written) on this repo's own Ubuntu 24.04 (systemd) container.

## Building

```bash
cd installer/linux/deb
./build.sh 1.0.0          # freezes the binary if needed, then builds the .deb
```

Produces `datasentinel-agent_1.0.0_amd64.deb` in this directory.

## Installing

```bash
sudo apt install ./datasentinel-agent_1.0.0_amd64.deb
# or: sudo dpkg -i datasentinel-agent_1.0.0_amd64.deb
```

This:

1. Creates an unprivileged system user/group `datasentinel` (no login shell,
   no home directory access needed to run).
2. Installs the binary at `/opt/datasentinel-agent/datasentinel`.
3. Installs `/etc/datasentinel-agent/scan-config.yaml` (a dpkg conffile —
   edit it to change scan profiles, include/exclude paths, or risk
   thresholds; upgrades never overwrite your edits) and, on first install
   only, `/etc/datasentinel-agent/agent.env` (backend URL, endpoint token,
   AI settings — blank/local-only by default).
4. Installs and enables the `datasentinel-agent` systemd service, and
   starts it immediately if systemd is running.

Configure it for a real deployment by editing
`/etc/datasentinel-agent/agent.env`:

```env
DATASENTINEL_BACKEND_URL=https://dashboard.example.com
DATASENTINEL_ENDPOINT_TOKEN=<token from POST /api/v1/endpoints/register>
```

then `sudo systemctl restart datasentinel-agent`.

## Verified on this machine

```
sudo dpkg -i datasentinel-agent_0.1.0_amd64.deb   # fresh install
systemctl status datasentinel-agent               # active (running), correct UID
sudo -u datasentinel .../datasentinel scan ...     # real scan succeeds as the service user
sudo dpkg -i datasentinel-agent_0.1.1_amd64.deb   # upgrade over 0.1.0 — agent.env preserved
sudo apt remove datasentinel-agent                 # service stopped/disabled, /opt removed, /etc kept
sudo apt purge datasentinel-agent                  # /etc, /var/lib, and the service user all removed
```

One real bug was caught and fixed during this: `postrm` originally only
removed `/var/lib/datasentinel-agent` on purge, leaving
`/etc/datasentinel-agent/agent.env` behind (it's deliberately not a dpkg
conffile — see `postinst`'s "write only if absent" logic — so dpkg doesn't
purge it automatically). Fixed to also `rm -rf` the config directory on
purge, then re-verified clean.

## Not covered

- Only `amd64` — no arm64 build/test.
- Not tested on Debian/RHEL-family distros beyond this Ubuntu 24.04
  container (spec section 45 also lists RHEL/Rocky/AlmaLinux/Amazon Linux —
  those would need an `.rpm` build instead of `.deb`, which isn't done).
- Not published to any APT repository — install the built file directly.
