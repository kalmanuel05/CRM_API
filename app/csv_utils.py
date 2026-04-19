from __future__ import annotations

import csv
import io
from typing import Any


def dicts_from_csv(content: bytes | str, encoding: str = "utf-8") -> list[dict[str, Any]]:
    text = content.decode(encoding) if isinstance(content, bytes) else content
    buf = io.StringIO(text)
    reader = csv.DictReader(buf)
    rows: list[dict[str, Any]] = []
    for row in reader:
        if row is None:
            continue
        cleaned = {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items() if k is not None}
        if any(v not in (None, "") for v in cleaned.values()):
            rows.append(cleaned)
    return rows


def csv_bytes_from_dicts(rows: list[dict[str, str]], fieldnames: list[str]) -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, delimiter=",")
    writer.writeheader()
    for r in rows:
        writer.writerow({k: r.get(k, "") for k in fieldnames})
    return buf.getvalue().encode("utf-8")
