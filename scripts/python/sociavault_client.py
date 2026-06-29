"""SociaVault REST API client for datasyn-local.

Docs: https://docs.sociavault.com
Auth: X-API-Key header (SOCIAVAULT_API_KEY in .env)
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx
from dotenv import load_dotenv

BASE_URL = "https://api.sociavault.com"
RATE_LIMIT_SECONDS = 1.0


def _dig(data: Any, *keys: str, default: Any = None) -> Any:
    node = data
    for key in keys:
        if not isinstance(node, dict):
            return default
        node = node.get(key)
    return node if node is not None else default


class SociaVaultError(Exception):
    """Base error for SociaVault API failures."""


class SociaVaultAuthError(SociaVaultError):
    """Missing or invalid API key."""


class SociaVaultCreditsError(SociaVaultError):
    """Insufficient credits (HTTP 402)."""

    def __init__(self, message: str, required: int | None = None, available: int | None = None):
        super().__init__(message)
        self.required = required
        self.available = available


class SociaVaultClient:
    """Thin wrapper around SociaVault scrape endpoints."""

    def __init__(self, api_key: str | None = None, *, rate_limit: float = RATE_LIMIT_SECONDS):
        load_dotenv()
        self.api_key = api_key or os.getenv("SOCIAVAULT_API_KEY", "").strip()
        if not self.api_key:
            raise SociaVaultAuthError(
                "SOCIAVAULT_API_KEY not set. Copy .env.example to .env and add your key."
            )
        self.rate_limit = rate_limit
        self._last_request_at = 0.0
        self.credits_used = 0
        self.requests: list[dict[str, Any]] = []

    def _wait_rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._wait_rate_limit()
        url = f"{BASE_URL}{path}" if path.startswith("/") else f"{BASE_URL}/{path}"
        headers = {"X-API-Key": self.api_key, "Accept": "application/json"}

        with httpx.Client(timeout=60, follow_redirects=True) as client:
            resp = client.request(method, url, params=params or {}, headers=headers)

        self._last_request_at = time.monotonic()
        meta = {
            "path": path,
            "params": params or {},
            "status_code": resp.status_code,
        }

        try:
            body: dict[str, Any] = resp.json()
        except Exception:
            body = {"error": resp.text, "success": False}

        credits = body.get("credits_used") or body.get("data", {}).get("credits_used")
        if isinstance(credits, (int, float)):
            self.credits_used += int(credits)

        meta["credits_used"] = credits
        meta["endpoint"] = body.get("endpoint")
        meta["success"] = body.get("success", resp.is_success)
        self.requests.append(meta)

        if resp.status_code == 401:
            raise SociaVaultAuthError(body.get("error", "Invalid API key"))
        if resp.status_code == 402:
            raise SociaVaultCreditsError(
                body.get("error", "Insufficient credits"),
                required=body.get("required"),
                available=body.get("available"),
            )
        if resp.status_code >= 400:
            raise SociaVaultError(body.get("error", f"HTTP {resp.status_code}: {resp.text[:200]}"))

        return body

    def get_credits(self) -> dict[str, Any]:
        """GET /v1/credits — current balance."""
        return self._request("GET", "/v1/credits")

    def scrape(self, platform: str, resource: str, params: dict[str, Any]) -> dict[str, Any]:
        """Call GET /v1/scrape/{platform}/{resource}."""
        path = f"/v1/scrape/{platform}/{resource}"
        clean = {k: v for k, v in params.items() if v is not None and v != ""}
        return self._request("GET", path, params=clean)

    def scrape_pages(
        self,
        platform: str,
        resource: str,
        params: dict[str, Any],
        *,
        cursor_param: str = "cursor",
        cursor_paths: tuple[str, ...] = ("data", "cursor"),
        max_pages: int = 50,
    ) -> list[dict[str, Any]]:
        """Paginate while cursor is present in the response."""
        pages: list[dict[str, Any]] = []
        cursor: str | None = None

        for _ in range(max_pages):
            page_params = dict(params)
            if cursor:
                page_params[cursor_param] = cursor

            page = self.scrape(platform, resource, page_params)
            pages.append(page)

            cursor = _dig(page, cursor_paths)
            if not cursor:
                break

        return pages
