"""
Hospital Finder — Flask Backend
================================
Serves the frontend (index.html) and proxies chat requests to the OpenAI API.
The CMS patient-reported outcomes CSV is loaded once at startup and used as
context for every OpenAI query.

Usage:
    python app.py

The server runs at http://localhost:5000
"""

import csv
import json
import os
import pathlib

from flask import Flask, jsonify, render_template_string, request
from flask_cors import CORS
from openai import OpenAI

# ============================================================
# CONFIGURATION
# ============================================================
# All tuneable settings live here. Edit these to change the
# behaviour of the app without touching the logic below.

CONFIG = {
    # Path to the CMS CSV dataset, relative to this file
    "CSV_PATH": "PATIENT_REPORTED_OUTCOMES_FACILITY.csv",

    # Path to the file containing your OpenAI API key (one line)
    "KEY_PATH": "private.txt",

    # OpenAI model to use for chat completions
    # e.g. "gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"
    "MODEL": "gpt-4o-mini",

    # Maximum number of CSV rows sent to OpenAI per query.
    # Rows are pre-filtered by the user's search terms before
    # this cap is applied. Lower = cheaper; higher = more context.
    "MAX_ROWS_IN_CONTEXT": 50,

    # Flask host and port
    "HOST": "127.0.0.1",
    "PORT": 5000,
    "DEBUG": True,
}

# ============================================================
# SYSTEM PROMPT
# ============================================================
# This is the overarching instruction sent to the OpenAI model
# on every request. Edit this to change how the assistant
# interprets questions and formats answers.

SYSTEM_PROMPT = """
You are a helpful hospital finder assistant. You have access to a dataset of
US hospitals with patient-reported outcome scores for hip and knee replacement
surgeries (THA/TKA), sourced from the CMS Provider Data Catalog.

Each hospital record includes:
- Facility ID, Facility Name, Address, City/Town, State, ZIP Code
- County/Parish, Telephone Number
- Measure ID and Measure Name (type of procedure)
- Voluntary Reporting status
- Score (performance relative to national average)
- Start Date and End Date of the reporting period

When answering:
- Help users find hospitals by name, city, state, or ZIP code.
- Explain scores clearly: scores indicate performance relative to the
  national average (better, worse, or no different).
- If a score is "Not Available", mention that data is not reported.
- Be concise but thorough. Format responses with clear structure.
- If no matching hospitals are found in the provided data, say so clearly.
- Do not make up hospital information. Only use the data provided.
"""

# ============================================================
# STARTUP: Load API key and CSV data
# ============================================================

BASE_DIR = pathlib.Path(__file__).parent


def load_api_key() -> str:
    """Read the OpenAI API key from private.txt."""
    key_path = BASE_DIR / CONFIG["KEY_PATH"]
    if not key_path.exists():
        raise FileNotFoundError(
            f"API key file not found: {key_path}\n"
            "Create a file called private.txt in the Hospital Finder folder "
            "and paste your OpenAI API key into it."
        )
    key = key_path.read_text().strip()
    if not key:
        raise ValueError("private.txt is empty. Add your OpenAI API key to it.")
    return key


def load_csv() -> list[dict]:
    """Load all rows from the CMS CSV into a list of dicts."""
    csv_path = BASE_DIR / CONFIG["CSV_PATH"]
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV dataset not found: {csv_path}")

    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    print(f"[startup] Loaded {len(rows)} rows from {csv_path.name}")
    return rows


# Load at module level so they're ready before the first request
API_KEY = load_api_key()
CSV_ROWS = load_csv()
openai_client = OpenAI(api_key=API_KEY)

# ============================================================
# FLASK APP
# ============================================================

app = Flask(__name__, template_folder=str(BASE_DIR))
CORS(app)  # Allow requests from the browser during local development


# ============================================================
# HELPERS
# ============================================================

