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

import json
import math
import os
import pathlib
import re

from flask import Flask, jsonify, request
from flask_cors import CORS

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - dependency is installed in deployment
    OpenAI = None

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


# Chat requests are deliberately small: the browser supplies the visible
# snapshot, and the model is never allowed to fetch or infer hidden data.
CHAT_MAX_MESSAGE_LENGTH = 1000
CHAT_MAX_HISTORY_MESSAGES = 8
CHAT_MAX_HISTORY_TEXT_LENGTH = 1000
CHAT_MAX_INDICATORS = 2
CHAT_MAX_COUNTRIES = 25
CHAT_MAX_ROWS = 120
CHAT_MAX_POINTS = 120
CHAT_MAX_STATISTICS = 8
CHAT_MAX_REQUEST_BYTES = 100_000
CHAT_MODES = {"trend", "rankings", "correlation"}
CHAT_COUNTRY_CODE = re.compile(r"^[A-Z0-9_-]{1,12}$")
CHAT_RECORD_KEYS = {
    "country_code", "country_name", "year", "value", "change", "pct_change",
    "rank", "x", "y",
}


# ============================================================
# CHAT VALIDATION / CONTEXT
# ============================================================

def _chat_error(message: str, status: int):
    """Return the stable error shape used by the chat endpoint."""
    return jsonify({"error": message}), status


def _bounded_string(value, maximum: int) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value if value and len(value) <= maximum else None


def _clean_chat_record(record: object) -> dict | None:
    """Keep only known, JSON-safe fields from a displayed row or point."""
    if not isinstance(record, dict):
        return None
    cleaned = {}
    for key, value in record.items():
        if key not in CHAT_RECORD_KEYS:
            continue
        if key in {"country_code", "country_name"}:
            if not isinstance(value, str) or len(value) > 120:
                return None
            cleaned[key] = value
        elif isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            return None
        else:
            cleaned[key] = value
    return cleaned if cleaned else None


def _validate_chat_payload(payload: object) -> tuple[dict | None, str | None]:
    """Validate and reduce the browser's visible dashboard snapshot."""
    if not isinstance(payload, dict):
        return None, "Invalid chat request."

    message = _bounded_string(payload.get("message"), CHAT_MAX_MESSAGE_LENGTH)
    mode = payload.get("mode")
    if message is None or mode not in CHAT_MODES:
        return None, "Invalid chat request."

    raw_indicators = payload.get("indicators", [])
    if not isinstance(raw_indicators, list) or len(raw_indicators) > CHAT_MAX_INDICATORS:
        return None, "Invalid chat request."
    indicators = []
    for indicator in raw_indicators:
        if not isinstance(indicator, dict):
            return None, "Invalid chat request."
        cleaned = {}
        for field in ("id", "label", "unit", "description", "source", "source_note"):
            value = indicator.get(field)
            if value is not None:
                if not isinstance(value, str) or len(value) > 240:
                    return None, "Invalid chat request."
                cleaned[field] = value
        if not cleaned.get("id") or not cleaned.get("label"):
            return None, "Invalid chat request."
        indicators.append(cleaned)

    raw_filters = payload.get("filters", {})
    if not isinstance(raw_filters, dict):
        return None, "Invalid chat request."
    raw_countries = raw_filters.get("countries", [])
    if not isinstance(raw_countries, list) or len(raw_countries) > CHAT_MAX_COUNTRIES:
        return None, "Invalid chat request."
    countries = []
    for country in raw_countries:
        if not isinstance(country, str) or not CHAT_COUNTRY_CODE.fullmatch(country.upper()):
            return None, "Invalid chat request."
        countries.append(country.upper())
    filters = {"countries": countries}
    for field in ("year", "top_n"):
        value = raw_filters.get(field)
        if value is not None:
            if isinstance(value, bool) or not isinstance(value, int) or abs(value) > 10000:
                return None, "Invalid chat request."
            filters[field] = value
    order = raw_filters.get("order")
    if order is not None:
        if order not in {"asc", "desc"}:
            return None, "Invalid chat request."
        filters["order"] = order

    raw_snapshot = payload.get("snapshot", {})
    if not isinstance(raw_snapshot, dict):
        return None, "Invalid chat request."
    rows = raw_snapshot.get("rows", [])
    points = raw_snapshot.get("points", [])
    statistics = raw_snapshot.get("statistics", [])
    if (not isinstance(rows, list) or len(rows) > CHAT_MAX_ROWS or
            not isinstance(points, list) or len(points) > CHAT_MAX_POINTS or
            not isinstance(statistics, list) or len(statistics) > CHAT_MAX_STATISTICS):
        return None, "Invalid chat request."
    clean_rows = []
    for row in rows:
        cleaned = _clean_chat_record(row)
        if cleaned is None:
            return None, "Invalid chat request."
        clean_rows.append(cleaned)
    clean_points = []
    for point in points:
        cleaned = _clean_chat_record(point)
        if cleaned is None:
            return None, "Invalid chat request."
        clean_points.append(cleaned)
    clean_statistics = []
    for statistic in statistics:
        if not isinstance(statistic, dict):
            return None, "Invalid chat request."
        label = _bounded_string(statistic.get("label"), 120)
        value = statistic.get("value")
        if label is None or not isinstance(value, (str, int, float)) or isinstance(value, bool):
            return None, "Invalid chat request."
        if isinstance(value, float) and not math.isfinite(value):
            return None, "Invalid chat request."
        clean_statistics.append({"label": label, "value": value})

    raw_history = payload.get("history", [])
    if not isinstance(raw_history, list) or len(raw_history) > CHAT_MAX_HISTORY_MESSAGES:
        return None, "Invalid chat request."
    history = []
    for item in raw_history:
        if not isinstance(item, dict) or item.get("role") not in {"user", "assistant"}:
            return None, "Invalid chat request."
        text = _bounded_string(item.get("content"), CHAT_MAX_HISTORY_TEXT_LENGTH)
        if text is None:
            return None, "Invalid chat request."
        history.append({"role": item["role"], "content": text})

    context = {
        "mode": mode,
        "indicators": indicators,
        "filters": filters,
        "snapshot": {
            "rows": clean_rows,
            "points": clean_points,
            "statistics": clean_statistics,
        },
    }
    return {"message": message, "history": history, "context": context}, None


