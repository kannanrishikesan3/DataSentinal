#!/usr/bin/env bash
# DataSentinel on-prem deployment — backend + frontend + PostgreSQL, no
# Docker. Mirrors exactly what docker-compose.yml does (see docker/
# for the containerized equivalent) as native systemd services + Apache
# instead of containers: PostgreSQL role/db, a Python venv running the
# FastAPI backend under uvicorn (systemd, reverse-proxied — never exposed
# directly), and the Vite-built static frontend served by Apache
# (mod_proxy + mod_rewrite).
#
# Run as root (or with sudo) from anywhere; point it at a checked-out copy
# of this repo with REPO_DIR (defaults to this script's own repo).
#
# Usage:
#   sudo ./scripts/deploy-on-prem.sh
#   sudo DOMAIN=dashboard.example.com ./scripts/deploy-on-prem.sh
#
# Idempotent and safe on a machine that already has some of this stack
# installed/running — every step re-checks actual state instead of
# assuming a bare machine:
#   - `apt-get install` on an already-installed package is a no-op.
#   - PostgreSQL: reuses the existing `postgresql` service/cluster if one
#     is already running; the role/database are only created if missing
#     (existing ones, and any other databases on the instance, are left
#     untouched).
#   - Apache: reuses an already-installed/running Apache — only enables
#     the modules and site this needs, and only disables the *default*
#     site if it's actually enabled (never touches any other vhost you
#     already have configured).
#   - Re-running after `git pull` redeploys (reinstalls the backend into
#     its venv, re-runs migrations, rebuilds the frontend, reloads
#     services) rather than failing on "already exists".
#
# What this does NOT do:
#   - Provision a TLS certificate. It configures Apache for plain HTTP and
#     prints the certbot command to run afterward once DOMAIN resolves to
#     this machine — spec section 39 requires HTTPS/TLS in production, but
#     issuing a cert needs a real, publicly resolvable domain this script
#     can't assume.
#   - Open firewall ports. Add ufw/firewalld rules for 80/443 yourself if
#     they're not already open.
#   - Remove or reconfigure nginx if it's also installed. If nginx is
#     already bound to port 80/443, Apache will fail to start until you
#     stop/disable nginx or move one of them to a different port —
#     this script won't guess which one you want to keep.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "Run as root (sudo ./scripts/deploy-on-prem.sh)." >&2
    exit 1
fi

if systemctl is-active --quiet nginx 2>/dev/null; then
    echo "WARNING: nginx is currently running and may already be bound to port 80/443." >&2
    echo "         Apache will fail to start if there's a port conflict — stop/disable" >&2
    echo "         nginx first (systemctl stop nginx) if this is meant to replace it." >&2
fi

# ---- Configuration (override via environment) ------------------------------
REPO_DIR="${REPO_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
DOMAIN="${DOMAIN:-}"                                   # e.g. dashboard.example.com; blank = serve on the bare IP
API_PORT="${API_PORT:-8000}"                           # backend's internal, loopback-only port
DB_NAME="${DB_NAME:-datasentinel}"
DB_USER="${DB_USER:-datasentinel}"
DB_PASSWORD="${DB_PASSWORD:-$(openssl rand -base64 24 | tr -d '/+=' | head -c 32)}"
BACKEND_USER="datasentinel-backend"
BACKEND_DIR="/opt/datasentinel-backend"
FRONTEND_DIR="/var/www/datasentinel-frontend"
ENV_FILE="/etc/datasentinel-backend/backend.env"
PUBLIC_ORIGIN="${PUBLIC_ORIGIN:-http://${DOMAIN:-$(hostname -I | awk '{print $1}')}}"

echo "==> Deploying DataSentinel from $REPO_DIR"
echo "    Public origin (frontend build target / CORS): $PUBLIC_ORIGIN"

# ---- 1. System packages -----------------------------------------------------
# `apt-get install` is inherently idempotent — an already-installed package
# (at any version apt considers current) is left alone, not reinstalled.
echo "==> Installing system packages (postgresql, apache2, python3-venv, nodejs)..."
apt-get update -qq
apt-get install -y --no-install-recommends \
    postgresql postgresql-contrib \
    python3-venv python3-pip \
    apache2 \
    openssl rsync \
    ca-certificates curl gnupg

if ! command -v node >/dev/null 2>&1 || [[ "$(node --version | cut -d. -f1 | tr -d v)" -lt 20 ]]; then
    echo "==> Installing Node.js 20.x (NodeSource)..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y nodejs
