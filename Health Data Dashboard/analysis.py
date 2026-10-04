"""
Comparative / statistical analysis helpers
=============================================
Pure functions over normalized DataFrames (see data_sources/schema.py).
Nothing here is aware of WHO/OWID specifics — it only deals in
country_code, year, indicator_id, value. This keeps analysis logic
reusable no matter how many sources get added later.
"""

from __future__ import annotations

import pandas as pd


def filter_data(
    df: pd.DataFrame,
    countries: list[str] | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
) -> pd.DataFrame:
    """Apply optional country/year filters to a normalized indicator DataFrame."""
    out = df
    if countries:
        out = out[out["country_code"].isin(countries)]
    if year_min is not None:
        out = out[out["year"] >= year_min]
    if year_max is not None:
        out = out[out["year"] <= year_max]
    return out.reset_index(drop=True)


def rankings(df: pd.DataFrame, year: int, top_n: int = 10, ascending: bool = False) -> pd.DataFrame:
    """
    Rank countries by indicator value for a specific year.
    Returns top_n rows sorted by value (descending by default).
    """
    year_df = df[df["year"] == year].copy()
    year_df = year_df.sort_values("value", ascending=ascending)
    return year_df.head(top_n).reset_index(drop=True)


def year_over_year_change(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute year-over-year absolute and percent change per country.
    Returns the input DataFrame with two extra columns:
        change        — value - previous year's value
        pct_change    — percent change vs previous year
    """
    out = df.sort_values(["country_code", "year"]).copy()
    out["change"] = out.groupby("country_code")["value"].diff()
    out["pct_change"] = out.groupby("country_code")["value"].pct_change() * 100
    return out.reset_index(drop=True)


def correlate_indicators(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    year: int | None = None,
) -> dict:
    """
    Compute the Pearson correlation between two indicators, joined on
    country_code (and year, if provided — otherwise averaged across all
    years each country has data for both indicators).

    Returns:
        {
            "n": number of countries used,
            "correlation": Pearson r (or None if fewer than 2 data points),
            "points": [{"country_code", "country_name", "x", "y"}, ...]
        }
    """
    a = df_a.copy()
    b = df_b.copy()

    if year is not None:
        a = a[a["year"] == year]
        b = b[b["year"] == year]
    else:
        a = a.groupby(["country_code", "country_name"], as_index=False)["value"].mean()
        b = b.groupby(["country_code", "country_name"], as_index=False)["value"].mean()

    merged = pd.merge(
        a[["country_code", "country_name", "value"]],
        b[["country_code", "value"]],
        on="country_code",
        suffixes=("_a", "_b"),
    )

    if len(merged) < 2:
        return {"n": len(merged), "correlation": None, "points": []}

    correlation = merged["value_a"].corr(merged["value_b"])

    points = [
        {
            "country_code": row["country_code"],
            "country_name": row["country_name"],
            "x": row["value_a"],
            "y": row["value_b"],
        }
        for _, row in merged.iterrows()
    ]

    return {
        "n": len(merged),
        "correlation": None if pd.isna(correlation) else round(float(correlation), 4),
        "points": points,
    }
