#!/usr/bin/env bash
# Installs the DataSentinel agent as a systemd service.
#
# Usage: sudo ./install-linux-service.sh [install-dir]
#
# Expects the agent to already be installed (pip install -e . or a
# PyInstaller build) at install-dir (default: /opt/datasentinel-agent).
set -euo pipefail

INSTALL_DIR="${1:-/opt/datasentinel-agent}"
DATA_DIR="/var/lib/datasentinel-agent"
CONFIG_DIR="/etc/datasentinel-agent"
SERVICE_NAME="datasentinel-agent"
SERVICE_USER="datasentinel"

if [[ $EUID -ne 0 ]]; then
    echo "This script must be run as root (it creates a system user and a systemd unit)." >&2
    exit 1
fi

if ! id "$SERVICE_USER" &>/dev/null; then
    echo "Creating unprivileged service account '$SERVICE_USER'…"
    useradd --system --no-create-home --shell /usr/sbin/nologin "$SERVICE_USER"
fi

mkdir -p "$DATA_DIR" "$CONFIG_DIR"
chown "$SERVICE_USER:$SERVICE_USER" "$DATA_DIR"

if [[ ! -f "$CONFIG_DIR/agent.env" ]]; then
    echo "Writing default $CONFIG_DIR/agent.env (edit this to configure AI/backend settings)…"
    cat > "$CONFIG_DIR/agent.env" <<'EOF'
AI_ENABLED=false
OPENROUTER_API_KEY=
OPENROUTER_MODEL=
DATASENTINEL_BACKEND_URL=
DATASENTINEL_ENDPOINT_TOKEN=
DATASENTINEL_LOG_LEVEL=INFO
EOF
    chmod 640 "$CONFIG_DIR/agent.env"
    chown "root:$SERVICE_USER" "$CONFIG_DIR/agent.env"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
sed "s|/opt/datasentinel-agent|$INSTALL_DIR|g" "$SCRIPT_DIR/datasentinel-agent.service" \
    > "/etc/systemd/system/${SERVICE_NAME}.service"

echo "Applying local database migrations…"
sudo -u "$SERVICE_USER" env DATASENTINEL_DB_PATH="$DATA_DIR/datasentinel.db" \
    "$INSTALL_DIR/.venv/bin/alembic" -c "$INSTALL_DIR/alembic.ini" upgrade head

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl start "$SERVICE_NAME"

echo "Installed. Check status with: systemctl status $SERVICE_NAME"
echo "Manage schedules with:        sudo -u $SERVICE_USER DATASENTINEL_DB_PATH=$DATA_DIR/datasentinel.db DATASENTINEL_SCHEDULES_PATH=$DATA_DIR/schedules.json $INSTALL_DIR/.venv/bin/datasentinel schedule add ..."
