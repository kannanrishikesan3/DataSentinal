#!/usr/bin/env bash
# SQ1 Security — DataSentinel on-prem server (LAN)
#
# Usage (on 192.168.8.99):
#   chmod +x server.sh
#   ./server.sh start          # API :8000 + dashboard :5173
#   ./server.sh token          # create an enrollment token (shown once)
#   ./server.sh help
#
# The enrollment token is NOT stored in this file. Create it with
# `./server.sh token` or in the dashboard (Endpoints → Create enrollment
# token), then pass it to scripts/install-agent.ps1 on each laptop.
set -euo pipefail

ORG_NAME="SQ1 Security"
PUBLIC_IP="${PUBLIC_IP:-192.168.8.99}"
API_PORT="${API_PORT:-8000}"
UI_PORT="${UI_PORT:-5173}"
API_URL="http://${PUBLIC_IP}:${API_PORT}"
UI_URL="http://${PUBLIC_IP}:${UI_PORT}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT/backend"
FRONTEND_DIR="$ROOT/frontend"

if [[ -x "$BACKEND_DIR/.venv/bin/uvicorn" ]]; then
  UVICORN="$BACKEND_DIR/.venv/bin/uvicorn"
  PYTHON="$BACKEND_DIR/.venv/bin/python"
elif [[ -x "$BACKEND_DIR/.venv/Scripts/uvicorn.exe" ]]; then
  UVICORN="$BACKEND_DIR/.venv/Scripts/uvicorn.exe"
  PYTHON="$BACKEND_DIR/.venv/Scripts/python.exe"
else
  UVICORN=""
  PYTHON=""
fi

usage() {
  cat <<EOF
SQ1 Security DataSentinel server

  ./server.sh start    Start API (${API_URL}) and dashboard (${UI_URL})
  ./server.sh token    Login as admin and print a new enrollment token
  ./server.sh help     Show this help

Company: ${ORG_NAME}
Other project on this host can keep port 3000 — this stack uses ${API_PORT} and ${UI_PORT}.

Enrollment token:
  You cannot guess it. After the API is running, run ./server.sh token
  (or create one in the dashboard). It looks like:
    dset_<uuid>_<secret>
  Copy that whole string into scripts/install-agent.ps1 on office laptops.
  It is shown once; after that the server only stores a hash.
EOF
}

require_venv() {
  if [[ -z "$UVICORN" || -z "$PYTHON" ]]; then
    echo "Backend venv not found. On the server, once:" >&2
    echo "  cd $BACKEND_DIR && python3 -m venv .venv && .venv/bin/pip install -e ." >&2
    echo "  cp .env.example .env   # then set CORS to ${UI_URL}" >&2
    echo "  .venv/bin/alembic upgrade head" >&2
    echo "  .venv/bin/python scripts/create_org_admin.py --org '${ORG_NAME}' --email admin@sq1security.local" >&2
    exit 1
  fi
}

cmd_start() {
  require_venv

  echo "==> ${ORG_NAME}"
  echo "    Dashboard: ${UI_URL}"
  echo "    API:       ${API_URL}"
  echo "    Agents must use SERVERURL=${API_URL} (not the dashboard port)."
  echo ""
  echo "    CORS in backend/.env should include:"
  echo "      DATASENTINEL_CORS_ORIGINS=${UI_URL},http://localhost:${UI_PORT}"
  echo ""

  cleanup() {
    echo ""
    echo "==> Stopping SQ1 Security DataSentinel..."
    [[ -n "${API_PID:-}" ]] && kill "$API_PID" 2>/dev/null || true
    [[ -n "${UI_PID:-}" ]] && kill "$UI_PID" 2>/dev/null || true
  }
  trap cleanup EXIT INT TERM

  echo "==> Starting API on 0.0.0.0:${API_PORT}..."
  (
    cd "$BACKEND_DIR"
    exec "$UVICORN" datasentinel_backend.main:app --host 0.0.0.0 --port "$API_PORT"
  ) &
  API_PID=$!

  echo "==> Starting dashboard on 0.0.0.0:${UI_PORT}..."
  (
    cd "$FRONTEND_DIR"
    export VITE_API_BASE_URL="$API_URL"
    exec npm run dev -- --host 0.0.0.0 --port "$UI_PORT"
  ) &
  UI_PID=$!

  echo ""
  echo "Open ${UI_URL}  →  login  →  Endpoints  →  Create enrollment token"
  echo "Or run:  ./server.sh token"
  echo "Ctrl+C to stop."
  wait
}

cmd_token() {
  require_venv

  echo "Create a reusable enrollment token for ${ORG_NAME} laptops."
  echo "API: ${API_URL}"
  echo ""
  read -r -p "Admin email: " ADMIN_EMAIL
  read -r -s -p "Admin password: " ADMIN_PASSWORD
  echo ""

  "$PYTHON" - "$API_URL" "$ADMIN_EMAIL" "$ADMIN_PASSWORD" <<'PY'
import json, sys, urllib.error, urllib.request

api_url, email, password = sys.argv[1], sys.argv[2], sys.argv[3]

def post(path, body, token=None):
    data = json.dumps(body).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(path, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP {exc.code} from {path}\n{detail}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as exc:
        print(f"Cannot reach {path}: {exc.reason}", file=sys.stderr)
        print("Is the server running? ./server.sh start", file=sys.stderr)
        sys.exit(1)

login = post(f"{api_url}/api/v1/auth/login", {"email": email, "password": password})
created = post(
    f"{api_url}/api/v1/enrollment-tokens",
    {
        "name": "SQ1 Security Windows fleet",
        "expires_in_days": 90,
        "max_uses": 500,
        "allowed_os": "windows",
    },
    token=login["access_token"],
)
raw = created["raw_token"]
print()
print("Copy this token now. It will not be shown again.")
print(raw)
print()
print("On each office laptop (PowerShell as Administrator):")
print(f'  .\\scripts\\install-agent.ps1 -EnrollmentToken "{raw}"')
PY
}

case "${1:-start}" in
  start) cmd_start ;;
  token) cmd_token ;;
  help|-h|--help) usage ;;
  *) echo "Unknown command: $1" >&2; usage >&2; exit 1 ;;
esac
