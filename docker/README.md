# docker/

Local / self-hosted deployment of the full DataSentinel stack: PostgreSQL, the
FastAPI backend, and the static frontend dashboard. This is for running the
whole system in one place (a laptop, a single VM, a demo box) — it is **not**
a production-hardening guide. For that (secrets management, TLS termination,
network policy, least-privilege, etc.) see [`../SECURITY.md`](../SECURITY.md).

## Contents

- `backend.Dockerfile` — multi-stage build of `../backend` (installs from
  `pyproject.toml`, runs `uvicorn datasentinel_backend.main:app`). Does **not**
  run `alembic upgrade head` on container start — see the rationale in the
  Dockerfile and in `backend/datasentinel_backend/main.py`'s module
  docstring. Migrations run as an explicit one-shot step instead.
- `frontend.Dockerfile` — multi-stage build of `../frontend` (`npm ci && npm
  run build`), served by a minimal nginx image with an SPA fallback for
  client-side routing.
- `docker-compose.yml` — wires up `postgres:16-alpine`, a one-shot
  `backend-migrate` service (`alembic upgrade head`), the `backend` API, and
  the `frontend` static server.
- `.env.example` — template for the `.env` file compose reads. Mirrors the
  relevant variables from `../backend/.env.example` and
  `../frontend/.env.example`, pointed at the compose service hostnames.

## Usage

```bash
cd docker
cp .env.example .env
# edit .env: set DATASENTINEL_SECRET_KEY and change the Postgres password
docker compose up --build
```

This will:

1. Start `postgres` and wait for its healthcheck to pass.
2. Run `backend-migrate` (`alembic upgrade head`) to completion against that
   Postgres instance.
3. Start `backend` (FastAPI, `http://localhost:8000`) once migrations
   succeed.
4. Start `frontend` (`http://localhost:5173`), a static build of the
   dashboard configured to call the backend at `VITE_API_BASE_URL`.

Postgres data persists in the named volume `docker_postgres_data` across
`docker compose down` / `up` cycles; use `docker compose down -v` to also
wipe it.

`VITE_API_BASE_URL` is baked into the frontend's static JS bundle at build
time (Vite inlines `VITE_*` vars at build, not at container runtime), so
changing it requires `docker compose up --build frontend` again, not just a
restart.

## Notes

- Never commit a real `.env` — only `.env.example` with placeholders is
  checked in.
- The `backend` service depends on `backend-migrate` completing successfully
  (`condition: service_completed_successfully`), which in turn depends on
  `postgres`'s healthcheck — so a first-time `docker compose up` always
  applies the schema before the API can receive traffic.
- To run only a subset (e.g. just the database, for pointing a locally-run
  backend at it), use `docker compose up postgres`.
