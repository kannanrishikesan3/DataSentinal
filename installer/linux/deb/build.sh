#!/usr/bin/env bash
# Builds datasentinel-agent_<version>_amd64.deb from the PyInstaller-frozen
# CLI binary. Run from a Linux machine (this repo's own container works —
# it's how this package was actually built and dpkg -i tested).
#
# Usage: ./build.sh [version]
set -euo pipefail

VERSION="${1:-0.1.0}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_DIR="$(cd "$SCRIPT_DIR/../../../agent" && pwd)"
PKG_NAME="datasentinel-agent"
PKG_ROOT="$SCRIPT_DIR/pkgroot"
OUT_FILE="$SCRIPT_DIR/${PKG_NAME}_${VERSION}_amd64.deb"

if [[ ! -x "$AGENT_DIR/dist/datasentinel" ]]; then
    echo "==> Frozen binary not found — building it first (pyinstaller datasentinel-agent.spec)..."
    (cd "$AGENT_DIR" && source .venv/bin/activate && pyinstaller datasentinel-agent.spec --clean)
fi

echo "==> Verifying the frozen binary actually runs..."
"$AGENT_DIR/dist/datasentinel" --version

echo "==> Assembling package tree at $PKG_ROOT ..."
rm -rf "$PKG_ROOT"
mkdir -p \
    "$PKG_ROOT/DEBIAN" \
    "$PKG_ROOT/opt/datasentinel-agent" \
    "$PKG_ROOT/etc/datasentinel-agent" \
    "$PKG_ROOT/lib/systemd/system"

install -m 755 "$AGENT_DIR/dist/datasentinel" "$PKG_ROOT/opt/datasentinel-agent/datasentinel"
install -m 644 "$AGENT_DIR/config/default.yaml" "$PKG_ROOT/etc/datasentinel-agent/scan-config.yaml"
install -m 644 "$SCRIPT_DIR/datasentinel-agent.service" "$PKG_ROOT/lib/systemd/system/datasentinel-agent.service"

install -m 755 "$SCRIPT_DIR/postinst" "$PKG_ROOT/DEBIAN/postinst"
install -m 755 "$SCRIPT_DIR/prerm" "$PKG_ROOT/DEBIAN/prerm"
install -m 755 "$SCRIPT_DIR/postrm" "$PKG_ROOT/DEBIAN/postrm"
install -m 644 "$SCRIPT_DIR/conffiles" "$PKG_ROOT/DEBIAN/conffiles"

installed_size_kb=$(du -sk "$PKG_ROOT" --exclude=DEBIAN | cut -f1)
sed -e "s/__VERSION__/${VERSION}/" "$SCRIPT_DIR/control" > "$PKG_ROOT/DEBIAN/control"
echo "Installed-Size: ${installed_size_kb}" >> "$PKG_ROOT/DEBIAN/control"

echo "==> Building $OUT_FILE ..."
dpkg-deb --build --root-owner-group "$PKG_ROOT" "$OUT_FILE"

echo "==> Lint check (dpkg-deb --info / --contents):"
dpkg-deb --info "$OUT_FILE"
dpkg-deb --contents "$OUT_FILE"

echo "==> Done: $OUT_FILE"
echo "Install with: sudo apt install $OUT_FILE   (or: sudo dpkg -i $OUT_FILE)"
