# DataSentinel Dashboard

SOC-style security dashboard: Overview, Endpoints, Scans, Findings, PII Explorer,
Secrets, Policies, Reports, Audit Logs, Settings. Built with React, TypeScript, Vite,
Tailwind CSS, shadcn/ui, Recharts, and TanStack Query.

## Status

All ten nav pages are implemented and wired to the real backend API: Overview
(stat tiles + severity/category/endpoint charts), Endpoints (register + list),
Scans (list + cancel), Findings (filterable table + detail dialog with false-
positive/suppress/reopen actions), PII Explorer (category quick-filters),
Secrets, Policies (create/list), Reports (download JSON/CSV/HTML/text), Audit
Logs, and Settings. JWT auth with a login screen and protected routes.

Verified end-to-end with a headless-browser smoke test against a live backend
+ seeded data (login → every page → finding detail → endpoint registration →
report download → policy creation), zero console errors. See
[`../docs/PHASES.md`](../docs/PHASES.md) for details.

## Setup

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

## Structure

```text
src/
├── components/
│   ├── ui/           # shadcn/ui-style primitives (Button, Card, Table, Select, Dialog, ...)
│   └── layout/        # Sidebar + app shell
├── pages/             # Route-level views, one per nav item
├── lib/               # api-client (fetch wrapper + auth), auth-context, cn() utility
├── types/              # TypeScript types mirroring backend/.../api/v1/schemas.py
└── api/                # TanStack Query hooks, one module per backend resource
```

Path alias `@/` resolves to `src/`. Severity colors are centralized in
`components/severity-badge.tsx` — Critical/High/Medium/Low/Informational, used
consistently across badges and charts.
