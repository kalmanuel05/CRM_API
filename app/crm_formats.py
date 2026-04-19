from __future__ import annotations

from app.models import CleanedRecord, ExportFormat


def _val(x: str | None) -> str:
    return x if x else ""


def row_generic(c: CleanedRecord) -> dict[str, str]:
    return {
        "First Name": _val(c.first_name),
        "Last Name": _val(c.last_name),
        "Full Name": _val(c.full_name),
        "Email": _val(c.email),
        "Phone": _val(c.phone_e164),
        "Company": _val(c.company),
        "Title": _val(c.title),
        "Address": _val(c.address),
        "City": _val(c.city),
        "State": _val(c.state),
        "ZIP": _val(c.zip),
        "Country": _val(c.country),
        "Notes": _val(c.notes),
    }


def row_hubspot(c: CleanedRecord) -> dict[str, str]:
    return {
        "First Name": _val(c.first_name),
        "Last Name": _val(c.last_name),
        "Email": _val(c.email),
        "Phone Number": _val(c.phone_e164),
        "Company": _val(c.company),
        "Job Title": _val(c.title),
        "Street Address": _val(c.address),
        "City": _val(c.city),
        "State/Region": _val(c.state),
        "Postal Code": _val(c.zip),
        "Country/Region": _val(c.country),
    }


def row_salesforce(c: CleanedRecord) -> dict[str, str]:
    return {
        "FirstName": _val(c.first_name),
        "LastName": _val(c.last_name),
        "Email": _val(c.email),
        "Phone": _val(c.phone_e164),
        "Company": _val(c.company),
        "Title": _val(c.title),
        "Street": _val(c.address),
        "City": _val(c.city),
        "State": _val(c.state),
        "PostalCode": _val(c.zip),
        "Country": _val(c.country),
        "Description": _val(c.notes),
    }


def row_zoho(c: CleanedRecord) -> dict[str, str]:
    return {
        "First Name": _val(c.first_name),
        "Last Name": _val(c.last_name),
        "Full Name": _val(c.full_name),
        "Email": _val(c.email),
        "Phone": _val(c.phone_e164),
        "Account Name": _val(c.company),
        "Title": _val(c.title),
        "Mailing Street": _val(c.address),
        "Mailing City": _val(c.city),
        "Mailing State": _val(c.state),
        "Mailing Zip": _val(c.zip),
        "Mailing Country": _val(c.country),
        "Description": _val(c.notes),
    }


GENERIC_FIELDS = list(row_generic(CleanedRecord()).keys())  # type: ignore[misc]

HUBSPOT_FIELDS = [
    "First Name",
    "Last Name",
    "Email",
    "Phone Number",
    "Company",
    "Job Title",
    "Street Address",
    "City",
    "State/Region",
    "Postal Code",
    "Country/Region",
]

SALESFORCE_FIELDS = [
    "FirstName",
    "LastName",
    "Email",
    "Phone",
    "Company",
    "Title",
    "Street",
    "City",
    "State",
    "PostalCode",
    "Country",
    "Description",
]

ZOHO_FIELDS = [
    "First Name",
    "Last Name",
    "Full Name",
    "Email",
    "Phone",
    "Account Name",
    "Title",
    "Mailing Street",
    "Mailing City",
    "Mailing State",
    "Mailing Zip",
    "Mailing Country",
    "Description",
]


def format_rows(cleaned: list[CleanedRecord], fmt: ExportFormat) -> tuple[list[dict[str, str]], list[str]]:
    if fmt == "hubspot":
        rows = [row_hubspot(c) for c in cleaned]
        keys = HUBSPOT_FIELDS
    elif fmt == "salesforce":
        rows = [row_salesforce(c) for c in cleaned]
        keys = SALESFORCE_FIELDS
    elif fmt == "zoho":
        rows = [row_zoho(c) for c in cleaned]
        keys = ZOHO_FIELDS
    else:
        rows = [row_generic(c) for c in cleaned]
        keys = GENERIC_FIELDS
    return rows, keys
