"""
Shared normalized schema
==========================
Every source client (WHO, OWID, future sources) returns a pandas DataFrame
with exactly these columns, regardless of how different the raw API/CSV
format is. This is what lets the rest of the app (analysis, API routes,
frontend) stay source-agnostic.

Columns:
    country_code   str   — ISO3 country code (e.g. "USA")
    country_name   str   — human-readable country/entity name
    year           int   — calendar year
    indicator_id   str   — the internal id from indicators.py
    value          float — the numeric value
    source         str   — "WHO" or "OWID", for attribution
"""

NORMALIZED_COLUMNS = ["country_code", "country_name", "year", "indicator_id", "value", "source"]