def filter_rows(query: str, rows: list[dict], max_rows: int) -> list[dict]:
    """
    Return up to max_rows CSV rows that are relevant to the user's query.

    Strategy: score each row by how many query tokens appear in key fields,
    then return the top matches. Falls back to the first max_rows rows if
    no tokens match (so the model always has some context).
    """
    tokens = [t.lower() for t in query.split() if len(t) > 1]

    # Fields to search for relevance
    search_fields = [
        "Facility Name", "City/Town", "State", "ZIP Code",
        "County/Parish", "Measure Name",
    ]

    scored: list[tuple[int, dict]] = []
    for row in rows:
        haystack = " ".join(row.get(f, "") for f in search_fields).lower()
        score = sum(1 for t in tokens if t in haystack)
        scored.append((score, row))

    # Sort by relevance descending; keep original order for ties
    scored.sort(key=lambda x: x[0], reverse=True)

    top = [row for _, row in scored[:max_rows]]

    # If nothing matched at all, return a generic sample so the model
    # can still explain what data is available
    if not top:
        return rows[:max_rows]

    return top


def rows_to_text(rows: list[dict]) -> str:
    """Serialise a list of CSV row dicts into a compact readable string."""
    lines = []
    for row in rows:
        lines.append(
            f"- {row.get('Facility Name', 'N/A')} | "
            f"{row.get('City/Town', 'N/A')}, {row.get('State', 'N/A')} "
            f"{row.get('ZIP Code', '')} | "
            f"Phone: {row.get('Telephone Number', 'N/A')} | "
            f"Measure: {row.get('Measure Name', 'N/A')} | "
            f"Score: {row.get('Score', 'N/A')} | "
            f"Voluntary: {row.get('Voluntary_Reporting', 'N/A')} | "
            f"Period: {row.get('Start Date', '')}–{row.get('End Date', '')}"
        )
    return "\n".join(lines)


# ============================================================
# ROUTES
# ============================================================

@app.route("/")
def index():
    """Serve the frontend HTML."""
    html_path = BASE_DIR / "index.html"
    return html_path.read_text(encoding="utf-8")


@app.route("/chat", methods=["POST"])
def chat():
    """
    POST /chat
    Body: { "message": "user's question", "history": [...] }
    Returns: { "reply": "assistant's answer" }

    The handler:
    1. Filters the CSV to rows relevant to the user's message
    2. Injects those rows as context into the system prompt
    3. Sends the full conversation history to OpenAI
    4. Returns the assistant's reply
    """
    body = request.get_json(force=True)
    user_message: str = body.get("message", "").strip()
    history: list[dict] = body.get("history", [])

    if not user_message:
        return jsonify({"error": "Empty message"}), 400

    # Filter CSV to relevant rows
    relevant_rows = filter_rows(
        user_message, CSV_ROWS, CONFIG["MAX_ROWS_IN_CONTEXT"]
    )
    data_context = rows_to_text(relevant_rows)

    # Build the system message with injected data
    system_with_data = (
        SYSTEM_PROMPT.strip()
        + f"\n\nHere is the relevant hospital data for this query "
        f"({len(relevant_rows)} records):\n\n{data_context}"
    )

    # Assemble message list for OpenAI
    messages = [{"role": "system", "content": system_with_data}]

    # Append conversation history (role: user/assistant pairs)
    for turn in history:
        role = turn.get("role")
        content = turn.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})

    # Append the new user message
    messages.append({"role": "user", "content": user_message})

    try:
        response = openai_client.chat.completions.create(
            model=CONFIG["MODEL"],
            messages=messages,
            temperature=0.3,   # Lower = more factual, less creative
            max_tokens=1024,
        )
        reply = response.choices[0].message.content
        return jsonify({"reply": reply})

    except Exception as e:
        # Return the error message to the frontend for display
        return jsonify({"error": str(e)}), 500


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    print(f"\n Hospital Finder running at http://{CONFIG['HOST']}:{CONFIG['PORT']}\n")
    app.run(host=CONFIG["HOST"], port=CONFIG["PORT"], debug=CONFIG["DEBUG"])
