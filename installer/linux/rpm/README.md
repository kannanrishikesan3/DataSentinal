# Linux `.rpm` package

Builds `datasentinel-agent-<version>-1.x86_64.rpm` from the same
PyInstaller-frozen CLI binary the `.deb` uses — the RHEL/Rocky
AlmaLinux/Amazon Linux side of spec section 11's "practical installation
method." Install/upgrade/erase all verified for real on this repo's own
Ubuntu 24.04 box (via `rpm -i`/`rpm -U`/`rpm -e` directly — RPM doesn't
require an RPM-based distro to install a package built for one, it just
extracts files and runs scriptlets; a real RHEL-family host is still where
this should get final sign-off, see "Not covered" below).

## Building

```bash
cd installer/linux/rpm
./build.sh 1.0.0          # freezes the binary if needed, then builds the .rpm
```

Requires `rpmbuild` — package `rpm` on Debian/Ubuntu, `rpm-build` on
RHEL-family distros.

## Installing

On a real RHEL/Rocky/AlmaLinux/Amazon Linux host:

```bash
sudo dnf install ./datasentinel-agent-1.0.0-1.x86_64.rpm
# or: sudo yum install ./datasentinel-agent-1.0.0-1.x86_64.rpm
```

This does exactly what the `.deb` does (see `../deb/README.md`): creates
an unprivileged `datasentinel` system user, installs the binary at
`/opt/datasentinel-agent/datasentinel`, installs
`/etc/datasentinel-agent/scan-config.yaml` (a `%config(noreplace)` file —
upgrades never overwrite your edits) and, on first install,
`/etc/datasentinel-agent/agent.env`, then installs/enables/starts the
`datasentinel-agent` systemd service.

Configure it the same way as the `.deb`: edit
`/etc/datasentinel-agent/agent.env`, then
`sudo systemctl restart datasentinel-agent`.

## Verified on this machine

```
sudo rpm -i datasentinel-agent-1.0.0-1.x86_64.rpm   # fresh install
systemctl status datasentinel-agent                  # active (running), correct UID
sudo -u datasentinel .../datasentinel scan ...        # real scan succeeds as the service user
sudo rpm -U datasentinel-agent-1.0.1-1.x86_64.rpm    # upgrade over 1.0.0 — agent.env preserved
sudo rpm -e datasentinel-agent                        # service stopped/disabled, everything removed
```

One real bug was caught and fixed during this: the spec file's `%files`
only listed the binary/config *files*, not the `/opt/datasentinel-agent`
directory itself — RPM doesn't own a directory it wasn't told about, so
`rpm -e` left an empty `/opt/datasentinel-agent/` behind. Fixed with
`%dir /opt/datasentinel-agent` (and the `/etc` equivalent), then
re-verified clean.

## Not covered

- Only `x86_64` — no `aarch64` build/test.
- Built and installed with plain `rpmbuild`/`rpm` on Ubuntu (which has no
  native RPM dependency database), not `dnf`/`yum` on an actual RHEL-family
  host — the package itself is portable, but `dnf install` dependency
  resolution (`Recommends: file-libs`) was never exercised for real.
- Not signed, not published to any repository — install the built file
  directly.
