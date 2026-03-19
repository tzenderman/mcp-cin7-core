"""Stock adjustment mock API responses."""

SA_LIST_RESPONSE = {
    "StockAdjustmentList": [
        {
            "TaskID": "sa-task-001",
            "Status": "COMPLETED",
            "EffectiveDate": "2026-03-01",
            "Reference": "ADJ-2026-001",
            "Account": "Cost of Goods Sold",
        },
        {
            "TaskID": "sa-task-002",
            "Status": "DRAFT",
            "EffectiveDate": "2026-03-05",
            "Reference": "ADJ-2026-002",
            "Account": "Inventory",
        },
    ],
    "Total": 2,
}

SA_SINGLE = {
    "TaskID": "sa-task-001",
    "Status": "COMPLETED",
    "EffectiveDate": "2026-03-01",
    "Reference": "ADJ-2026-001",
    "Account": "Cost of Goods Sold",
    "UpdateOnHand": True,
    # Note: stock adjustment API uses "ProductName" (not "Name" like PO/sale line items)
    "Lines": [
        {
            "ProductID": "prod-abc-123",
            "SKU": "WIDGET-001",
            "ProductName": "Blue Widget",
            "Quantity": 10,
            "UnitCost": 12.50,
            "Location": "Main Warehouse",
        }
    ],
}

SA_CREATE_RESPONSE = {
    "TaskID": "sa-task-new-789",
    "Status": "DRAFT",
    "EffectiveDate": "2026-03-05",
    "UpdateOnHand": True,
    # Note: stock adjustment API uses "ProductName" (not "Name" like PO/sale line items)
    "Lines": [
        {
            "ProductID": "prod-abc-123",
            "SKU": "WIDGET-001",
            "ProductName": "Blue Widget",
            "Quantity": 5,
            "UnitCost": 12.50,
            "Location": "Main Warehouse",
        }
    ],
}
