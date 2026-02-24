"""Common mock API responses: Me, health check, errors."""

ME_RESPONSE = {
    "Company": "Acme Corp",
    "Currency": "USD",
    "TimeZone": "America/New_York",
    "DefaultLocation": "Main Warehouse",
    "LockDate": "2024-01-01",
    "TaxRule": "Tax Exempt",
}

HEALTH_CHECK_RESPONSE = {
    "Products": [{"SKU": "HEALTH-CHK", "Name": "Health Check Product"}],
    "Total": 1,
}

ERROR_AUTH_401 = "Unauthorized: Invalid account ID or API key"

ERROR_BAD_REQUEST_400 = "Bad Request: Missing required field"