else
    echo "==> Node.js $(node --version) already installed — skipping."
fi

# ---- 2. PostgreSQL: role + database (idempotent) ---------------------------
# Reuses whatever PostgreSQL is already running (existing databases/roles
# on the instance are never touched) — only creates the role/db this app
# needs, and only if they don't already exist.
echo "==> Configuring PostgreSQL role/database..."
if systemctl is-active --quiet postgresql; then
    echo "    postgresql is already running — reusing it."
else
    systemctl enable --now postgresql
fi

ROLE_EXISTS=$(sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'")
if [[ "$ROLE_EXISTS" != "1" ]]; then
    sudo -u postgres psql -c "CREATE ROLE ${DB_USER} LOGIN PASSWORD '${DB_PASSWORD}';"
elif [[ ! -f "$ENV_FILE" ]]; then
    # The role already exists (e.g. from a prior manual setup) but we're
    # about to mint a *new* backend.env with a freshly-generated
    # DB_PASSWORD — sync the role's actual password to match, otherwise
    # the connection string we write would be wrong. Only safe to do this
    # when ENV_FILE doesn't exist yet: if it does, we leave both the role
    # and the file alone below and never touch DB_PASSWORD/DATABASE_URL.
    echo "    Role '${DB_USER}' already exists — syncing its password to match the new backend.env being created."
    sudo -u postgres psql -c "ALTER ROLE ${DB_USER} WITH PASSWORD '${DB_PASSWORD}';"
else
    echo "    Role '${DB_USER}' and ${ENV_FILE} both already exist — leaving the existing password alone."
fi

sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};"

DATABASE_URL="postgresql+psycopg://${DB_USER}:${DB_PASSWORD}@localhost:5432/${DB_NAME}"

# ---- 3. Backend: system user, venv, install, migrate -----------------------
echo "==> Setting up the backend..."
id -u "$BACKEND_USER" &>/dev/null || useradd --system --no-create-home --shell /usr/sbin/nologin "$BACKEND_USER"

mkdir -p "$BACKEND_DIR" "$(dirname "$ENV_FILE")"
rsync -a --delete \
    --exclude '.venv' --exclude '__pycache__' --exclude '.pytest_cache' \
    "$REPO_DIR/backend/" "$BACKEND_DIR/"

python3 -m venv "$BACKEND_DIR/.venv"
"$BACKEND_DIR/.venv/bin/pip" install --no-cache-dir --upgrade pip
"$BACKEND_DIR/.venv/bin/pip" install --no-cache-dir "$BACKEND_DIR"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "==> Writing $ENV_FILE (generated secret key + DB credentials)..."
    SECRET_KEY="$("$BACKEND_DIR/.venv/bin/python" -c 'import secrets; print(secrets.token_urlsafe(48))')"
    cat > "$ENV_FILE" <<EOF
DATASENTINEL_ENV=production
DATASENTINEL_DATABASE_URL=${DATABASE_URL}
DATASENTINEL_SECRET_KEY=${SECRET_KEY}
DATASENTINEL_ACCESS_TOKEN_EXPIRE_MINUTES=30
DATASENTINEL_CORS_ORIGINS=${PUBLIC_ORIGIN}
DATASENTINEL_LOG_LEVEL=INFO
EOF
    chmod 640 "$ENV_FILE"
    chown "root:$BACKEND_USER" "$ENV_FILE"
else
    echo "==> $ENV_FILE already exists — leaving it as-is (edit it by hand, then re-run this script)."
fi

chown -R "$BACKEND_USER:$BACKEND_USER" "$BACKEND_DIR"

echo "==> Running database migrations (alembic upgrade head)..."
# `sudo -u ... --preserve-env` + a subshell that sources the env file is
# more robust than `env $(grep ... | xargs)` — the latter mis-parses blank
# lines or any value containing spaces/quotes.
sudo -u "$BACKEND_USER" bash -c "set -a; source '$ENV_FILE'; set +a; exec '$BACKEND_DIR/.venv/bin/alembic' -c '$BACKEND_DIR/alembic.ini' upgrade head"

# ---- 4. Backend systemd service ---------------------------------------------
echo "==> Installing the backend systemd service..."
cat > /etc/systemd/system/datasentinel-backend.service <<EOF
[Unit]
Description=DataSentinel Backend API (FastAPI/uvicorn)
After=network-online.target postgresql.service
Wants=network-online.target
Requires=postgresql.service

