"""
WHO Global Health Observatory (GHO) OData API client
=======================================================
Docs: https://www.who.int/data/gho/info/gho-odata-api
Base URL: https://ghoapi.azureedge.net/api/
No API key required.

This module knows how to:
  1. Fetch raw indicator data for a given WHO indicator code
  2. Normalize it into the shared schema (see data_sources/schema.py)

It does NOT know about the indicator registry — callers pass in whatever
indicator_id/source_code pair they want, which keeps this file reusable
for any current or future WHO indicator without modification.
"""

from __future__ import annotations

import functools

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://ghoapi.azureedge.net/api"
REQUEST_TIMEOUT = (10, 45)  # connect timeout, read timeout in seconds


def _build_session() -> requests.Session:
    """Create a GET-only session that retries transient WHO gateway failures."""
    retry = Retry(
        total=4,
        connect=4,
        read=4,
        status=4,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


HTTP = _build_session()

# WHO's "both sexes" / "total" dimension codes. We filter to these so that
# indicators with sex/age/wealth breakdowns collapse to one row per
# country-year, matching the normalized schema. If an indicator doesn't
# use these dimensions at all, the filter simply has no effect.
PREFERRED_DIM1 = "SEX_BTSX"
PREFERRED_DIM3 = "WEALTHQUINTILE_TOTL"


@functools.lru_cache(maxsize=1)
def get_country_lookup() -> dict:
    """
    Fetch and cache the WHO COUNTRY dimension (ISO3 code -> country name).
    Cached for the lifetime of the process since this rarely changes.
    Public: also used by app.py to serve GET /api/countries.
    """
    url = f"{BASE_URL}/DIMENSION/COUNTRY/DimensionValues"
    resp = HTTP.get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    values = resp.json().get("value", [])
    return {row["Code"]: row["Title"] for row in values}


def fetch_indicator(source_code: str, indicator_id: str) -> pd.DataFrame:
    """
    Fetch all data for a WHO indicator code and normalize it.

    Parameters:
        source_code:  the WHO indicator code, e.g. "WHOSIS_000001"
        indicator_id: the internal registry id to tag rows with,
                       e.g. "life_expectancy"

    Returns a DataFrame with columns matching schema.NORMALIZED_COLUMNS.
    """
    url = f"{BASE_URL}/{source_code}"
    resp = HTTP.get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    rows = resp.json().get("value", [])

    if not rows:
        return pd.DataFrame(columns=["country_code", "country_name", "year", "indicator_id", "value", "source"])

    df = pd.DataFrame(rows)

    # Only keep country-level rows (WHO also returns region/global aggregates
    # under SpatialDimType == "REGION" or "WORLD", which we don't want mixed
    # in with per-country comparisons).
    df = df[df["SpatialDimType"] == "COUNTRY"]

    # Collapse disaggregated indicators (sex/wealth breakdowns) down to the
    # "total" row where that dimension exists on this indicator at all.
    if "Dim1" in df.columns and df["Dim1"].notna().any():
        has_total = df["Dim1"].isin([PREFERRED_DIM1, None])
        if has_total.any():
            df = df[df["Dim1"].isna() | (df["Dim1"] == PREFERRED_DIM1)]
    if "Dim3" in df.columns and df["Dim3"].notna().any():
        has_total = df["Dim3"].isin([PREFERRED_DIM3, None])
        if has_total.any():
            df = df[df["Dim3"].isna() | (df["Dim3"] == PREFERRED_DIM3)]

    country_names = get_country_lookup()

    out = pd.DataFrame({
        "country_code": df["SpatialDim"],
        "country_name": df["SpatialDim"].map(country_names).fillna(df["SpatialDim"]),
        "year": pd.to_numeric(df["TimeDim"], errors="coerce"),
        "indicator_id": indicator_id,
        "value": pd.to_numeric(df["NumericValue"], errors="coerce"),
        "source": "WHO",
    })

    out = out.dropna(subset=["year", "value"])
    out["year"] = out["year"].astype(int)

    # If duplicates remain (e.g. multiple data sources for one country-year),
    # keep the most recently reported one isn't tracked here, so just average.
    out = out.groupby(["country_code", "country_name", "year", "indicator_id", "source"], as_index=False)["value"].mean()

    return out.reset_index(drop=True)
