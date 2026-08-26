#!/usr/bin/env bash
# Builds datasentinel-agent-<version>-1.x86_64.rpm from the PyInstaller-
# frozen CLI binary — the RHEL/Rocky/AlmaLinux/Amazon Linux equivalent of
# ../deb/build.sh. Requires `rpmbuild` (the `rpm` package on Debian/Ubuntu,
# `rpm-build` on RHEL-family distros).
#
# Usage: ./build.sh [version]
set -euo pipefail

VERSION="${1:-1.0.0}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_DIR="$(cd "$SCRIPT_DIR/../../../agent" && pwd)"
TOPDIR="$SCRIPT_DIR/build"

if [[ ! -x "$AGENT_DIR/dist/datasentinel" ]]; then
    echo "==> Frozen binary not found — building it first (pyinstaller datasentinel-agent.spec)..."
    (cd "$AGENT_DIR" && source .venv/bin/activate && pyinstaller datasentinel-agent.spec --clean)
fi

echo "==> Verifying the frozen binary actually runs..."
"$AGENT_DIR/dist/datasentinel" --version

rm -rf "$TOPDIR"
mkdir -p "$TOPDIR"/{BUILD,RPMS,SOURCES,SPECS,SRPMS,BUILDROOT}

echo "==> Building the RPM (version $VERSION)..."
rpmbuild \
    --define "_topdir $TOPDIR" \
    --define "_ds_version $VERSION" \
    --define "_ds_binary $AGENT_DIR/dist/datasentinel" \
    --define "_ds_service_file $SCRIPT_DIR/../deb/datasentinel-agent.service" \
    --define "_ds_scan_config $AGENT_DIR/config/default.yaml" \
    -bb "$SCRIPT_DIR/datasentinel-agent.spec"

RPM_FILE=$(find "$TOPDIR/RPMS" -name '*.rpm' | head -1)
cp "$RPM_FILE" "$SCRIPT_DIR/"
OUT_FILE="$SCRIPT_DIR/$(basename "$RPM_FILE")"

echo "==> Lint check (rpm -qip / -qlp):"
rpm -qip "$OUT_FILE"
rpm -qlp "$OUT_FILE"

echo "==> Done: $OUT_FILE"
echo "Install with: sudo rpm -i $OUT_FILE   (or: sudo dnf install $OUT_FILE / sudo yum install $OUT_FILE on a real RHEL-family host)"
