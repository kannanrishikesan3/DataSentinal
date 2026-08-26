"""Thin HTTP client for the agent's (optional) calls to the central
backend. Mirrors `ai.openrouter_client`'s timeout/retry conventions:
short timeout, a couple of retries with backoff, and every failure mode
collapses to one exception type the caller can catch and fall back from.
"""

from __future__ import annotations

import httpx
from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential


class BackendUnavailable(Exception):
    """Raised on any failure talking to the backend — network error, non-2xx
    response, or an unparseable body. Callers must treat this as "continue
    with local state", never as fatal to the scan."""


class BackendClient:
    def __init__(
        self,
        base_url: str,
        endpoint_token: str,
        *,
        timeout_seconds: float = 10.0,
        max_retries: int = 2,
        transport: httpx.BaseTransport | None = None,
    ):
        self._base_url = base_url.rstrip("/")
        self._token = endpoint_token
        self._max_retries = max_retries
        self._client = httpx.Client(timeout=timeout_seconds, transport=transport)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "BackendClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def _get(self, path: str) -> object:
        def _request_once() -> object:
            response = self._client.get(
                f"{self._base_url}{path}",
                headers={"Authorization": f"Bearer {self._token}"},
            )
            response.raise_for_status()
            return response.json()

        try:
            for attempt in Retrying(
                stop=stop_after_attempt(self._max_retries + 1),
                wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
                retry=retry_if_exception_type(httpx.TransportError),
                reraise=True,
            ):
                with attempt:
                    return _request_once()
        except (httpx.HTTPError, ValueError) as exc:
            raise BackendUnavailable(str(exc)) from exc
        raise BackendUnavailable("unreachable")  # pragma: no cover - Retrying always returns or raises

    def fetch_effective_policies(self) -> list[dict]:
        """GET /api/v1/policies/effective — the org's centrally-defined
        policies, authenticated with this endpoint's own API token."""
        data = self._get("/api/v1/policies/effective")
        if not isinstance(data, list):
            raise BackendUnavailable("Unexpected response shape from /api/v1/policies/effective")
        return data

    def submit_scan_report(self, payload: dict) -> None:
        """POST /api/v1/scans — uploads one completed (or in-progress)
        scan's report. Raises `BackendUnavailable` on any failure; the
        caller (`sync.scan_uploader`) is responsible for retry/queueing."""

        def _request_once() -> None:
            response = self._client.post(
                f"{self._base_url}/api/v1/scans",
                headers={"Authorization": f"Bearer {self._token}"},
                json=payload,
            )
            response.raise_for_status()

        try:
            for attempt in Retrying(
                stop=stop_after_attempt(self._max_retries + 1),
                wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
                retry=retry_if_exception_type(httpx.TransportError),
                reraise=True,
            ):
                with attempt:
                    _request_once()
                    return
        except httpx.HTTPError as exc:
            raise BackendUnavailable(str(exc)) from exc
