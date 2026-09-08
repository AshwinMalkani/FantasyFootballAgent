"""Tiny TTL cache: in-memory first, JSON files on disk second."""
import json
import re
import time
from pathlib import Path
from typing import Any, Callable

from .config import settings

_MEM: dict[str, tuple[float, Any]] = {}


def _path(key: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", key)
    return settings.cache_dir / f"{safe}.json"


def cached(key: str, ttl_seconds: float, fetch: Callable[[], Any]) -> Any:
    now = time.time()
    hit = _MEM.get(key)
    if hit and hit[0] > now:
        return hit[1]

    p = _path(key)
    if p.exists():
        try:
            raw = json.loads(p.read_text())
            if raw.get("expires", 0) > now:
                _MEM[key] = (raw["expires"], raw["value"])
                return raw["value"]
        except (ValueError, KeyError):
            pass

    value = fetch()
    expires = now + ttl_seconds
    _MEM[key] = (expires, value)
    try:
        settings.cache_dir.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"expires": expires, "value": value}))
    except (OSError, TypeError):
        pass
    return value


def clear_all() -> int:
    _MEM.clear()
    n = 0
    if settings.cache_dir.exists():
        for f in settings.cache_dir.glob("*.json"):
            f.unlink()
            n += 1
    return n


def clear_prefix(prefix: str) -> None:
    for k in [k for k in _MEM if k.startswith(prefix)]:
        del _MEM[k]
    if settings.cache_dir.exists():
        for f in settings.cache_dir.glob(f"{re.sub(r'[^A-Za-z0-9_.-]+', '_', prefix)}*.json"):
            f.unlink()
