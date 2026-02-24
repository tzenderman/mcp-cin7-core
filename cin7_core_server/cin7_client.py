from __future__ import annotations

import asyncio
import os
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx


logger = logging.getLogger("cin7_core_server.http")

MAX_RETRIES = 3
RETRY_DELAYS = [1.0, 2.0, 4.0]


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
    """Minimal async client for Cin7 Core (DEAR) API.

    Uses per-request httpx.AsyncClient with automatic retry on transient errors.
    """

    base_url: str
    account_id: str
    application_key: str

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

        return cls(
            base_url=base_url,
            account_id=account_id,
            application_key=application_key,
        )

    def _headers(self) -> dict:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "api-auth-accountid": self.account_id,
            "api-auth-applicationkey": self.application_key,
        }

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        """Execute HTTP request with per-request client and retry logic."""
        async with httpx.AsyncClient(
            base_url=self.base_url,
            headers=self._headers(),
            timeout=httpx.Timeout(30.0, connect=10.0),
        ) as client:
            return await self._execute_with_retry(client, method, path, **kwargs)

    async def _execute_with_retry(
        self, client: httpx.AsyncClient, method: str, path: str, **kwargs
    ) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                start = time.perf_counter()
                response = await getattr(client, method)(path, **kwargs)
                elapsed_ms = (time.perf_counter() - start) * 1000.0

                logger.debug(
                    "HTTP %s %s status=%s elapsed_ms=%.2f",
                    method.upper(),
                    path,
                    response.status_code,
                    elapsed_ms,
                )

                # Don't retry client errors (4xx except 429)
                if 400 <= response.status_code < 500 and response.status_code != 429:
                    return response

                # Retry on rate limit (429) and server errors (5xx)
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt < MAX_RETRIES - 1:
                        logger.warning(
                            "Retrying %s %s (status %s, attempt %d/%d)",
                            method.upper(), path, response.status_code,
                            attempt + 1, MAX_RETRIES,
                        )
                        await asyncio.sleep(RETRY_DELAYS[attempt])
                        continue

                return response

            except (httpx.TimeoutException, httpx.NetworkError) as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    logger.warning(
                        "Retrying %s %s (%s, attempt %d/%d)",
                        method.upper(), path, type(e).__name__,
                        attempt + 1, MAX_RETRIES,
                    )
                    await asyncio.sleep(RETRY_DELAYS[attempt])
                    continue

        raise Cin7ClientError(f"Request failed after {MAX_RETRIES} retries: {last_error}")

    # ----------------------------- API methods -----------------------------

    async def health_check(self) -> Dict[str, Any]:
        """Perform a lightweight authenticated request to verify connectivity."""
        response = await self._request("get", "Product", params={"Page": 1, "Limit": 1})

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
        """Call the Me endpoint to get account/user info."""
        response = await self._request("get", "me")
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
        """List products with pagination and optional filters."""
        params: Dict[str, Any] = {"Page": page, "Limit": limit}
        if name:
            params["Name"] = name
        if sku:
            params["Sku"] = sku
        response = await self._request("get", "Product", params=params)
        try:
            data = response.json()
        except Exception:
            data = {"raw": _truncate(response.text or "")}
        if response.status_code == 200:
            return data if isinstance(data, dict) else {"result": data}
        raise Cin7ClientError(
            f"Product list error: {response.status_code} {response.text[:200]}"
        )

    async def get_product(
        self,
        *,
        product_id: Optional[str] = None,
        sku: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch a single product by ID or SKU."""
        if not product_id and not sku:
            raise Cin7ClientError("get_product requires product_id or sku")

        params: Dict[str, Any] = {}
        if product_id is not None:
            params["ID"] = product_id
        if sku is not None:
            params["Sku"] = sku

        response = await self._request("get", "Product", params=params)
        try:
            data = response.json()
        except Exception:
            data = {"raw": _truncate(response.text or "")}

        if response.status_code == 200 and isinstance(data, dict):
            products = data.get("Products")
            if isinstance(products, list) and products:
                return products[0]
            if data:
                return data
            raise Cin7ClientError("Product not found")

        raise Cin7ClientError(
            f"Product get error: {response.status_code} {response.text[:200]}"
        )

    async def update_product(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """Update a Product via PUT Product."""
        response = await self._request("put", "Product", json=product)
        try:
            data = response.json()
        except Exception:
            data = {"raw": _truncate(response.text or "")}

        if response.status_code in (200, 204):
            return data if isinstance(data, dict) else {"result": data}

        raise Cin7ClientError(
            f"Product update error: {response.status_code} {response.text[:500]}"
        )

    async def save_product(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """Create a Product via POST Product."""
        response = await self._request("post", "Product", json=product)
        try:
            data = response.json()
        except Exception:
            data = {"raw": _truncate(response.text or "")}

        if response.status_code in (200, 201):
            return data if isinstance(data, dict) else {"result": data}

        raise Cin7ClientError(
            f"Product save error: {response.status_code} {response.text[:500]}"
        )

    async def list_suppliers(
        self,
        *,
        page: int = 1,
        limit: int = 100,
        name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List suppliers with pagination and optional filters."""
        params: Dict[str, Any] = {"Page": page, "Limit": limit}
        if name:
            params["Name"] = name
        response = await self._request("get", "Supplier", params=params)
        try:
            data = response.json()
        except Exception:
            data = {"raw": _truncate(response.text or "")}
        if response.status_code == 200:
            return data if isinstance(data, dict) else {"result": data}
        raise Cin7ClientError(
            f"Supplier list error: {response.status_code} {response.text[:200]}"
        )

    async def get_supplier(
        self,
        *,
        supplier_id: Optional[str] = None,
        name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch a single supplier by ID or Name."""
        if not supplier_id and not name:
            raise Cin7ClientError("get_supplier requires supplier_id or name")

        params: Dict[str, Any] = {}
        if supplier_id is not None:
            params["ID"] = supplier_id
        if name is not None:
            params["Name"] = name

        response = await self._request("get", "Supplier", params=params)
        try:
            data = response.json()
        except Exception:
            data = {"raw": _truncate(response.text or "")}

        if response.status_code == 200 and isinstance(data, dict):
            suppliers = data.get("SupplierList")
            if isinstance(suppliers, list) and suppliers:
                return suppliers[0]
            if data:
                return data
            raise Cin7ClientError("Supplier not found")

        raise Cin7ClientError(
            f"Supplier get error: {response.status_code} {response.text[:200]}"
        )

    async def save_supplier(self, supplier: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new Supplier via POST Supplier."""
        response = await self._request("post", "Supplier", json=supplier)
        try:
            data = response.json()
        except Exception:
            data = {"raw": _truncate(response.text or "")}

        if response.status_code in (200, 201):
            return data if isinstance(data, dict) else {"result": data}

        raise Cin7ClientError(
            f"Supplier save error: {response.status_code} {response.text[:200]}"
        )

    async def update_supplier(self, supplier: Dict[str, Any]) -> Dict[str, Any]:
        """Update a Supplier via PUT Supplier."""
        response = await self._request("put", "Supplier", json=supplier)
        try:
            data = response.json()
        except Exception:
            data = {"raw": _truncate(response.text or "")}

        if response.status_code in (200, 204):
            return data if isinstance(data, dict) else {"result": data}

        raise Cin7ClientError(
            f"Supplier update error: {response.status_code} {response.text[:200]}"
        )

    async def list_sales(
        self,
        *,
        page: int = 1,
        limit: int = 100,
        search: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List sales with pagination and optional search filter."""
        params: Dict[str, Any] = {"Page": page, "Limit": limit}
        if search:
            params["Search"] = search
        response = await self._request("get", "saleList", params=params)
        try:
            data = response.json()
        except Exception:
            data = {"raw": _truncate(response.text or "")}
        if response.status_code == 200:
            return data if isinstance(data, dict) else {"result": data}
        raise Cin7ClientError(
            f"Sale list error: {response.status_code} {response.text[:200]}"
        )

    async def get_sale(
        self,
        *,
        sale_id: Optional[str] = None,
        combine_additional_charges: bool = False,
        hide_inventory_movements: bool = False,
        include_transactions: bool = False,
    ) -> Dict[str, Any]:
        """Fetch a single sale by ID with full details including line items."""
        if not sale_id:
            raise Cin7ClientError("get_sale requires sale_id")

        params: Dict[str, Any] = {"ID": sale_id}
        if combine_additional_charges:
            params["CombineAdditionalCharges"] = "true"
        if hide_inventory_movements:
            params["HideInventoryMovements"] = "true"
        if include_transactions:
            params["IncludeTransactions"] = "true"

        response = await self._request("get", "Sale", params=params)
        try:
            data = response.json()
        except Exception:
            data = {"raw": _truncate(response.text or "")}

        if response.status_code == 200 and isinstance(data, dict):
            return data

        raise Cin7ClientError(
            f"Sale get error: {response.status_code} {response.text[:200]}"
        )

    async def save_sale(self, sale: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new Sale via two-step Cin7 API process.

        1. POST to /Sale - creates the base sale header, returns ID
        2. POST to /sale/order - adds order lines using the SaleID

        Status and SkipQuote must be provided by the caller — no defaults are injected.
        """
        payload = dict(sale)

        lines = payload.pop("Lines", None)
        additional_charges = payload.pop("AdditionalCharges", [])
        order_memo = payload.pop("Memo", None)

        # STEP 1: Create the base sale header (without lines)
        response = await self._request("post", "Sale", json=payload)
        try:
            data = response.json()
        except Exception:
            data = {"raw": _truncate(response.text or "")}

        if response.status_code not in (200, 201):
            raise Cin7ClientError(
                f"Sale header creation error: {response.status_code} {response.text[:500]}"
            )

        sale_id = data.get("ID")
        if not sale_id:
            raise Cin7ClientError("No ID returned from Sale creation")

        # STEP 2: Add order lines (if we have any)
        if lines:
            order_payload: Dict[str, Any] = {
                "SaleID": sale_id,
                "Lines": lines,
            }
            if "Status" in payload:
                order_payload["Status"] = payload["Status"]
            if additional_charges:
                order_payload["AdditionalCharges"] = additional_charges
            if order_memo:
                order_payload["Memo"] = order_memo

            order_response = await self._request("post", "sale/order", json=order_payload)
            try:
                order_data = order_response.json()
            except Exception:
                order_data = {"raw": _truncate(order_response.text or "")}

            if order_response.status_code not in (200, 201):
                raise Cin7ClientError(
                    f"Sale order lines creation error (orphaned SaleID={sale_id}): "
                    f"{order_response.status_code} {order_response.text[:500]}"
                )

            if isinstance(order_data, dict):
                data["Order"] = order_data
            return data

        return data if isinstance(data, dict) else {"result": data}

    async def update_sale(self, sale: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing Sale via PUT Sale."""
        response = await self._request("put", "Sale", json=sale)
        try:
            data = response.json()
        except Exception:
            data = {"raw": _truncate(response.text or "")}

        if response.status_code in (200, 204):
            return data if isinstance(data, dict) else {"result": data}

        raise Cin7ClientError(
            f"Sale update error: {response.status_code} {response.text[:500]}"
        )

    async def list_purchase_orders(
        self,
        *,
        page: int = 1,
        limit: int = 100,
        search: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List purchase orders with pagination and optional search filter."""
        params: Dict[str, Any] = {"Page": page, "Limit": limit}
        if search:
            params["Search"] = search
        response = await self._request("get", "purchaseList", params=params)
        try:
            data = response.json()
        except Exception:
            data = {"raw": _truncate(response.text or "")}
        if response.status_code == 200:
            return data if isinstance(data, dict) else {"result": data}
        raise Cin7ClientError(
            f"Purchase Order list error: {response.status_code} {response.text[:200]}"
        )

    async def get_purchase_order(
        self,
        *,
        purchase_order_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch a single purchase order by ID."""
        if not purchase_order_id:
            raise Cin7ClientError("get_purchase_order requires purchase_order_id")

        params: Dict[str, Any] = {"ID": purchase_order_id}
        response = await self._request("get", "Purchase", params=params)
        try:
            data = response.json()
        except Exception:
            data = {"raw": _truncate(response.text or "")}

        if response.status_code == 200 and isinstance(data, dict):
            purchases = data.get("PurchaseList")
            if isinstance(purchases, list) and purchases:
                return purchases[0]
            if data:
                return data
            raise Cin7ClientError("Purchase Order not found")

        raise Cin7ClientError(
            f"Purchase Order get error: {response.status_code} {response.text[:200]}"
        )

    async def save_purchase_order(self, purchase_order: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new Purchase Order via two-step Cin7 API process.

        1. POST to /Purchase - creates the base purchase header, returns TaskID
        2. POST to /purchase/order - adds order lines using the TaskID

        Status must be provided by the caller — no default is injected.
        """
        payload = dict(purchase_order)

        lines = payload.pop("Lines", None)
        additional_charges = payload.pop("AdditionalCharges", [])
        order_memo = payload.pop("Memo", None)
        payload.pop("Order", None)

        # STEP 1: Create the base purchase header (without lines)
        response = await self._request("post", "Purchase", json=payload)
        try:
            data = response.json()
        except Exception:
            data = {"raw": _truncate(response.text or "")}

        if response.status_code not in (200, 201):
            raise Cin7ClientError(
                f"Purchase Order header creation error: {response.status_code} {response.text[:500]}"
            )

        task_id = data.get("ID") or data.get("TaskID")
        if not task_id:
            raise Cin7ClientError("No TaskID returned from Purchase creation")

        # STEP 2: Add order lines (if we have any)
        if lines:
            order_payload: Dict[str, Any] = {
                "TaskID": task_id,
                "Lines": lines,
            }
            if "Status" in payload:
                order_payload["Status"] = payload["Status"]
            if additional_charges:
                order_payload["AdditionalCharges"] = additional_charges
            if order_memo:
                order_payload["Memo"] = order_memo

            order_response = await self._request("post", "purchase/order", json=order_payload)
            try:
                order_data = order_response.json()
            except Exception:
                order_data = {"raw": _truncate(order_response.text or "")}

            if order_response.status_code not in (200, 201):
                raise Cin7ClientError(
                    f"Purchase Order lines creation error (orphaned TaskID={task_id}): "
                    f"{order_response.status_code} {order_response.text[:500]}"
                )

            if isinstance(order_data, dict):
                data["Order"] = order_data
            return data

        return data if isinstance(data, dict) else {"result": data}

    async def list_stock_transfers(
        self,
        *,
        page: int = 1,
        limit: int = 100,
        search: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List stock transfers with pagination and optional search filter."""
        params: Dict[str, Any] = {"Page": page, "Limit": limit}
        if search:
            params["Search"] = search
        response = await self._request("get", "stockTransferList", params=params)
        try:
            data = response.json()
        except Exception:
            data = {"raw": _truncate(response.text or "")}
        if response.status_code == 200:
            return data if isinstance(data, dict) else {"result": data}
        raise Cin7ClientError(
            f"Stock Transfer list error: {response.status_code} {response.text[:200]}"
        )

    async def get_product_suppliers(
        self,
        *,
        product_id: str,
    ) -> Dict[str, Any]:
        """Fetch suppliers for a product by ProductID (Guid).

        API docs: GET /product-suppliers?ProductID=...
        See: https://dearinventory.docs.apiary.io/#reference/reference-books/product-suppliers/get
        """
        if not product_id:
            raise Cin7ClientError("get_product_suppliers requires product_id")

        params: Dict[str, Any] = {"ProductID": product_id}

        response = await self._request("get", "product-suppliers", params=params)
        try:
            data = response.json()
        except Exception:
            data = {"raw": _truncate(response.text or "")}

        if response.status_code == 200 and isinstance(data, dict):
            return data

        raise Cin7ClientError(
            f"ProductSuppliers get error: {response.status_code} {response.text[:200]}"
        )

    async def update_product_suppliers(
        self,
        products: list[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Update suppliers for one or more products via PUT ProductSuppliers."""
        payload = {"Products": products}
        response = await self._request("put", "product-suppliers", json=payload)
        try:
            data = response.json()
        except Exception:
            data = {"raw": _truncate(response.text or "")}

        if response.status_code in (200, 204):
            return data if isinstance(data, dict) else {"result": data}

        raise Cin7ClientError(
            f"ProductSuppliers update error: {response.status_code} {response.text[:500]}"
        )

    async def list_product_availability(
        self,
        *,
        page: int = 1,
        limit: int = 100,
        product_id: Optional[str] = None,
        sku: Optional[str] = None,
        location: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List product availability with stock levels per location."""
        params: Dict[str, Any] = {"Page": page, "Limit": limit}
        if product_id:
            params["ID"] = product_id
        if sku:
            params["Sku"] = sku
        if location:
            params["Location"] = location

        response = await self._request("get", "ref/productavailability", params=params)
        try:
            data = response.json()
        except Exception:
            data = {"raw": _truncate(response.text or "")}

        if response.status_code == 200:
            return data if isinstance(data, dict) else {"result": data}

        raise Cin7ClientError(
            f"ProductAvailability list error: {response.status_code} {response.text[:200]}"
        )

    async def get_product_availability(
        self,
        *,
        product_id: Optional[str] = None,
        sku: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get availability for a single product across all locations."""
        if not product_id and not sku:
            raise Cin7ClientError("get_product_availability requires product_id or sku")

        result = await self.list_product_availability(
            product_id=product_id,
            sku=sku,
            limit=1000,
        )
        return result.get("ProductAvailabilityList", [])

    async def get_stock_transfer(
        self,
        *,
        stock_transfer_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch a single stock transfer by TaskID."""
        if not stock_transfer_id:
            raise Cin7ClientError("get_stock_transfer requires stock_transfer_id")

        params: Dict[str, Any] = {"TaskID": stock_transfer_id}
        response = await self._request("get", "stockTransfer", params=params)
        try:
            data = response.json()
        except Exception:
            data = {"raw": _truncate(response.text or "")}

        if response.status_code == 200 and isinstance(data, dict):
            stock_transfers = data.get("StockTransferList")
            if isinstance(stock_transfers, list) and stock_transfers:
                return stock_transfers[0]
            if data:
                return data
            raise Cin7ClientError("Stock Transfer not found")

        # Handle 400 "not found" errors specifically
        if response.status_code == 400:
            if isinstance(data, list) and data:
                error_obj = data[0]
                if isinstance(error_obj, dict):
                    exception_msg = error_obj.get("Exception", "")
                    if exception_msg and "not found" in exception_msg.lower():
                        raise Cin7ClientError("Stock Transfer not found")

        raise Cin7ClientError(
            f"Stock Transfer get error: {response.status_code} {response.text[:200]}"
        )
