"""MCP resource handlers for templates."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

from ..cin7_client import Cin7Client
from ..utils.logging import truncate

logger = logging.getLogger("cin7_core_server.resources.templates")


# ----------------------------- Product Templates -----------------------------

async def resource_product_template() -> str:
    """Blank product template with all available fields and required field indicators.

    Use this template to see what fields are available when creating products.
    """
    template = {
        "SKU": "",
        "Name": "",
        "Category": "",
        "Brand": "",
        "Barcode": "",
        "Status": "",
        "Type": "",
        "UOM": "Item",
        "CostingMethod": "",
        "DefaultLocation": "",
        "PriceTier1": 0.0,
        "PriceTier2": 0.0,
        "PurchasePrice": 0.0,
        "COGSAccount": "5000",
        "RevenueAccount": "4000",
        "InventoryAccount": "1401",
        "PurchaseTaxRule": "",
        "SaleTaxRule": "",
        "Suppliers": []
    }
    return json.dumps(template, indent=2)


async def resource_product_by_id(product_id: str) -> str:
    """Get existing product as template for updates."""
    logger.debug("Resource call: resource_product_by_id(product_id=%s)", product_id)
    client = Cin7Client.from_env()
    product = await client.get_product(product_id=product_id)
    logger.debug("Resource result: resource_product_by_id -> %s", truncate(str(product)))
    return json.dumps(product, indent=2)


async def resource_product_by_sku(sku: str) -> str:
    """Get existing product by SKU as template for updates."""
    logger.debug("Resource call: resource_product_by_sku(sku=%s)", sku)
    client = Cin7Client.from_env()
    product = await client.get_product(sku=sku)
    logger.debug("Resource result: resource_product_by_sku -> %s", truncate(str(product)))
    return json.dumps(product, indent=2)


# ----------------------------- Supplier Templates -----------------------------

async def resource_supplier_template() -> str:
    """Blank supplier template with all available fields."""
    template = {
        "Name": "",
        "ContactPerson": "",
        "Phone": "",
        "Email": "",
        "Website": "",
        "Address": {
            "Line1": "",
            "Line2": "",
            "City": "",
            "State": "",
            "Postcode": "",
            "Country": ""
        },
        "PaymentTerm": "",
        "Discount": 0.0,
        "TaxRule": "",
        "Currency": ""
    }
    return json.dumps(template, indent=2)


async def resource_supplier_by_id(supplier_id: str) -> str:
    """Get existing supplier as template for updates."""
    logger.debug("Resource call: resource_supplier_by_id(supplier_id=%s)", supplier_id)
    client = Cin7Client.from_env()
    supplier = await client.get_supplier(supplier_id=supplier_id)
    logger.debug("Resource result: resource_supplier_by_id -> %s", truncate(str(supplier)))
    return json.dumps(supplier, indent=2)


async def resource_supplier_by_name(name: str) -> str:
    """Get existing supplier by name as template for updates."""
    logger.debug("Resource call: resource_supplier_by_name(name=%s)", name)
    client = Cin7Client.from_env()
    supplier = await client.get_supplier(name=name)
    logger.debug("Resource result: resource_supplier_by_name -> %s", truncate(str(supplier)))
    return json.dumps(supplier, indent=2)


# ----------------------------- Purchase Order Templates -----------------------------

async def resource_purchase_order_template() -> str:
    """Blank purchase order template with all available fields."""
    template = {
        "TaskID": "",
        "Supplier": "",
        "Location": "",
        "Status": "",
        "OrderDate": "",
        "RequiredBy": "",
        "CurrencyCode": "",
        "Note": "",
        "Lines": [
            {
                "ProductID": "",
                "SKU": "",
                "Name": "",
                "Quantity": 1.0,
                "Price": 0.0,
                "Tax": 0.0,
                "TaxRule": "",
                "Total": 0.0,
                "Discount": 0.0,
                "SupplierSKU": "",
                "Comment": "",
            }
        ],
        "AdditionalCharges": [
            {
                "Description": "",
                "Quantity": 1.0,
                "Price": 0.0,
                "Tax": 0.0,
                "TaxRule": "",
                "Total": 0.0,
                "Reference": "",
                "Discount": 0.0,
            }
        ],
        "Memo": "",
    }
    return json.dumps(template, indent=2)


async def resource_purchase_order_by_id(purchase_order_id: str) -> str:
    """Get existing purchase order as template for review or updates."""
    logger.debug("Resource call: resource_purchase_order_by_id(purchase_order_id=%s)", purchase_order_id)
    client = Cin7Client.from_env()
    purchase_order = await client.get_purchase_order(purchase_order_id=purchase_order_id)
    logger.debug("Resource result: resource_purchase_order_by_id -> %s", truncate(str(purchase_order)))
    return json.dumps(purchase_order, indent=2)


# ----------------------------- Sale Templates -----------------------------

async def resource_sale_template() -> str:
    """Blank sale template with all available fields."""
    template = {
        "CustomerID": "",
        "Customer": "",
        "Phone": "",
        "Email": "",
        "Contact": "",
        "DefaultAccount": "200",
        "BillingAddress": {
            "Line1": "",
            "Line2": "",
            "City": "",
            "State": "",
            "Postcode": "",
            "Country": ""
        },
        "ShippingAddress": {
            "Line1": "",
            "Line2": "",
            "City": "",
            "State": "",
            "Postcode": "",
            "Country": "",
            "Company": "",
            "Contact": "",
            "ShipToOther": False
        },
        "ShippingNotes": "",
        "TaxRule": "",
        "Terms": "",
        "PriceTier": "Tier 1",
        "Location": "",
        "Note": "",
        "CustomerReference": "",
        "SalesRepresentative": "",
        "Carrier": "",
        "CurrencyRate": 1.0,
        "SaleOrderDate": "",
        "ShipBy": "",
        "SkipQuote": None,
        "Status": "",
        "Lines": [
            {
                "ProductID": "",
                "SKU": "",
                "Name": "",
                "Quantity": 1.0,
                "Price": 0.0,
                "Discount": 0.0,
                "Tax": 0.0,
                "AverageCost": 0.0,
                "TaxRule": "",
                "Comment": "",
                "Total": 0.0,
            }
        ],
        "AdditionalCharges": [
            {
                "Description": "",
                "Price": 0.0,
                "Quantity": 1.0,
                "Discount": 0.0,
                "Tax": 0.0,
                "Total": 0.0,
                "TaxRule": "",
                "Comment": ""
            }
        ],
        "Memo": "",
    }
    return json.dumps(template, indent=2)


async def resource_sale_by_id(sale_id: str) -> str:
    """Get existing sale as template for review or updates."""
    logger.debug("Resource call: resource_sale_by_id(sale_id=%s)", sale_id)
    client = Cin7Client.from_env()
    sale = await client.get_sale(sale_id=sale_id)
    logger.debug("Resource result: resource_sale_by_id -> %s", truncate(str(sale)))
    return json.dumps(sale, indent=2)
