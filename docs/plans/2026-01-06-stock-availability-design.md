# Stock Availability API Design

## Problem

The Cin7 MCP server doesn't expose actual stock quantities. The Product endpoint only returns `Tags` (e.g., "In Stock", "Out of Stock") - not actual quantities like `OnHand`, `Available`, or `Allocated`.

This causes issues when:
- Comparing Cin7 stock levels to Shopify (sync validation)
- Answering inventory queries ("how much of X is in stock?")

## Solution

Add new MCP tools that expose the Cin7 `ProductAvailability` endpoint, which provides per-location stock levels.

## API Client Layer

Add to `cin7_client.py`:

```python
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

    Maps to GET ProductAvailability endpoint.
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
    # ... standard response handling


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

    # Fetch all matching records
    result = await self.list_product_availability(
        product_id=product_id,
        sku=sku,
        limit=1000
    )
    return result.get("ProductAvailabilityList", [])
```

## MCP Tools Layer

Add to `mcp_server.py`:

### Basic Tools

```python
async def cin7_stock_levels(
    page: int = 1,
    limit: int = 100,
    location: Optional[str] = None,
    fields: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """List stock levels across all products and locations.

    Default fields: SKU, Location, OnHand, Available
    Optional fields: Allocated, OnOrder, InTransit, NextDeliveryDate, Bin, Batch, Barcode

    Args:
        page: Page number (1-indexed)
        limit: Results per page (max 1000)
        location: Filter by location name
        fields: Additional fields beyond defaults

    Returns:
        ProductAvailabilityList with stock data per SKU/location
    """


async def cin7_get_stock(
    sku: Optional[str] = None,
    product_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Get stock levels for a single product across all locations.

    Args:
        sku: Product SKU (preferred)
        product_id: Product GUID

    Returns:
        List of location entries with full stock breakdown:
        - Location: Warehouse name
        - OnHand: Physical quantity
        - Available: OnHand - Allocated
        - Allocated: Reserved for pending orders
        - OnOrder: On purchase orders, not received
        - InTransit: Being transferred between locations
    """
```

### Snapshot Tools

For syncing large catalogs (thousands of SKUs):

```python
async def cin7_stock_snapshot_start(
    page: int = 1,
    limit: int = 100,
    location: Optional[str] = None,
    fields: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Start building a stock availability snapshot.

    Returns snapshot_id to use with status/chunk/close tools.
    """


async def cin7_stock_snapshot_status(
    snapshot_id: str,
) -> Dict[str, Any]:
    """Check snapshot build progress.

    Returns: status (building/ready/error), itemsCollected, total
    """


async def cin7_stock_snapshot_chunk(
    snapshot_id: str,
    offset: int = 0,
    limit: int = 100,
) -> Dict[str, Any]:
    """Fetch a chunk of snapshot data.

    Returns: items, nextOffset (null when exhausted)
    """


async def cin7_stock_snapshot_close(
    snapshot_id: str,
) -> Dict[str, Any]:
    """Close and clean up a snapshot."""
```

## Snapshot Implementation

Reuse existing snapshot pattern:

```python
_stock_snapshots: Dict[str, Dict[str, Any]] = {}

STOCK_SNAPSHOT_TTL_SECONDS = 900  # 15 minutes
STOCK_SNAPSHOT_MAX_ITEMS = 250_000

# Snapshot structure
{
    "id": "uuid",
    "status": "building" | "ready" | "error",
    "created_at": datetime,
    "expires_at": datetime,
    "items": [],
    "total": 0,
    "error": None,
    "params": {
        "location": "...",
        "fields": [...]
    }
}
```

Background build process:
1. `snapshot_start` creates entry, spawns async task
2. Task pages through ProductAvailability API (limit=1000 per request)
3. Applies field projection to reduce memory
4. Caps at 250k items
5. Sets `status="ready"` when complete

## Response Fields

From Cin7 ProductAvailability endpoint:

| Field | Type | Description |
|-------|------|-------------|
| ProductID | guid | Product identifier |
| SKU | string | Product SKU |
| Location | string | Warehouse/location name |
| Bin | string | Bin location within warehouse |
| Batch | string | Batch/lot number |
| OnHand | decimal | Physical stock quantity |
| Available | decimal | Available for orders (OnHand - Allocated) |
| Allocated | decimal | Reserved for pending orders |
| OnOrder | decimal | On purchase orders, not yet received |
| InTransit | decimal | Stock being transferred |
| NextDeliveryDate | datetime | Expected delivery date |
| Barcode | string | Product barcode |
| ExpiryDate | datetime | Batch expiry date |

## Default Field Projection

To reduce payload size, default response includes:
- `SKU`, `Location`, `OnHand`, `Available`

Use `fields` parameter to include additional fields:
- `Allocated`, `OnOrder`, `InTransit`, `NextDeliveryDate`, `Bin`, `Batch`, `Barcode`

## Files to Modify

1. `src/mcp_cin7_core/cin7_client.py` - Add `list_product_availability`, `get_product_availability`
2. `src/mcp_cin7_core/mcp_server.py` - Add 6 MCP tools + snapshot storage/logic
3. `CLAUDE.md` - Document new tools and workflow
4. `tests/test_cin7_client.py` - Client method tests
5. `tests/test_mcp_server.py` - Tool registration and snapshot tests

## Usage Examples

### Single product stock check

```python
# AI query: "How much of VANCR102 is in stock?"
result = await cin7_get_stock(sku="VANCR102")
# Returns:
# [
#   {"Location": "Main Warehouse", "OnHand": 50, "Available": 45, "Allocated": 5},
#   {"Location": "Retail Store", "OnHand": 10, "Available": 10, "Allocated": 0}
# ]
```

### Sync validation workflow

```python
# 1. Start snapshot
result = await cin7_stock_snapshot_start(fields=["Allocated", "OnOrder"])
snapshot_id = result["snapshot_id"]

# 2. Wait for completion
while True:
    status = await cin7_stock_snapshot_status(snapshot_id)
    if status["status"] == "ready":
        break
    await asyncio.sleep(2)

# 3. Fetch all data in chunks
all_stock = []
offset = 0
while offset is not None:
    chunk = await cin7_stock_snapshot_chunk(snapshot_id, offset=offset, limit=500)
    all_stock.extend(chunk["items"])
    offset = chunk["nextOffset"]

# 4. Compare to Shopify inventory
for item in all_stock:
    shopify_qty = get_shopify_inventory(item["SKU"])
    cin7_qty = item["Available"]
    if shopify_qty != cin7_qty:
        print(f"Mismatch: {item['SKU']} - Cin7: {cin7_qty}, Shopify: {shopify_qty}")

# 5. Cleanup
await cin7_stock_snapshot_close(snapshot_id)
```

## References

- [Cin7 Core API - Product Availability](https://dearinventory.docs.apiary.io/#reference/product/product-availability)
- [List of Endpoints](https://help.core.cin7.com/hc/en-us/articles/9034487144079-List-of-Endpoints)
- [Stock Quantity Calculations](https://help.core.cin7.com/hc/en-us/articles/12429786547983-Calculation-of-Available-On-Hand-and-Allocated-Stock-quantity)
