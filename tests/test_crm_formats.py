from __future__ import annotations

from app.crm_formats import format_rows
from app.models import CleanedRecord

_sample = CleanedRecord(
    first_name="Jane",
    last_name="Doe",
    full_name="Jane Doe",
    email="jane@example.com",
    phone_e164="+12025550100",
    company="Acme",
    title="VP Sales",
    address="1 Main",
    city="Austin",
    state="TX",
    zip="78701",
    country="US",
    notes="VIP",
)


def test_export_format_generic_mapping() -> None:
    rows, keys = format_rows([_sample], "generic")
    assert keys[0] == "First Name"
    assert rows[0]["Email"] == "jane@example.com"
    assert rows[0]["ZIP"] == "78701"


def test_export_format_hubspot_mapping() -> None:
    rows, keys = format_rows([_sample], "hubspot")
    assert "Phone Number" in keys
    assert rows[0]["Job Title"] == "VP Sales"
    assert rows[0]["Postal Code"] == "78701"


def test_export_format_salesforce_mapping() -> None:
    rows, keys = format_rows([_sample], "salesforce")
    assert "FirstName" in keys
    assert rows[0]["PostalCode"] == "78701"
    assert rows[0]["Description"] == "VIP"


def test_export_format_zoho_mapping() -> None:
    rows, keys = format_rows([_sample], "zoho")
    assert "Account Name" in keys
    assert rows[0]["Mailing Zip"] == "78701"
    assert rows[0]["Full Name"] == "Jane Doe"