def _chat_scope(context: dict) -> dict:
    return {
        "mode": context["mode"],
        "indicator_ids": [item["id"] for item in context["indicators"]],
        "selected_country_count": len(context["filters"]["countries"]),
        "visible_row_count": len(context["snapshot"]["rows"]),
        "visible_point_count": len(context["snapshot"]["points"]),
    }


def _openai_api_key() -> str:
    """Read the production environment key or a local ignored fallback."""
    value = os.environ.get("OPENAI_API_KEY", "").strip()
    if value:
        return value
    local_key_path = BASE_DIR / "private.txt"
    if local_key_path.exists():
        return local_key_path.read_text(encoding="utf-8").strip()
    return ""


def _ask_chat_model(chat: dict) -> str:
    """Ask OpenAI using only the validated dashboard snapshot and history."""
    api_key = _openai_api_key()
    if not api_key or OpenAI is None:
        raise RuntimeError("chat provider unavailable")

    system_prompt = (
        "You answer questions about a public-health dashboard. Use ONLY the dashboard "
        "snapshot JSON below and the conversation. Do not use outside knowledge, "
        "invent values, claim access to hidden rows, or give medical advice. If the "
        "snapshot does not contain enough information, say so plainly. Keep answers "
        "concise and mention the relevant indicator, unit, or filter when useful.\n\n"
        "DASHBOARD SNAPSHOT:\n" + json.dumps(chat["context"], separators=(",", ":"), ensure_ascii=True)
    )
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(chat["history"])
    messages.append({"role": "user", "content": chat["message"]})

    client = OpenAI(api_key=api_key, timeout=20.0)
    response = client.chat.completions.create(
        model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        messages=messages,
        temperature=0.1,
        max_tokens=500,
    )
    answer = response.choices[0].message.content if response.choices else None
    if not isinstance(answer, str) or not answer.strip():
        raise RuntimeError("empty chat response")
    return answer.strip()[:4000]


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


def _indicator_payload(indicator_id: str, df) -> dict:
    """Return indicator metadata annotated with the source actually used."""
    metadata = dict(get_indicator(indicator_id))
    sources = sorted({str(source) for source in df.get("source", []).dropna()}) if "source" in df else []
    if sources:
        metadata["data_source"] = sources[0] if len(sources) == 1 else sources
        if sources[0] != metadata.get("source"):
            metadata["source_note"] = (
                f"Primary {metadata.get('source')} data was unavailable; "
                f"this result uses {sources[0]} data."
            )
    return metadata


# ============================================================
# ROUTES — static frontend
# ============================================================

@app.get("/health")
def health():
    """Return a lightweight Render deployment check."""
    return jsonify({"status": "ok", "service": "health-data-dashboard"})


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


@app.route("/api/chat", methods=["POST"])
def api_chat():
    """
    POST /api/chat
    Answer a question from the bounded, visible dashboard snapshot supplied
    by the browser. This route never fetches indicator data on the model's
    behalf and never returns provider-specific error details.
    """
    if request.content_length and request.content_length > CHAT_MAX_REQUEST_BYTES:
        return _chat_error("Invalid chat request.", 400)

    payload = request.get_json(silent=True)
    chat, error = _validate_chat_payload(payload)
    if error:
        return _chat_error(error, 400)

    try:
        answer = _ask_chat_model(chat)
    except RuntimeError:
        return _chat_error("Chat service is temporarily unavailable.", 503)
    except Exception:
        return _chat_error("Chat service is temporarily unavailable.", 502)

    return jsonify({"answer": answer, "scope": _chat_scope(chat["context"])})


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
        "indicator": _indicator_payload(indicator_id, df),
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
        "indicator": _indicator_payload(indicator_id, df),
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
        "indicator": _indicator_payload(indicator_id, df),
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
        "indicator_x": _indicator_payload(id_x, df_x),
        "indicator_y": _indicator_payload(id_y, df_y),
        "year": year,
        **result,
    })


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    print(f"\n🌍 Global Health Trends Dashboard running at http://localhost:{CONFIG['PORT']}\n")
    app.run(host=CONFIG["HOST"], port=CONFIG["PORT"], debug=CONFIG["DEBUG"])
