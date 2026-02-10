"""Purchase order mock API responses."""

PO_LIST_RESPONSE = {
    "PurchaseList": [
        {
            "TaskID": "po-task-001",
            "Supplier": "Acme Supplies",
            "Status": "DRAFT",
            "OrderDate": "2024-06-01",
            "Location": "Main Warehouse",
            "Total": 500.00,
            "RequiredBy": "2024-07-01",
        },
        {
            "TaskID": "po-task-002",
            "Supplier": "Global Parts Inc",
            "Status": "AUTHORISED",
            "OrderDate": "2024-06-02",
            "Location": "Store",
            "Total": 1200.00,
            "RequiredBy": "2024-07-15",
        },
    ],
    "Total": 2,
}

PO_SINGLE = {
    "ID": "po-abc-123",
    "TaskID": "po-task-001",
    "Supplier": "Acme Supplies",
    "Location": "Main Warehouse",
    "Status": "DRAFT",
    "OrderDate": "2024-06-01",
    "Order": {
        "Lines": [
            {
                "ProductID": "prod-abc-123",
                "SKU": "WIDGET-001",
                "Name": "Blue Widget",
                "Quantity": 10,
                "Price": 12.50,
                "Tax": 0,
                "TaxRule": "Tax Exempt",
                "Total": 125.00,
            }
        ]
    },
}

PO_HEADER_RESPONSE = {
    "ID": "po-new-789",
    "Supplier": "Acme Supplies",
    "Status": "DRAFT",
}

PO_ORDER_RESPONSE = {
    "TaskID": "po-new-789",
    "Status": "DRAFT",
    "Lines": [
        {
            "ProductID": "prod-abc-123",
            "SKU": "WIDGET-001",
            "Name": "Blue Widget",
            "Quantity": 5,
            "Price": 12.50,
            "Total": 62.50,
        }
    ],
}
