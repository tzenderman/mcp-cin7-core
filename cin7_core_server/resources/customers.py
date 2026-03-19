"""Customer tools."""

from __future__ import annotations

import logging
from typing import Any, Dict

from ..cin7_client import Cin7Client
from ..utils.logging import truncate
from ..utils.projection import project_dict, project_items

logger = logging.getLogger("cin7_core_server.resources.customers")


async def cin7_customers(
    limit: int = 100,
    cursor: str | None = None,
    search: str | None = None,
    fields: list[str] | None = None,
) -> Dict[str, Any]:
    """List customers with pagination and optional name filter.

    Parameters:
    - limit: Items per page (Cin7 limits apply)
    - cursor: Opaque cursor for next page (pass from previous response)
    - search: Optional name filter
    - fields: Additional fields to include beyond defaults, or ["*"] for all fields

    Available fields: ID, Name, Email, Phone, Status, Currency, PaymentTerm, TaxRule
        Default returns: ID, Name
    """
    logger.debug(
        "Tool call: cin7_customers(limit=%s, cursor=%s, search=%s)",
        limit, cursor, search,
    )
    page = int(cursor) if cursor else 1
    client = Cin7Client.from_env()
    raw = await client.list_customers(page=page, limit=limit, name=search)

    items = raw.get("CustomerList", [])
    total = raw.get("Total", len(items))

    items = project_items(items, fields, base_fields={"ID", "Name"})

    has_more = (page * limit) < total
    result = {
        "results": items,
        "has_more": has_more,
        "cursor": str(page + 1) if has_more else None,
        "total_returned": len(items),
    }
    logger.debug("Tool result: cin7_customers -> %s", truncate(str(result)))
    return result


async def cin7_get_customer(
    customer_id: str | None = None,
    name: str | None = None,
    fields: list[str] | None = None,
) -> Dict[str, Any]:
    """Get a single customer by ID or name.

    Parameters:
    - customer_id: Customer GUID
    - name: Customer name
    - fields: Additional fields to include beyond defaults, or ["*"] for all fields

    Available fields: ID, Name, Email, Phone, Status, Currency, PaymentTerm, TaxRule
        Default returns: ID, Name
    """
    logger.debug(
        "Tool call: cin7_get_customer(customer_id=%s, name=%s)",
        customer_id, name,
    )
    client = Cin7Client.from_env()
    result = await client.get_customer(customer_id=customer_id, name=name)

    result = project_dict(result, fields, base_fields={"ID", "Name"})

    logger.debug("Tool result: cin7_get_customer -> %s", truncate(str(result)))
    return result


async def cin7_create_customer(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new Cin7 Core customer via POST customer.

    Required fields: Name, Status, Currency, PaymentTerm, AccountReceivable,
        RevenueAccount, TaxRule

    Use cin7://templates/customer to get a blank template with all fields.

    Key payload structure notes:
    - Contact (string): header-level contact name
    - Contacts (array): list of contact objects, each with:
        Name, Phone, Email, Comment, Default (bool)
    - Addresses (array): list of address objects, each with:
        Line1, Line2, City, State, Postcode, Country, Type ("Billing"/"Shipping")
    - Optional fields: Location, Carrier, SalesRepresentative, PriceTier,
        Discount, CreditLimit, Comments

    Docs: https://dearinventory.docs.apiary.io/#reference/customer/customer/post
    """
    logger.debug("Tool call: cin7_create_customer(payload=%s)", truncate(str(payload)))
    client = Cin7Client.from_env()
    result = await client.save_customer(payload)
    logger.debug("Tool result: cin7_create_customer -> %s", truncate(str(result)))
    return result


async def cin7_update_customer(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Update a Cin7 Core customer via PUT customer.

    Docs: https://dearinventory.docs.apiary.io/#reference/customer/customer/put
    """
    logger.debug("Tool call: cin7_update_customer(payload=%s)", truncate(str(payload)))
    client = Cin7Client.from_env()
    result = await client.update_customer(payload)
    logger.debug("Tool result: cin7_update_customer -> %s", truncate(str(result)))
    return result
