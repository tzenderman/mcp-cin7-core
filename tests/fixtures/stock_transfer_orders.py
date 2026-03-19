"""Stock transfer order mock API responses."""

STO_SINGLE = {
    "TaskID": "sto-task-001",
    "FromLocation": "Main Warehouse",
    "ToLocation": "Store Front",
    "Status": "DRAFT",
    "TransferDate": "2026-03-05",
    "Lines": [
        {
            "ProductID": "prod-abc-123",
            "SKU": "WIDGET-001",
            "ProductName": "Blue Widget",
            "TransferQuantity": 10.0,
            "QuantityOnHand": 100.0,
            "QuantityAvailable": 85.0,
        }
    ],
}

STO_CREATE_RESPONSE = {
    "TaskID": "sto-new-789",
    "FromLocation": "Main Warehouse",
    "ToLocation": "Store Front",
    "Status": "DRAFT",
    "TransferDate": "2026-03-05",
    "Lines": [
        {
            "ProductID": "prod-abc-123",
            "SKU": "WIDGET-001",
            "ProductName": "Blue Widget",
            "TransferQuantity": 5.0,
        }
    ],
}

STO_NOT_FOUND_400 = [{"Exception": "Stock transfer order 'sto-nonexistent' not found"}]
