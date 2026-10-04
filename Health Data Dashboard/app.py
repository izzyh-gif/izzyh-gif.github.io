"""
Global Health Trends Dashboard — Flask Backend
==================================================
Serves the frontend (index.html) and exposes a small JSON API that fetches,
normalizes, caches, and analyzes public health data from two sources:

  - WHO Global Health Observatory (GHO) OData API
  - Our World in Data (OWID) Grapher CSV exports

See data_sources/who_client.py and data_sources/owid_client.py for the
source-specific fetching logic, data_sources/fetcher.py for caching +
dispatch, indicators.py for the indicator registry, and analysis.py for
the comparative/statistical functions.

Usage (local):
    python app.py
    Then open http://localhost:5000

Usage (Render):
    Deployed automatically via render.yaml.
    The frontend (index.html on GitHub Pages) calls this server via
    BACKEND_URL in index.html.
"""

from __future__ import annotations

import os
import pathlib

from flask import Flask, jsonify, request
from flask_cors import CORS

import analysis
from data_sources.fetcher import get_indicator_data
from data_sources.who_client import get_country_lookup as who_country_lookup
from indicators import get_indicator, list_indicators

# ============================================================
# CONFIGURATION
# ============================================================

CONFIG = {
    "HOST": "0.0.0.0",
    "PORT": int(os.environ.get("PORT", 5000)),
    "DEBUG": os.environ.get("RENDER") is None,  # disable debug on Render
}

BASE_DIR = pathlib.Path(__file__).parent

app = Flask(__name__, template_folder=str(BASE_DIR))

# Allow requests from GitHub Pages and localhost
CORS(app, origins=[
    "https://izzyh-gif.github.io",
    "http://localhost:5000",
    "http://127.0.0.1:5000",
])


# ============================================================
# HELPERS
# ============================================================

def _parse_countries_param() -> list[str] | None:
    """Parse a comma-separated ?countries=USA,GBR,IND query param."""
    raw = request.args.get("countries", "").strip()
    if not raw:
        return None
    return [c.strip().upper() for c in raw.split(",") if c.strip()]


def _parse_int_param(name: str) -> int | None:
    raw = request.args.get(name)
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _df_to_records(df) -> list[dict]:
    """Convert a pandas DataFrame to a list of plain dicts, JSON-safe."""
    return df.where(df.notna(), None).to_dict(orient="records")


def _load_indicator_or_404(indicator_id: str):
    """
    Fetch indicator data, returning either (df, None) on success or
    (None, (response, status_code)) on failure, so routes can do:
        df, error = _load_indicator_or_404(indicator_id)
        if error: return error
    """
    if get_indicator(indicator_id) is None:
        return None, (jsonify({"error": f"Unknown indicator id '{indicator_id}'"}), 404)
    try:
        df = get_indicator_data(indicator_id)
    except Exception as e:
        return None, (jsonify({"error": f"Failed to fetch indicator data: {e}"}), 502)
    return df, None


# ============================================================
# ROUTES — static frontend
# ============================================================

@app.route("/")
def index():
    """Serve the frontend HTML."""
    html_path = BASE_DIR / "index.html"
    return html_path.read_text(encoding="utf-8")


# ============================================================
# ROUTES — indicator registry & reference data
# ============================================================

@app.route("/api/indicators")
def api_indicators():
    """
    GET /api/indicators
    Returns the full indicator registry, grouped by category, so the
    frontend can build its indicator picker without any hardcoded names.
    """
    return jsonify(list_indicators())


@app.route("/api/countries")
def api_countries():
    """
    GET /api/countries
    Returns the master list of countries (code + name) available for
    filtering, sourced from WHO's COUNTRY dimension (234 countries).
    """
    try:
        lookup = who_country_lookup()
    except Exception as e:
        return jsonify({"error": f"Failed to fetch country list: {e}"}), 502
    countries = [{"code": code, "name": name} for code, name in sorted(lookup.items(), key=lambda kv: kv[1])]
    return jsonify(countries)


# ============================================================
# ROUTES — data & analysis
# ============================================================

@app.route("/api/data")
def api_data():
    """
    GET /api/data?indicator=<id>&countries=USA,GBR&year_min=2000&year_max=2023
    Returns raw normalized data points for one indicator, optionally
    filtered by country list and/or year range.
    """
    indicator_id = request.args.get("indicator", "")
    df, error = _load_indicator_or_404(indicator_id)
    if error:
        return error

    df = analysis.filter_data(
        df,
        countries=_parse_countries_param(),
        year_min=_parse_int_param("year_min"),
        year_max=_parse_int_param("year_max"),
    )
    return jsonify({
        "indicator": get_indicator(indicator_id),
        "data": _df_to_records(df),
    })


@app.route("/api/rankings")
def api_rankings():
    """
    GET /api/rankings?indicator=<id>&year=2022&top_n=10&order=desc
    Returns the top N countries for an indicator in a given year.
    """
    indicator_id = request.args.get("indicator", "")
    df, error = _load_indicator_or_404(indicator_id)
    if error:
        return error

    year = _parse_int_param("year")
    if year is None:
        return jsonify({"error": "Missing required 'year' parameter"}), 400

    top_n = _parse_int_param("top_n") or 10
    ascending = request.args.get("order", "desc").lower() == "asc"

    ranked = analysis.rankings(df, year=year, top_n=top_n, ascending=ascending)
    return jsonify({
        "indicator": get_indicator(indicator_id),
        "year": year,
        "data": _df_to_records(ranked),
    })


@app.route("/api/trend")
def api_trend():
    """
    GET /api/trend?indicator=<id>&countries=USA,GBR
    Returns year-over-year change (absolute + percent) per country.
    """
    indicator_id = request.args.get("indicator", "")
    df, error = _load_indicator_or_404(indicator_id)
    if error:
        return error

    df = analysis.filter_data(df, countries=_parse_countries_param())
    trend = analysis.year_over_year_change(df)
    return jsonify({
        "indicator": get_indicator(indicator_id),
        "data": _df_to_records(trend),
    })


@app.route("/api/correlation")
def api_correlation():
    """
    GET /api/correlation?indicator_x=<id>&indicator_y=<id>&year=2022
    Returns the Pearson correlation between two indicators across
    countries, plus the scatter points used to compute it. If 'year' is
    omitted, each country's values are averaged across all available years.
    """
    id_x = request.args.get("indicator_x", "")
    id_y = request.args.get("indicator_y", "")

    df_x, error_x = _load_indicator_or_404(id_x)
    if error_x:
        return error_x
    df_y, error_y = _load_indicator_or_404(id_y)
    if error_y:
        return error_y

    year = _parse_int_param("year")
    result = analysis.correlate_indicators(df_x, df_y, year=year)

    return jsonify({
        "indicator_x": get_indicator(id_x),
        "indicator_y": get_indicator(id_y),
        "year": year,
        **result,
    })


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    print(f"\n🌍 Global Health Trends Dashboard running at http://localhost:{CONFIG['PORT']}\n")
    app.run(host=CONFIG["HOST"], port=CONFIG["PORT"], debug=CONFIG["DEBUG"])
