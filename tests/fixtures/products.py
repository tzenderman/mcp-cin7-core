"""Product mock API responses."""

PRODUCT_SINGLE = {
    "ID": "prod-abc-123",
    "SKU": "WIDGET-001",
    "Name": "Blue Widget",
    "Category": "Widgets",
    "Brand": "Acme",
    "Status": "Active",
    "Type": "Stock",
    "UOM": "Item",
    "CostingMethod": "FIFO",
    "DefaultLocation": "Main Warehouse",
    "PriceTier1": 29.99,
    "PurchasePrice": 12.50,
    "Barcode": "123456789012",
}

PRODUCT_LIST_RESPONSE = {
    "Products": [
        {
            "ID": "prod-abc-123",
            "SKU": "WIDGET-001",
            "Name": "Blue Widget",
            "Category": "Widgets",
            "Brand": "Acme",
            "PriceTier1": 29.99,
        },
        {
            "ID": "prod-def-456",
            "SKU": "GADGET-002",
            "Name": "Red Gadget",
            "Category": "Gadgets",
            "Brand": "Acme",
            "PriceTier1": 49.99,
        },
    ],
    "Total": 2,
}

PRODUCT_EMPTY_LIST = {
    "Products": [],
    "Total": 0,
}

PRODUCT_SAVE_RESPONSE = {
    "ID": "prod-new-789",
    "SKU": "NEWPROD-001",
    "Name": "New Product",
    "Category": "Test",
    "Status": "Active",
}

PRODUCT_UPDATE_RESPONSE = {
    "ID": "prod-abc-123",
    "SKU": "WIDGET-001",
    "Name": "Updated Widget",
    "Category": "Widgets",
    "Status": "Active",
}

PRODUCT_SUPPLIERS_RESPONSE = {
    "Products": [
        {
            "ProductID": "prod-abc-123",
            "Suppliers": [
                {
                    "SupplierID": "sup-111",
                    "SupplierName": "Widget Supplier Co",
                    "SupplierInventoryCode": "WS-001",
                    "Cost": 12.50,
                }
            ],
        }
    ]
}

PRODUCT_SUPPLIERS_UPDATE_RESPONSE = {
    "Products": [
        {
            "ProductID": "prod-abc-123",
            "Suppliers": [
                {
                    "SupplierID": "sup-222",
                    "SupplierName": "New Supplier",
                    "Cost": 10.00,
                }
            ],
        }
    ]
}
