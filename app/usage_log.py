from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any

from app.tiers import TierId

_file_lock: Any = None


def _lock():
    global _file_lock
    if _file_lock is None:
        from threading import Lock

        _file_lock = Lock()
    return _file_lock


def log_usage(
    *,
    log_path: str,
    request_id: str,
    api_key_fingerprint: str,
    tier: TierId,
    endpoint: str,
    method: str,
    status_code: int,
    record_count: int | None,
    duration_ms: float,
    error: str | None = None,
) -> None:
    row = {
        "ts": time.time(),
        "request_id": request_id,
        "key_fp": api_key_fingerprint,
        "tier": tier.value,
        "endpoint": endpoint,
        "method": method,
        "status_code": status_code,
        "record_count": record_count,
        "duration_ms": round(duration_ms, 3),
        "error": error,
    }
    line = json.dumps(row, ensure_ascii=False) + "\n"
    try:
        os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
    except OSError:
        pass
    with _lock():
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line)


def new_request_id() -> str:
    return str(uuid.uuid4())


def fingerprint_key(api_key: str) -> str:
    if len(api_key) <= 8:
        return "***"
    return f"{api_key[:4]}…{api_key[-4:]}"
