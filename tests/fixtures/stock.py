"""Stock availability mock API responses."""

STOCK_AVAILABILITY_LIST = {
    "ProductAvailabilityList": [
        {
            "ProductID": "prod-abc-123",
            "SKU": "WIDGET-001",
            "Location": "Main Warehouse",
            "OnHand": 100.0,
            "Available": 85.0,
            "Allocated": 15.0,
            "OnOrder": 50.0,
            "InTransit": 0.0,
            "Bin": "A1-01",
            "Batch": "BATCH-2024-001",
        },
        {
            "ProductID": "prod-def-456",
            "SKU": "GADGET-002",
            "Location": "Main Warehouse",
            "OnHand": 25.0,
            "Available": 20.0,
            "Allocated": 5.0,
            "OnOrder": 0.0,
            "InTransit": 10.0,
            "Bin": "B2-03",
            "Batch": "",
        },
    ],
    "Total": 2,
}

STOCK_SINGLE_SKU_MULTI_LOCATION = [
    {
        "ProductID": "prod-abc-123",
        "SKU": "WIDGET-001",
        "Location": "Main Warehouse",
        "OnHand": 100.0,
        "Available": 85.0,
        "Allocated": 15.0,
        "OnOrder": 50.0,
    },
    {
        "ProductID": "prod-abc-123",
        "SKU": "WIDGET-001",
        "Location": "Store",
        "OnHand": 20.0,
        "Available": 18.0,
        "Allocated": 2.0,
        "OnOrder": 0.0,
    },
]
