"""
Our World in Data (OWID) Grapher CSV client
==============================================
OWID doesn't expose a stable public REST "Indicators" search API for
arbitrary HTTP use (their documented Charts/Tables/Indicators/Search APIs
are oriented around their internal catalog tooling). What IS reliably
public and CORS-open is the per-chart data export used by every grapher
page on their site:

    https://ourworldindata.org/grapher/<slug>.csv
    https://ourworldindata.org/grapher/<slug>.metadata.json

Verified live (2026-10-04): both endpoints return 200 with
`access-control-allow-origin: *`, no API key required.

This module fetches that CSV and normalizes it into the shared schema.
Every OWID CSV follows the same shape: Entity, Code, Year, <value column>
(occasionally more columns, e.g. a region breakdown — we only use the
first numeric data column).
"""

from __future__ import annotations

import io

import pandas as pd
import requests

GRAPHER_BASE_URL = "https://ourworldindata.org/grapher"
REQUEST_TIMEOUT = 20  # seconds


def fetch_indicator(source_code: str, indicator_id: str) -> pd.DataFrame:
    """
    Fetch all data for an OWID grapher slug and normalize it.

    Parameters:
        source_code:  the OWID grapher slug, e.g. "life-expectancy"
        indicator_id: the internal registry id to tag rows with,
                       e.g. "owid_life_expectancy"

    Returns a DataFrame with columns matching schema.NORMALIZED_COLUMNS.
    """
    url = f"{GRAPHER_BASE_URL}/{source_code}.csv"
    resp = requests.get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()

    raw = pd.read_csv(io.StringIO(resp.text))

    # Expected columns: Entity, Code, Year|Day, <value...>. Some slugs use
    # "Day" instead of "Year" (daily time series, e.g. COVID data). We
    # derive a "year" column from "Day" in that case rather than rejecting
    # the slug outright, since daily OWID series are common.
    if "Year" in raw.columns:
        time_col = "Year"
    elif "Day" in raw.columns:
        time_col = "Day"
    else:
        raise ValueError(
            f"OWID slug '{source_code}' has no recognized time column "
            f"(columns found: {list(raw.columns)}). Pick a different slug."
        )

    # Drop rows with no ISO3 code (OWID includes aggregates like "World",
    # "Africa", income groups, etc. with blank Code) to keep this consistent
    # with the WHO client, which is country-only.
    raw = raw[raw["Code"].notna() & (raw["Code"].str.len() == 3)]

    # The value column is whichever one isn't Entity/Code/Year/Day
    value_cols = [c for c in raw.columns if c not in ("Entity", "Code", "Year", "Day")]
    if not value_cols:
        raise ValueError(f"OWID slug '{source_code}' has no value column.")
    value_col = value_cols[0]

    if time_col == "Year":
        year = pd.to_numeric(raw["Year"], errors="coerce")
    else:
        year = pd.to_datetime(raw["Day"], errors="coerce").dt.year

    out = pd.DataFrame({
        "country_code": raw["Code"],
        "country_name": raw["Entity"],
        "year": year,
        "indicator_id": indicator_id,
        "value": pd.to_numeric(raw[value_col], errors="coerce"),
        "source": "OWID",
    })

    out = out.dropna(subset=["year", "value"])
    out["year"] = out["year"].astype(int)

    if time_col == "Day":
        # Daily series collapsed to yearly: for cumulative metrics (like
        # cumulative vaccinations), the most meaningful single value per
        # country-year is the latest reading in that year. Attach the
        # original day so sorting (and therefore "last") is chronological.
        out["_day"] = pd.to_datetime(raw.loc[out.index, "Day"], errors="coerce")
        out = out.sort_values(["country_code", "year", "_day"])
        out = out.drop(columns="_day")
        out = out.groupby(["country_code", "country_name", "year", "indicator_id", "source"], as_index=False).last()

    return out.reset_index(drop=True)
