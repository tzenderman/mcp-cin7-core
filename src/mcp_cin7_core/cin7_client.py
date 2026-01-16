from __future__ import annotations

import os
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Callable, List, Optional

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
            logger.debug(
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
            logger.debug(
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


    async def get_product(
        self,
        *,
        product_id: Optional[str] = None,
        sku: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch a single product by ID or SKU.

        Maps to GET Product endpoint with filters. If multiple products are
        returned (e.g., by SKU), the first item is returned.

        Docs: https://dearinventory.docs.apiary.io/#reference/product/product
        """
        if not product_id and not sku:
            raise Cin7ClientError("get_product requires product_id or sku")

        params: Dict[str, Any] = {}
        if product_id is not None:
            params["ID"] = product_id
        if sku is not None:
            params["SKU"] = sku

        response = await self.client.get("Product", params=params)
        try:
            data = response.json()
        except Exception:
            data = {"raw": _truncate(response.text or "")}

        if response.status_code == 200 and isinstance(data, dict):
            products = data.get("Products")
            if isinstance(products, list) and products:
                return products[0]
            # Some responses might directly return the object; fall back to data
            if data:
                return data
            raise Cin7ClientError("Product not found")

        raise Cin7ClientError(
            f"Product get error: {response.status_code} {response.text[:200]}"
        )

    async def update_product(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """Update a Product via PUT Product.

        Provide the full product payload as required by Cin7 Core. Typically
        includes the product ID along with updated fields.

        Docs: https://dearinventory.docs.apiary.io/#reference/product/product
        """
        logger.debug("Cin7Client.update_product called with payload: %s", product)
        logger.debug("Payload size: %d chars, keys: %s", len(str(product)), list(product.keys()) if isinstance(product, dict) else "NOT A DICT")

        try:
            response = await self.client.put("Product", json=product)
            logger.debug("Cin7 API PUT Product response status: %d", response.status_code)
            logger.debug("Cin7 API response headers: %s", dict(response.headers))
            logger.debug("Cin7 API response body (first 1000 chars): %s", response.text[:1000] if response.text else "(empty)")

            try:
                data = response.json()
            except Exception as json_error:
                logger.error("Failed to parse Cin7 response as JSON: %s", str(json_error))
                data = {"raw": _truncate(response.text or "")}

            if response.status_code in (200, 204):
                logger.debug("Product update successful, returning data")
                return data if isinstance(data, dict) else {"result": data}

            error_msg = f"Product update error: {response.status_code} {response.text[:500]}"
            logger.error("Product update failed: %s", error_msg)
            logger.debug("Full response text: %s", response.text)
            raise Cin7ClientError(error_msg)

        except Cin7ClientError:
            raise
        except Exception as e:
            logger.error("Unexpected error in update_product: %s", str(e), exc_info=True)
            raise

    async def save_product(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update a Product.

        This is a pass-through to the Cin7 Core "Product" endpoint that accepts a
        JSON payload per the API. Use it to create or update product data.

        Docs: https://dearinventory.docs.apiary.io/#reference/product/product
        """
        logger.debug("Cin7Client.save_product called with payload: %s", product)
        logger.debug("Payload size: %d chars, keys: %s", len(str(product)), list(product.keys()) if isinstance(product, dict) else "NOT A DICT")

        try:
            response = await self.client.post("Product", json=product)
            logger.debug("Cin7 API POST Product response status: %d", response.status_code)
            logger.debug("Cin7 API response headers: %s", dict(response.headers))
            logger.debug("Cin7 API response body (first 1000 chars): %s", response.text[:1000] if response.text else "(empty)")

            try:
                data = response.json()
            except Exception as json_error:
                logger.error("Failed to parse Cin7 response as JSON: %s", str(json_error))
                data = {"raw": _truncate(response.text or "")}

            if response.status_code in (200, 201):
                logger.debug("Product save successful, returning data")
                return data if isinstance(data, dict) else {"result": data}

            error_msg = f"Product save error: {response.status_code} {response.text[:500]}"
            logger.error("Product save failed: %s", error_msg)
            logger.debug("Full response text: %s", response.text)
            raise Cin7ClientError(error_msg)

        except Cin7ClientError:
            raise
        except Exception as e:
            logger.error("Unexpected error in save_product: %s", str(e), exc_info=True)
            raise

    async def list_suppliers(
        self,
        *,
        page: int = 1,
        limit: int = 100,
        name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List suppliers with pagination and optional filters.

        Maps to GET Supplier endpoint.
        Common params per docs: Page, Limit, Name.
        Docs: https://dearinventory.docs.apiary.io/#reference/supplier/supplier/get
        """
        params: Dict[str, Any] = {"Page": page, "Limit": limit}
        if name:
            params["Name"] = name
        response = await self.client.get("Supplier", params=params)
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
        """Fetch a single supplier by ID or Name.

        Maps to GET Supplier endpoint with filters. If multiple suppliers are
        returned (e.g., by Name), the first item is returned.

        Docs: https://dearinventory.docs.apiary.io/#reference/supplier/supplier/get
        """
        if not supplier_id and not name:
            raise Cin7ClientError("get_supplier requires supplier_id or name")

        params: Dict[str, Any] = {}
        if supplier_id is not None:
            params["ID"] = supplier_id
        if name is not None:
            params["Name"] = name

        response = await self.client.get("Supplier", params=params)
        try:
            data = response.json()
        except Exception:
            data = {"raw": _truncate(response.text or "")}

        if response.status_code == 200 and isinstance(data, dict):
            suppliers = data.get("SupplierList")
            if isinstance(suppliers, list) and suppliers:
                return suppliers[0]
            # Some responses might directly return the object; fall back to data
            if data:
                return data
            raise Cin7ClientError("Supplier not found")

        raise Cin7ClientError(
            f"Supplier get error: {response.status_code} {response.text[:200]}"
        )

    async def save_supplier(self, supplier: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new Supplier via POST Supplier.

        Provide the full supplier payload as required by Cin7 Core.

        Docs: https://dearinventory.docs.apiary.io/#reference/supplier/supplier/post
        """
        response = await self.client.post("Supplier", json=supplier)
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
        """Update a Supplier via PUT Supplier.

        Provide the full supplier payload as required by Cin7 Core. Typically
        includes the supplier ID along with updated fields.

        Docs: https://dearinventory.docs.apiary.io/#reference/supplier/supplier/put
        """
        response = await self.client.put("Supplier", json=supplier)
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
        """List sales with pagination and optional search filter.

        Maps to GET SaleList endpoint.
        Common params per docs: Page, Limit, Search.
        Docs: https://help.core.cin7.com/hc/en-us/articles/9034555593871-SaleList
        """
        params: Dict[str, Any] = {"Page": page, "Limit": limit}
        if search:
            params["Search"] = search
        response = await self.client.get("SaleList", params=params)
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
        """Fetch a single sale by ID with full details including line items.

        Maps to GET Sale endpoint with ID filter.
        Returns complete sale data including Quote, Order, Fulfilments, Invoices,
        CreditNotes, and optionally InventoryMovements and Transactions.

        Args:
            sale_id: The sale UUID (required)
            combine_additional_charges: Combine additional charges into response
            hide_inventory_movements: Hide inventory movement details
            include_transactions: Include transaction details

        Docs: https://dearinventory.docs.apiary.io/#reference/sale/sale/get
        """
        if not sale_id:
            raise Cin7ClientError("get_sale requires sale_id")

        params: Dict[str, Any] = {"ID": sale_id}
        if combine_additional_charges:
            params["CombineAdditionalCharges"] = "true"
        if hide_inventory_movements:
            params["HideInventoryMovements"] = "true"
        if include_transactions:
            params["IncludeTransactions"] = "true"

        response = await self.client.get("Sale", params=params)
        try:
            data = response.json()
        except Exception:
            data = {"raw": _truncate(response.text or "")}

        if response.status_code == 200 and isinstance(data, dict):
            return data

        raise Cin7ClientError(
            f"Sale get error: {response.status_code} {response.text[:200]}"
        )

    async def list_purchase_orders(
        self,
        *,
        page: int = 1,
        limit: int = 100,
        search: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List purchase orders with pagination and optional search filter.

        Maps to GET PurchaseList endpoint.
        Common params per docs: Page, Limit, Search.
        Docs: https://help.core.cin7.com/hc/en-us/articles/9034547620751-PurchaseList
        """
        params: Dict[str, Any] = {"Page": page, "Limit": limit}
        if search:
            params["Search"] = search
        response = await self.client.get("PurchaseList", params=params)
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
        """Fetch a single purchase order by ID.

        Maps to GET Purchase endpoint with ID filter.
        Docs: https://dearinventory.docs.apiary.io/#reference/purchase/purchase-order/get
        """
        if not purchase_order_id:
            raise Cin7ClientError("get_purchase_order requires purchase_order_id")

        params: Dict[str, Any] = {"ID": purchase_order_id}
        response = await self.client.get("Purchase", params=params)
        try:
            data = response.json()
        except Exception:
            data = {"raw": _truncate(response.text or "")}

        if response.status_code == 200 and isinstance(data, dict):
            purchases = data.get("PurchaseList")
            if isinstance(purchases, list) and purchases:
                return purchases[0]
            # Some responses might directly return the object; fall back to data
            if data:
                return data
            raise Cin7ClientError("Purchase Order not found")

        raise Cin7ClientError(
            f"Purchase Order get error: {response.status_code} {response.text[:200]}"
        )

    async def save_purchase_order(self, purchase_order: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new Purchase Order via POST Purchase.

        Provide the full purchase order payload as required by Cin7 Core.
        The Status field should be set to "DRAFT" to allow user review before authorization.

        The payload can have Lines at the top level (convenience) or nested under Order.
        This method normalizes the structure before sending to the API.

        Docs: https://dearinventory.docs.apiary.io/#reference/purchase/purchase-order/post
        """
        logger.debug("Cin7Client.save_purchase_order called with payload: %s", purchase_order)
        logger.debug("Payload size: %d chars, keys: %s", len(str(purchase_order)), list(purchase_order.keys()) if isinstance(purchase_order, dict) else "NOT A DICT")

        # Make a copy to avoid mutating the original
        payload = dict(purchase_order)

        # Ensure Status is DRAFT for new purchase orders
        if "Status" not in payload:
            payload["Status"] = "DRAFT"
        elif payload.get("Status") != "DRAFT":
            logger.warning("Purchase Order Status was %s, forcing to DRAFT", payload.get("Status"))
            payload["Status"] = "DRAFT"

        # Cin7 API expects Lines nested under Order for Advanced POs
        # If Lines is at top level, move it into Order structure
        if "Lines" in payload and "Order" not in payload:
            lines = payload.pop("Lines")
            additional_charges = payload.pop("AdditionalCharges", [])
            memo = payload.pop("Memo", None)
            # Create Order object with Status="DRAFT" for Advanced PO
            payload["Order"] = {
                "Status": "DRAFT",
                "Lines": lines,
                "AdditionalCharges": additional_charges,
            }
            if memo is not None:
                payload["Order"]["Memo"] = memo
            logger.debug("Restructured payload: moved Lines into Order object (Advanced PO)")
        elif "Order" in payload and isinstance(payload["Order"], dict):
            # Ensure Order.Status is set for Advanced PO
            if "Status" not in payload["Order"]:
                payload["Order"]["Status"] = "DRAFT"
                logger.debug("Set Order.Status to DRAFT for Advanced PO")

        try:
            response = await self.client.post("Purchase", json=payload)
            logger.debug("Cin7 API POST Purchase response status: %d", response.status_code)
            logger.debug("Cin7 API response headers: %s", dict(response.headers))
            logger.debug("Cin7 API response body (first 1000 chars): %s", response.text[:1000] if response.text else "(empty)")

            try:
                data = response.json()
            except Exception as json_error:
                logger.error("Failed to parse Cin7 response as JSON: %s", str(json_error))
                data = {"raw": _truncate(response.text or "")}

            if response.status_code in (200, 201):
                logger.debug("Purchase Order save successful, returning data")
                return data if isinstance(data, dict) else {"result": data}

            error_msg = f"Purchase Order save error: {response.status_code} {response.text[:500]}"
            logger.error("Purchase Order save failed: %s", error_msg)
            logger.debug("Full response text: %s", response.text)
            raise Cin7ClientError(error_msg)

        except Cin7ClientError:
            raise
        except Exception as e:
            logger.error("Unexpected error in save_purchase_order: %s", str(e), exc_info=True)
            raise

    async def list_stock_transfers(
        self,
        *,
        page: int = 1,
        limit: int = 100,
        search: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List stock transfers with pagination and optional search filter.

        Maps to GET StockTransferList endpoint.
        Common params per docs: Page, Limit, Search.
        Docs: https://dearinventory.docs.apiary.io/#reference/stock/stock-transfer-list
        """
        params: Dict[str, Any] = {"Page": page, "Limit": limit}
        if search:
            params["Search"] = search
        response = await self.client.get("StockTransferList", params=params)
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
        product_id: Optional[str] = None,
        sku: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch suppliers for a product by ID or SKU.

        Maps to GET ProductSuppliers endpoint.
        Docs: https://help.core.cin7.com/hc/en-us/articles/9034477854607-Product-Suppliers
        """
        if not product_id and not sku:
            raise Cin7ClientError("get_product_suppliers requires product_id or sku")

        params: Dict[str, Any] = {}
        if product_id is not None:
            params["ID"] = product_id
        if sku is not None:
            params["SKU"] = sku

        response = await self.client.get("ProductSuppliers", params=params)
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
        """Update suppliers for one or more products via PUT ProductSuppliers.

        IMPORTANT: You must supply the FULL list of suppliers for each product.
        If a supplier is not provided, the association will be deleted.

        Args:
            products: List of dicts, each with:
                - ProductID: Product GUID (required)
                - Suppliers: List of supplier objects (required)

        Up to 100 products can be updated in one batch.

        Docs: https://help.core.cin7.com/hc/en-us/articles/9034477854607-Product-Suppliers
        """
        logger.debug("Cin7Client.update_product_suppliers called with %d products", len(products))

        payload = {"Products": products}

        try:
            response = await self.client.put("ProductSuppliers", json=payload)
            logger.debug("Cin7 API PUT ProductSuppliers response status: %d", response.status_code)

            try:
                data = response.json()
            except Exception as json_error:
                logger.error("Failed to parse ProductSuppliers response as JSON: %s", str(json_error))
                data = {"raw": _truncate(response.text or "")}

            if response.status_code in (200, 204):
                logger.debug("ProductSuppliers update successful")
                return data if isinstance(data, dict) else {"result": data}

            error_msg = f"ProductSuppliers update error: {response.status_code} {response.text[:500]}"
            logger.error("ProductSuppliers update failed: %s", error_msg)
            raise Cin7ClientError(error_msg)

        except Cin7ClientError:
            raise
        except Exception as e:
            logger.error("Unexpected error in update_product_suppliers: %s", str(e), exc_info=True)
            raise

    async def list_product_availability(
        self,
        *,
        page: int = 1,
        limit: int = 100,
        product_id: Optional[str] = None,
        sku: Optional[str] = None,
        location: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List product availability with stock levels per location.

        Maps to GET ref/productavailability endpoint.
        Returns: ProductID, SKU, Location, OnHand, Available,
                 Allocated, OnOrder, InTransit, NextDeliveryDate, Bin, Batch

        Docs: https://dearinventory.docs.apiary.io/#reference/product/product-availability
        """
        params: Dict[str, Any] = {"Page": page, "Limit": limit}
        if product_id:
            params["ProductID"] = product_id
        if sku:
            params["SKU"] = sku
        if location:
            params["Location"] = location

        response = await self.client.get("ref/productavailability", params=params)
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
        """Get availability for a single product across all locations.

        Returns list of location entries (one product can have multiple
        location records).
        """
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
        """Fetch a single stock transfer by TaskID.

        Maps to GET StockTransfer endpoint with TaskID query parameter.
        The stock_transfer_id parameter should be the TaskID from the list response.
        Docs: https://dearinventory.docs.apiary.io/#reference/stock/stock-transfer
        """
        if not stock_transfer_id:
            raise Cin7ClientError("get_stock_transfer requires stock_transfer_id")

        # StockTransfer endpoint expects TaskID as a query parameter
        params: Dict[str, Any] = {"TaskID": stock_transfer_id}
        response = await self.client.get("StockTransfer", params=params)
        try:
            data = response.json()
        except Exception:
            data = {"raw": _truncate(response.text or "")}

        if response.status_code == 200 and isinstance(data, dict):
            stock_transfers = data.get("StockTransferList")
            if isinstance(stock_transfers, list) and stock_transfers:
                return stock_transfers[0]
            # Some responses might directly return the object; fall back to data
            if data:
                return data
            raise Cin7ClientError("Stock Transfer not found")

        # Handle 400 "not found" errors specifically
        if response.status_code == 400:
            # Check if the already-parsed data contains a "not found" error
            if isinstance(data, list) and data:
                error_obj = data[0]
                if isinstance(error_obj, dict):
                    exception_msg = error_obj.get("Exception", "")
                    if exception_msg and "not found" in exception_msg.lower():
                        raise Cin7ClientError("Stock Transfer not found")

        raise Cin7ClientError(
            f"Stock Transfer get error: {response.status_code} {response.text[:200]}"
        )