[Service]
Type=simple
User=${BACKEND_USER}
Group=${BACKEND_USER}
WorkingDirectory=${BACKEND_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${BACKEND_DIR}/.venv/bin/uvicorn datasentinel_backend.main:app --host 127.0.0.1 --port ${API_PORT}
Restart=on-failure
RestartSec=5

NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=${BACKEND_DIR}

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable datasentinel-backend
systemctl restart datasentinel-backend

# ---- 5. Frontend: build + deploy static bundle ------------------------------
echo "==> Building the frontend (this can take a minute)..."
pushd "$REPO_DIR/frontend" >/dev/null
VITE_API_BASE_URL="$PUBLIC_ORIGIN" npm ci
VITE_API_BASE_URL="$PUBLIC_ORIGIN" npm run build
popd >/dev/null

mkdir -p "$FRONTEND_DIR"
rsync -a --delete "$REPO_DIR/frontend/dist/" "$FRONTEND_DIR/"
chown -R www-data:www-data "$FRONTEND_DIR"

# ---- 6. Apache: serve frontend, reverse-proxy /api/ to the backend ---------
# Only touches what this app needs: enables the handful of modules it
# requires (a2enmod is a no-op if a module is already enabled), writes its
# own site config, and disables the *default* site only if that specific
# site is currently enabled — any other vhost you already have configured
# on this Apache instance is left completely alone.
echo "==> Configuring Apache..."
a2enmod proxy proxy_http rewrite headers >/dev/null

cat > /etc/apache2/sites-available/datasentinel.conf <<EOF
<VirtualHost *:80>
    ServerName ${DOMAIN:-_}
    DocumentRoot ${FRONTEND_DIR}

    ProxyPreserveHost On
    ProxyPass /api/ http://127.0.0.1:${API_PORT}/api/
    ProxyPassReverse /api/ http://127.0.0.1:${API_PORT}/api/
    ProxyPass /health http://127.0.0.1:${API_PORT}/health
    ProxyPassReverse /health http://127.0.0.1:${API_PORT}/health

    <Directory ${FRONTEND_DIR}>
        Options -Indexes +FollowSymLinks
        AllowOverride None
        Require all granted

        # SPA fallback: client-side routes (react-router-dom) must serve
        # index.html instead of a 404, but real static files (JS/CSS/
        # images) and the /api and /health proxies above still resolve
        # normally.
        RewriteEngine On
        RewriteCond %{REQUEST_FILENAME} !-f
        RewriteCond %{REQUEST_FILENAME} !-d
        RewriteCond %{REQUEST_URI} !^/api/
        RewriteCond %{REQUEST_URI} !^/health
        RewriteRule ^ index.html [L]
    </Directory>

    ErrorLog \${APACHE_LOG_DIR}/datasentinel-error.log
    CustomLog \${APACHE_LOG_DIR}/datasentinel-access.log combined
</VirtualHost>
EOF

a2ensite datasentinel >/dev/null
if a2query -s 000-default >/dev/null 2>&1; then
    echo "    Disabling Apache's default site (000-default) — it would otherwise shadow this one."
    a2dissite 000-default >/dev/null
fi

apache2ctl configtest
systemctl enable apache2
systemctl reload apache2 || systemctl restart apache2

# ---- 7. Summary --------------------------------------------------------------
echo ""
echo "==> Done."
echo "    Dashboard:        ${PUBLIC_ORIGIN}"
echo "    Backend (direct): http://127.0.0.1:${API_PORT} (loopback-only, not exposed)"
echo "    Backend env:      ${ENV_FILE}"
echo "    DB credentials:   user=${DB_USER} db=${DB_NAME} (password generated into ${ENV_FILE} if this was a fresh install)"
echo ""
echo "    Next steps:"
echo "    - Create the first organization/admin user (there is no signup UI by design):"
echo "        sudo -u ${BACKEND_USER} bash -c \"set -a; source ${ENV_FILE}; set +a; exec ${BACKEND_DIR}/.venv/bin/python ${BACKEND_DIR}/scripts/create_org_admin.py --org 'Your Org' --email admin@example.com\""
echo "    - Enable HTTPS once DOMAIN resolves here: sudo apt install certbot python3-certbot-apache && sudo certbot --apache -d ${DOMAIN:-<your-domain>}"
echo "    - Re-run this script any time after 'git pull' to redeploy (idempotent)."
