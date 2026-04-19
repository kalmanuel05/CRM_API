from __future__ import annotations

import json
import os
import traceback
from collections import deque
from threading import Lock
from typing import Any

_file_lock: Any = None
_ring: deque[dict[str, Any]] = deque(maxlen=100)
_ring_lock = Lock()


def _lock_file():
    global _file_lock
    if _file_lock is None:
        _file_lock = Lock()
    return _file_lock


def error_log_path() -> str:
    return os.environ.get("CRM_ERROR_LOG_PATH", "logs/errors.jsonl")


def log_unhandled_exception(*, request_id: str, path: str, exc: BaseException) -> None:
    row = {
        "kind": "unhandled_exception",
        "request_id": request_id,
        "path": path,
        "error_type": type(exc).__name__,
        "message": str(exc),
        "traceback": traceback.format_exc(),
    }
    line = json.dumps(row, ensure_ascii=False) + "\n"
    with _ring_lock:
        _ring.appendleft(
            {
                "request_id": request_id,
                "path": path,
                "error_type": type(exc).__name__,
                "message": str(exc),
            }
        )
    path_log = error_log_path()
    try:
        os.makedirs(os.path.dirname(path_log) or ".", exist_ok=True)
    except OSError:
        pass
    with _lock_file():
        try:
            with open(path_log, "a", encoding="utf-8") as f:
                f.write(line)
        except OSError:
            pass


def recent_errors_snapshot(limit: int = 50) -> list[dict[str, Any]]:
    with _ring_lock:
        return list(_ring)[:limit]
