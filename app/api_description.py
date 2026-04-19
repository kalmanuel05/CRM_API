API_DESCRIPTION = """
## What this API does

Accept **messy customer rows** (JSON or CSV) and return **normalized fields**, **duplicate groups**,
**merge suggestions**, **warnings**, and **CRM-ready** tabular data.

---

## Authentication

Send your API key in either header:

- `X-API-Key: <your_key>`
- `Authorization: Bearer <your_key>`

---

## Pricing tiers (reference)

| Tier | Price (mo) | Req / month | Rate limit | Max records / request |
|------|------------|-------------|------------|------------------------|
| **free** | $0 | 500 | 5 / min | 50 |
| **starter** | $10 | 10,000 | 20 / min | 200 |
| **growth** | $30 | 100,000 | 60 / min | 500 |
| **pro** | $100 | 250,000 | 300 / min | 1,000 |

Monthly and per-minute limits are enforced per API key. Responses include a `usage` object with your tier and current month usage.

---

## Error responses

Failures return JSON with a stable **`error.code`**, a **human-readable `error.message`**, and **`error.request_id`**
(mirrored in the **`X-Request-Id`** response header when the request id middleware runs). Example:

```json
{
  "error": {
    "code": "BATCH_TOO_LARGE",
    "message": "Batch has 60 records; tier free allows at most 50 per request.",
    "request_id": "6f2c3b1e-8a4d-4c1e-9f0b-123456789abc"
  }
}
```

---

## Merge recommendations (exact meaning)

For each **duplicate group** (indices of rows that likely describe the same person), the API picks a single
**`keep_index`**: the row with the **highest “completeness” score** = count of non-empty normalized fields
on the cleaned record. Ties break toward the **lower index**.

**`merge_indices`** lists the other rows in that group. The API does **not** merge data in the database; it
recommends: **retain `keep_index` as the canonical row**, then **manually merge or discard** the rows in
`merge_indices` in your CRM or spreadsheet, using your own rules for field-level conflict resolution.

---

## Normalization rules

### Names
- Trim whitespace, collapse internal spaces.
- **Title-case** words (`string.capwords`) for person and place-style fields.
- If **full name** is provided without first/last, split on the first space into first + remainder.

### Email
- Trim, lowercase.
- Validated with **email-validator** (syntax; deliverability is **not** checked).
- Normalized form follows the library’s normalized output.

### Phone
- Parsed with **Google libphonenumber** (`phonenumbers`); default region from `default_phone_region` (e.g. `US`).
- Output **E.164** when the number is **valid** for its region; otherwise treated as invalid.

### Other text fields
- Trim; collapse whitespace; title-case where appropriate (address lines and notes are not title-cased).

---

## What counts as a duplicate?

Duplicate detection **merges indices into the same group** when any of these hold:

1. **Same normalized email** (after cleaning/validation).
2. **Same E.164 phone** (valid numbers only).
3. **Same normalized full name + same company** (company must be non-empty on both sides of the match),
   so common names without a company do not create huge false clusters.

Groups are **connected components**: if A matches B by email and B matches C by phone, A–B–C are one group.

---

## Export formats

`export_format` (JSON body or CSV form field): `generic` | `hubspot` | `salesforce` | `zoho`.

The JSON field **`crm_import_rows`** (and CSV downloads) contains one object per cleaned row using the mapping below.

### `generic` — example `crm_import_rows` row

```json
{
  "First Name": "Jane",
  "Last Name": "Doe",
  "Full Name": "Jane Doe",
  "Email": "jane@example.com",
  "Phone": "+12025550100",
  "Company": "Acme Inc",
  "Title": "VP Sales",
  "Address": "1 Main St",
  "City": "Austin",
  "State": "TX",
  "ZIP": "78701",
  "Country": "US",
  "Notes": "VIP"
}
```

### `hubspot` — example `crm_import_rows` row

```json
{
  "First Name": "Jane",
  "Last Name": "Doe",
  "Email": "jane@example.com",
  "Phone Number": "+12025550100",
  "Company": "Acme Inc",
  "Job Title": "VP Sales",
  "Street Address": "1 Main St",
  "City": "Austin",
  "State/Region": "TX",
  "Postal Code": "78701",
  "Country/Region": "US"
}
```

### `salesforce` — example `crm_import_rows` row

```json
{
  "FirstName": "Jane",
  "LastName": "Doe",
  "Email": "jane@example.com",
  "Phone": "+12025550100",
  "Company": "Acme Inc",
  "Title": "VP Sales",
  "Street": "1 Main St",
  "City": "Austin",
  "State": "TX",
  "PostalCode": "78701",
  "Country": "US",
  "Description": "VIP"
}
```

### `zoho` — example `crm_import_rows` row

```json
{
  "First Name": "Jane",
  "Last Name": "Doe",
  "Full Name": "Jane Doe",
  "Email": "jane@example.com",
  "Phone": "+12025550100",
  "Account Name": "Acme Inc",
  "Title": "VP Sales",
  "Mailing Street": "1 Main St",
  "Mailing City": "Austin",
  "Mailing State": "TX",
  "Mailing Zip": "78701",
  "Mailing Country": "US",
  "Description": "VIP"
}
```

---

## Size limits

- **Batch**: maximum rows per request is set by your **tier** (see table above).
- **JSON body**: rejected with `PAYLOAD_TOO_LARGE` if the request body exceeds the configured size limit.
- **CSV upload**: rejected with `CSV_TOO_LARGE` if the upload exceeds the configured file size limit.

---

## Example: duplicates (response excerpt)

Two rows normalize to the same email; they appear in one duplicate group and get a merge recommendation.

```json
{
  "duplicate_groups": [[0, 1]],
  "merge_recommendations": [
    {
      "duplicate_group_index": 0,
      "member_indices": [0, 1],
      "keep_index": 1,
      "merge_indices": [0],
      "rationale": "Keep the row with the most populated normalized fields; merge or discard the others after reviewing source data."
    }
  ]
}
```

---

## Example: warnings (response excerpt)

Invalid email/phone values produce warnings while still returning cleaned rows where possible.

```json
{
  "warnings": [
    {
      "record_index": 0,
      "field": "email",
      "severity": "invalid",
      "message": "Email is present but could not be validated."
    },
    {
      "record_index": 0,
      "field": "phone",
      "severity": "invalid",
      "message": "Phone is present but invalid or not parseable for the given region."
    }
  ]
}
```

---

## CSV upload (multipart)

`POST /v1/clean/csv` with `multipart/form-data`:

- **`file`**: UTF-8 CSV with a header row (required).
- **`default_phone_region`**: form field, default `US`.
- **`export_format`**: form field: `generic` | `hubspot` | `salesforce` | `zoho`.
- **`download`**: query `true` to receive a CSV file of `crm_import_rows` instead of JSON.

Minimal example (conceptual):

```
POST /v1/clean/csv
Content-Type: multipart/form-data; boundary=----abc

------abc
Content-Disposition: form-data; name="file"; filename="leads.csv"
Content-Type: text/csv

email,company
jane@example.com,Acme Inc
------abc
Content-Disposition: form-data; name="default_phone_region"

US
------abc
Content-Disposition: form-data; name="export_format"

hubspot
------abc--
```

---

## Sample JSON request (`POST /v1/clean`)

```json
{
  "default_phone_region": "US",
  "export_format": "hubspot",
  "records": [
    {
      "first_name": "  jane  ",
      "last_name": "DOE",
      "email": "Jane.Doe+tag@Example.COM",
      "phone": "+12025550173",
      "company": "Acme Inc"
    }
  ]
}
```

## Sample JSON response (shape)

```json
{
  "cleaned_records": [ { "first_name": "Jane", "last_name": "Doe", "email": "jane.doe@example.com", "phone_e164": "+12025550173" } ],
  "warnings": [ { "record_index": 0, "field": "phone", "severity": "missing", "message": "..." } ],
  "duplicate_groups": [ [0, 1] ],
  "merge_recommendations": [ { "duplicate_group_index": 0, "member_indices": [0,1], "keep_index": 0, "merge_indices": [1], "rationale": "..." } ],
  "summary": { "record_count": 2, "warning_count": 1, "warnings_by_field": {}, "warnings_by_severity": {}, "duplicate_group_count": 1, "records_in_duplicate_groups": 2, "avg_non_empty_fields_per_record": 6.5 },
  "crm_import_rows": [ { "First Name": "Jane" } ],
  "usage": { "request_id": "uuid", "tier": "free", "monthly_quota": 500, "monthly_used": 12, "rate_limit_per_minute": 5, "max_batch_records": 50 }
}
```

---

## Common use cases

- **Inbound spreadsheet cleanup** before HubSpot / Salesforce / Zoho import.
- **Lead list hygiene** after events or scraped forms.
- **Deduplication passes** using email/phone/name+company signals.

---

## Endpoints

- `GET /health` — no auth.
- `POST /v1/clean` — JSON body; returns full structured response.
- `POST /v1/clean/csv` — `multipart/form-data` with field `file` (CSV); optional `download=1` query returns **CSV file** (`text/csv`) of cleaned rows.
"""
