"""MCP prompt functions for workflow guidance."""

from __future__ import annotations


async def create_product() -> str:
    """Guide for creating a Cin7 Core product with all required fields."""
    return """Create a product in Cin7 Core:

1. Read cin7://templates/product to see all available fields

2. REQUIRED fields for Cin7 API:
   - SKU (unique identifier)
   - Name (product title)
   - Category (product category)
   - Status (Active or Inactive)
   - Type (Stock, Service, or Bundle)
   - UOM (Item, Case, Box, etc.)
   - CostingMethod (FIFO, LIFO, or Average)
   - DefaultLocation (warehouse location)

3. Recommended fields:
   - Brand (manufacturer name)
   - Barcode (typically 12-digit UPC)
   - PriceTier1, PriceTier2 (pricing)
   - PurchasePrice (cost)
   - Suppliers array (supplier information)

4. Accounting fields (often required):
   - COGSAccount, RevenueAccount, InventoryAccount
   - PurchaseTaxRule, SaleTaxRule

5. Use cin7_create_product tool with complete payload

6. Verify creation with cin7_get_product using returned ID
"""


async def update_batch() -> str:
    """Guide for batch updating products with error collection."""
    return """Batch update products in Cin7 Core:

1. Retrieve products to update using cin7_products or snapshot tools

2. For each product, read template: cin7://templates/product/{id}

3. Prepare ALL changes (show user complete before/after list)

4. Get explicit ONE-TIME approval from user for entire batch

5. Execute updates with cin7_update_product for each product:
   - Continue on failures (don't stop)
   - Track successes and failures separately
   - Show progress: \u2713 Product 1/N, \u2717 Product 2/N (error), etc.

6. Report summary: X succeeded, Y failed

7. For failures, show error details and offer to retry

Error handling: Collect all errors, continue processing, report at end.
"""


async def verify_required_fields() -> str:
    """Check product data completeness before creation/update."""
    return """Verify product has required Cin7 Core fields:

Required fields checklist:
\u25a1 SKU
\u25a1 Name
\u25a1 Category
\u25a1 Status
\u25a1 Type
\u25a1 UOM
\u25a1 CostingMethod
\u25a1 DefaultLocation

Recommended fields:
\u25a1 Brand
\u25a1 Barcode
\u25a1 Pricing (PriceTier1, PriceTier2, PurchasePrice)

Report any missing or empty required fields before proceeding.
"""


async def create_purchase_order() -> str:
    """Guide for creating a Cin7 Core purchase order."""
    return """Create a purchase order in Cin7 Core:

1. Read cin7://templates/purchase_order to see all available fields

2. REQUIRED fields for Cin7 API:
   - Supplier (supplier name or ID)
   - Location (warehouse location)
   - OrderDate (YYYY-MM-DD format)
   - Lines (array with at least one line item)

3. Each line item REQUIRES:
   - ProductID (GUID from cin7_get_product)
   - SKU (product SKU)
   - Name (product name)
   - Quantity (order quantity, minimum 1)
   - Price (unit price per unit)
   - Tax (tax amount)
   - TaxRule (tax rule name, e.g., "Tax Exempt")
   - Total (line total for validation: (Price \u00d7 Quantity) - Discount + Tax)

   Optional line fields:
   - Discount (0-100, default 0)
   - SupplierSKU (supplier's SKU)
   - Comment (line comment)

4. Optional: AdditionalCharges array for service charges
   Each additional charge REQUIRES:
   - Description (service product name)
   - Quantity (minimum 1)
   - Price (unit price)
   - Tax (tax amount)
   - TaxRule (tax rule name)
   - Total (line total for validation)

5. IMPORTANT: Status field behavior
   - All new purchase orders are created with Status="DRAFT"
   - This allows user review in Cin7 Core before authorization
   - Users can authorize the PO in the Cin7 Core web interface

6. Optional but recommended PO-level fields:
   - RequiredBy (expected delivery date)
   - CurrencyCode (defaults to USD)
   - Note (internal note)
   - Memo (external memo to supplier)

7. Use cin7_create_purchase_order tool with complete payload

8. Verify creation with cin7_get_purchase_order using returned TaskID

Example workflow:
- Get supplier info with cin7_get_supplier
- Get product info with cin7_get_product (to get ProductID, SKU, Name)
- Calculate line totals: (Price \u00d7 Quantity) - Discount + Tax
- Build Lines array with all required fields
- Set OrderDate to today's date
- Submit with cin7_create_purchase_order
- PO will be created as DRAFT for user review
"""


async def create_sale() -> str:
    """Guide for creating a Cin7 Core sale."""
    return """Create a sale in Cin7 Core:

1. Read cin7://templates/sale to see all available fields

2. REQUIRED fields for Cin7 API:
   - Customer (customer name) or CustomerID (customer GUID)
   - Location (warehouse/sales location)
   - Lines (array with at least one line item)

3. Each line item REQUIRES:
   - ProductID (GUID from cin7_get_product)
   - SKU (product SKU)
   - Name (product name)
   - Quantity (sale quantity, minimum 1)
   - Price (unit price per unit)
   - Tax (tax amount)
   - TaxRule (tax rule name, e.g., "Tax Exempt")
   - Total (line total for validation: (Price \u00d7 Quantity) - Discount + Tax)

   Optional line fields:
   - Discount (0-100, default 0)
   - AverageCost (for margin calculation)
   - Comment (line comment)

4. Optional: AdditionalCharges array for service charges
   Each additional charge includes:
   - Description (service product name)
   - Quantity, Price, Tax, TaxRule, Total

5. IMPORTANT: Status field behavior
   - All new sales are created with Status="DRAFT" by default
   - This creates a Draft Quote for user review
   - Set Status="AUTHORISED" to create an authorized Quote
   - Users can convert Quote to Order in Cin7 Core web interface

6. Optional but recommended sale-level fields:
   - BillingAddress, ShippingAddress
   - TaxRule (default tax rule for sale)
   - Terms (payment terms, e.g., "30 days")
   - PriceTier (customer price tier)
   - SaleOrderDate (defaults to today)
   - CustomerReference (customer's PO number)
   - SalesRepresentative
   - SkipQuote (false = Quote stage, true = skip to Order)

7. Use cin7_create_sale tool with complete payload

8. Verify creation with cin7_get_sale using returned SaleID

Example workflow:
- Use customer name directly or look up CustomerID
- Get product info with cin7_get_product (to get ProductID, SKU, Name)
- Calculate line totals: (Price \u00d7 Quantity) - Discount + Tax
- Build Lines array with all required fields
- Submit with cin7_create_sale
- Sale will be created as Draft Quote for user review
"""
