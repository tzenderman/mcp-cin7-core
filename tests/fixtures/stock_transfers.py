"""Stock transfer mock API responses."""

STOCK_TRANSFER_LIST_RESPONSE = {
    "StockTransferList": [
        {
            "TaskID": "st-task-001",
            "FromLocation": "Main Warehouse",
            "ToLocation": "Store",
            "Status": "COMPLETED",
            "TransferDate": "2024-06-01",
            "Note": "Monthly restock",
        },
        {
            "TaskID": "st-task-002",
            "FromLocation": "Store",
            "ToLocation": "Main Warehouse",
            "Status": "DRAFT",
            "TransferDate": "2024-06-15",
            "Note": "Return excess stock",
        },
    ],
    "Total": 2,
}

STOCK_TRANSFER_SINGLE = {
    "TaskID": "st-task-001",
    "FromLocation": "Main Warehouse",
    "ToLocation": "Store",
    "Status": "COMPLETED",
    "TransferDate": "2024-06-01",
    "Lines": [
        {
            "ProductID": "prod-abc-123",
            "SKU": "WIDGET-001",
            "Name": "Blue Widget",
            "Quantity": 10.0,
        }
    ],
}

STOCK_TRANSFER_NOT_FOUND_400 = [
    {"Exception": "Stock transfer 'st-nonexistent' not found"}
]
