# tests/

Cross-component integration tests (agent → backend → dashboard end-to-end flows).

Component-level unit tests live alongside each component: `agent/tests/` and
`backend/tests/`.

## `test_agent_to_backend_integration.py`

Runs a real agent scan (the actual discovery/detection pipeline, against a temp
directory containing a synthetic email address) via
`datasentinel_agent.core.pipeline.run_scan`, maps the resulting scan/files/findings
onto the backend's `POST /api/v1/scans` request shape, submits it to a real
in-process FastAPI app (`TestClient`, throwaway SQLite database — no mocking on
either side), and asserts the email finding comes back correctly (redacted, not
raw) from `GET /api/v1/findings`.

### Setup

This test imports both `datasentinel_agent` and `datasentinel_backend`, so both
packages need to be installed into one environment. A dedicated venv at
`tests/.venv` keeps this independent of each component's own `.venv`:

```bash
cd tests
python3 -m venv .venv
source .venv/bin/activate   # .venv\Scripts\activate on Windows
pip install -e ../agent[dev] -e ../backend[dev]
```

### Running

```bash
cd tests
source .venv/bin/activate
pytest test_agent_to_backend_integration.py -v
```
