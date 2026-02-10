"""Supplier mock API responses."""

SUPPLIER_SINGLE = {
    "ID": "sup-abc-123",
    "Name": "Acme Supplies",
    "ContactPerson": "John Doe",
    "Phone": "555-0100",
    "Email": "john@acme-supplies.com",
    "Currency": "USD",
    "TaxRule": "Tax Exempt",
    "PaymentTerm": "Net 30",
}

SUPPLIER_LIST_RESPONSE = {
    "SupplierList": [
        {
            "ID": "sup-abc-123",
            "Name": "Acme Supplies",
            "ContactPerson": "John Doe",
            "Phone": "555-0100",
        },
        {
            "ID": "sup-def-456",
            "Name": "Global Parts Inc",
            "ContactPerson": "Jane Smith",
            "Phone": "555-0200",
        },
    ],
    "Total": 2,
}

SUPPLIER_EMPTY_LIST = {
    "SupplierList": [],
    "Total": 0,
}

SUPPLIER_SAVE_RESPONSE = {
    "ID": "sup-new-789",
    "Name": "New Supplier",
    "ContactPerson": "Bob Wilson",
}

SUPPLIER_UPDATE_RESPONSE = {
    "ID": "sup-abc-123",
    "Name": "Acme Supplies Updated",
    "ContactPerson": "John Doe Jr",
}
