"""Sale mock API responses."""

SALE_LIST_RESPONSE = {
    "SaleList": [
        {
            "Order": "SO-001",
            "SaleOrderNumber": "SON-001",
            "Customer": "Test Customer",
            "Location": "Main Warehouse",
            "Status": "DRAFT",
            "Total": 100.00,
            "OrderDate": "2024-06-01",
        },
        {
            "Order": "SO-002",
            "SaleOrderNumber": "SON-002",
            "Customer": "Another Customer",
            "Location": "Store",
            "Status": "AUTHORISED",
            "Total": 250.00,
            "OrderDate": "2024-06-02",
        },
    ],
    "Total": 2,
}

SALE_SINGLE = {
    "ID": "sale-abc-123",
    "Customer": "Test Customer",
    "Location": "Main Warehouse",
    "Status": "DRAFT",
    "Quote": {
        "Status": "DRAFT",
        "Lines": [
            {
                "ProductID": "prod-abc-123",
                "SKU": "WIDGET-001",
                "Name": "Blue Widget",
                "Quantity": 2,
                "Price": 29.99,
                "Tax": 0,
                "TaxRule": "Tax Exempt",
                "Total": 59.98,
            }
        ],
    },
}

SALE_HEADER_RESPONSE = {
    "ID": "sale-new-789",
    "Customer": "New Customer",
    "Status": "DRAFT",
}

SALE_ORDER_RESPONSE = {
    "SaleID": "sale-new-789",
    "Status": "DRAFT",
    "Lines": [
        {
            "ProductID": "prod-abc-123",
            "SKU": "WIDGET-001",
            "Name": "Blue Widget",
            "Quantity": 1,
            "Price": 29.99,
            "Total": 29.99,
        }
    ],
}
