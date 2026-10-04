"""
Source dispatcher + in-memory cache
======================================
This is the one place that knows "WHO indicators go to who_client, OWID
indicators go to owid_client." Routes and analysis code never import the
source clients directly — they call get_indicator_data(indicator_id), which
looks up the registry entry and dispatches automatically.

This is also where results are cached. Both upstream APIs are free public
services without generous rate-limit guarantees, so repeated requests for
the same indicator (e.g. multiple users loading the same chart) are served
from memory instead of re-fetching every time.
"""

from __future__ import annotations

import threading
import time

import pandas as pd

from indicators import get_indicator
from data_sources import who_client, owid_client

CACHE_TTL_SECONDS = 60 * 60  # 1 hour

_cache: dict[str, tuple[float, pd.DataFrame]] = {}
_cache_lock = threading.Lock()

_SOURCE_CLIENTS = {
    "WHO": who_client.fetch_indicator,
    "OWID": owid_client.fetch_indicator,
}


def get_indicator_data(indicator_id: str) -> pd.DataFrame:
    """
    Return normalized data for one indicator, using the cache when possible.
    Raises ValueError if indicator_id isn't in the registry, or if its
    "source" has no registered client.
    """
    entry = get_indicator(indicator_id)
    if entry is None:
        raise ValueError(f"Unknown indicator id: '{indicator_id}'")

    with _cache_lock:
        cached = _cache.get(indicator_id)
        if cached is not None:
            fetched_at, df = cached
            if time.time() - fetched_at < CACHE_TTL_SECONDS:
                return df.copy()

    fetch_fn = _SOURCE_CLIENTS.get(entry["source"])
    if fetch_fn is None:
        raise ValueError(f"No client registered for source '{entry['source']}'")

    df = fetch_fn(entry["source_code"], indicator_id)

    with _cache_lock:
        _cache[indicator_id] = (time.time(), df)

    return df.copy()


def clear_cache() -> None:
    """Mainly useful for tests / manual refresh."""
    with _cache_lock:
        _cache.clear()
