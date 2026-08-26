# e2e/

Playwright browser tests against a **live backend + frontend** — real login,
real RBAC enforcement, real DOM assertions. No mocking of the API; these
catch UI/backend contract drift and RBAC UI gaps that unit tests (which
mock the API layer) can't.

## Running

1. Start a backend against a throwaway database, with a seeded org and
   three users (admin/analyst/viewer) — see
   `backend/scripts/create_org_admin.py` for the admin, then insert
   analyst/viewer rows with the same org_id and `role` set accordingly.
2. `cd frontend && VITE_API_BASE_URL=http://127.0.0.1:8123 npm run dev` (or
   any backend URL/port your seeded instance is on).
3. Update `CREDS` in `rbac.spec.ts` to match your seeded users if different,
   and seed at least one endpoint + scan with findings and one policy (the
   Endpoint-policy-assignment and Finding-detail tests need existing rows).
4. `npx playwright test` (from `frontend/`).

The `analyst can change a finding status` test is written to be idempotent
across repeated runs against the same seeded backend — it inspects which
mutation button is currently offered rather than assuming a fixed starting
status, since the finding's status persists in the backend between runs.
