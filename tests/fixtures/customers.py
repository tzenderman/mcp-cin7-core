"""Customer mock API responses."""

CUSTOMER_LIST_RESPONSE = {
    "CustomerList": [
        {
            "ID": "cust-abc-123",
            "Name": "Acme Corp",
            "Email": "orders@acme.com",
            "Phone": "555-0100",
            "Status": "Active",
            "Currency": "USD",
        },
        {
            "ID": "cust-def-456",
            "Name": "Beta Ltd",
            "Email": "buy@beta.com",
            "Phone": "555-0200",
            "Status": "Active",
            "Currency": "AUD",
        },
    ],
    "Total": 2,
}

CUSTOMER_EMPTY_LIST = {
    "CustomerList": [],
    "Total": 0,
}

CUSTOMER_SINGLE = {
    "ID": "cust-abc-123",
    "Name": "Acme Corp",
    "Email": "orders@acme.com",
    "Phone": "555-0100",
    "Status": "Active",
    "Currency": "USD",
    "PaymentTerm": "Net 30",
    "TaxRule": "Tax Exempt",
    "AccountReceivable": "120",
}

CUSTOMER_SAVE_RESPONSE = {
    "ID": "cust-new-789",
    "Name": "New Customer",
    "Email": "contact@new.com",
}

CUSTOMER_UPDATE_RESPONSE = {
    "ID": "cust-abc-123",
    "Name": "Acme Corp Updated",
    "Email": "new@acme.com",
}
