"""Disk-cached HTTP GET with retry/backoff.

This is the union of the three near-duplicate `_cached_get` implementations:
  - 404 -> {}                       (from player_stats / squad)
  - HTTPError carries response=resp (from stats; lets callers read .status_code)
  - JSONDecodeError is retried       (from stats)
  - empty payloads ([] or {}) are not cached, so a transient empty response
    doesn't get frozen to disk forever (generalized from stats' list-only check)
"""
import json
import time
from pathlib import Path

import requests

from . import config


def cached_get(url: str, cache_path: Path) -> dict | list:
    if cache_path.exists():
        with cache_path.open(encoding="utf-8") as f:
            return json.load(f)

    cache_path.parent.mkdir(parents=True, exist_ok=True)

    last_exc: Exception | None = None
    payload: dict | list = {}
    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            resp = requests.get(url, headers=config.HEADERS, timeout=config.REQUEST_TIMEOUT)
            if resp.status_code >= 500 or resp.status_code == 429:
                raise requests.HTTPError(
                    f"{resp.status_code} server/rate-limit", response=resp
                )
            if resp.status_code == 404:
                return {}
            resp.raise_for_status()
            payload = resp.json()
            break
        except (requests.RequestException, json.JSONDecodeError) as e:
            last_exc = e
            if attempt == config.MAX_RETRIES:
                raise
            wait = config.RETRY_BACKOFF_BASE * (2 ** (attempt - 1))
            print(f"    retry {attempt}/{config.MAX_RETRIES} after {wait:.0f}s: {e}")
            time.sleep(wait)
    else:  # pragma: no cover - loop always breaks or raises
        raise last_exc  # type: ignore[misc]

    # Don't persist empty responses (unplayed-match stats come back as []).
    if payload not in ([], {}):
        with cache_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f)

    time.sleep(config.SLEEP_BETWEEN_CALLS)
    return payload