from __future__ import annotations

import os
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Callable, Optional

import httpx


logger = logging.getLogger("mcp_cin7_core.http")


def _redact_headers(headers: Dict[str, Any]) -> Dict[str, Any]:
    redacted = {}
    for k, v in headers.items():
        lk = str(k).lower()
        if lk in {"api-auth-accountid", "api-auth-applicationkey", "authorization"}:
            redacted[k] = "[REDACTED]"
        else:
            redacted[k] = v
    return redacted


def _truncate(text: str, max_len: int = 1000) -> str:
    if text is None:
        return ""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "... [truncated]"


class Cin7ClientError(Exception):
    """Represents an error when communicating with Cin7 Core API."""


@dataclass
class Cin7Client:
    """Minimal async client for Cin7 Core (DEAR) API."""

    base_url: str
    account_id: str
    application_key: str
    client: httpx.AsyncClient

    @classmethod
    def from_env(cls) -> "Cin7Client":
        """Create a client using environment variables loaded via dotenv.

        Required env vars:
        - CIN7_ACCOUNT_ID
        - CIN7_API_KEY
        Optional:
        - CIN7_BASE_URL (defaults to DEAR v2)
        """
        base_url = os.getenv(
            "CIN7_BASE_URL", "https://inventory.dearsystems.com/ExternalApi/v2/"
        )
        account_id = os.getenv("CIN7_ACCOUNT_ID")
        application_key = os.getenv("CIN7_API_KEY")

        if not account_id or not application_key:
            raise Cin7ClientError(
                "Missing CIN7_ACCOUNT_ID or CIN7_API_KEY in environment."
            )

        if not base_url.endswith("/"):
            base_url = base_url + "/"

        async def on_request(request: httpx.Request) -> None:
            request.extensions["_start_time"] = time.perf_counter()
            try:
                content = request.content.decode() if isinstance(request.content, (bytes, bytearray)) else str(request.content)
            except Exception:
                content = "<un-decodable body>"
            logger.info(
                "HTTP Request: %s %s headers=%s body=%s",
                request.method,
                str(request.url),
                _redact_headers(dict(request.headers)),
                _truncate(content),
            )

        async def on_response(response: httpx.Response) -> None:
            start = response.request.extensions.get("_start_time")
            elapsed_ms: Optional[float] = None
            if isinstance(start, float):
                elapsed_ms = (time.perf_counter() - start) * 1000.0
            body_text = None
            try:
                body_text = response.text
            except Exception:
                body_text = "<un-decodable body>"
            logger.info(
                "HTTP Response: %s %s status=%s elapsed_ms=%s body=%s",
                response.request.method,
                str(response.request.url),
                response.status_code,
                f"{elapsed_ms:.2f}" if elapsed_ms is not None else "?",
                _truncate(body_text),
            )

        client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "api-auth-accountid": account_id,
                "api-auth-applicationkey": application_key,
            },
            timeout=httpx.Timeout(30.0, connect=10.0),
            event_hooks={
                "request": [on_request],
                "response": [on_response],
            },
        )

        return cls(
            base_url=base_url,
            account_id=account_id,
            application_key=application_key,
            client=client,
        )

    async def aclose(self) -> None:
        await self.client.aclose()

    async def health_check(self) -> Dict[str, Any]:
        """Perform a lightweight authenticated request to verify connectivity.

        We call GET Product with Page=1, Limit=1 which should be fast and
        verifies that credentials and base URL are correct.
        """
        response = await self.client.get("Product", params={"Page": 1, "Limit": 1})

        data: Dict[str, Any] = {}
        try:
            parsed = response.json()
            if isinstance(parsed, dict):
                data = parsed
        except Exception:
            parsed = None

        if response.status_code == 200:
            products = data.get("Products") if isinstance(data, dict) else None
            sample_count = len(products) if isinstance(products, list) else 0
            return {
                "ok": True,
                "status": response.status_code,
                "sample_count": sample_count,
                "rate_limit_remaining": response.headers.get("X-RateLimit-Remaining"),
                "base_url": self.base_url,
            }

        raise Cin7ClientError(
            f"Cin7 Core auth failed or API error: {response.status_code} "
            f"{response.text[:200]}"
        )

    async def get_me(self) -> Dict[str, Any]:
        """Call the Me endpoint to get account/user info.

        Docs: https://dearinventory.docs.apiary.io/#reference/me
        """
        response = await self.client.get("Me")
        try:
            data = response.json()
        except Exception:
            data = {"raw": _truncate(response.text or "")}
        if response.status_code == 200:
            return data if isinstance(data, dict) else {"result": data}
        raise Cin7ClientError(
            f"Me endpoint error: {response.status_code} {response.text[:200]}"
        )

    async def list_products(
        self,
        *,
        page: int = 1,
        limit: int = 100,
        name: Optional[str] = None,
        sku: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List products with pagination and optional filters.

        Maps to GET Product endpoint.
        Common params per docs: Page, Limit, Name, SKU.
        Docs: https://dearinventory.docs.apiary.io/#reference/product/product
        """
        params: Dict[str, Any] = {"Page": page, "Limit": limit}
        if name:
            params["Name"] = name
        if sku:
            params["SKU"] = sku
        response = await self.client.get("Product", params=params)
        try:
            data = response.json()
        except Exception:
            data = {"raw": _truncate(response.text or "")}
        if response.status_code == 200:
            return data if isinstance(data, dict) else {"result": data}
        raise Cin7ClientError(
            f"Product list error: {response.status_code} {response.text[:200]}"
        )


