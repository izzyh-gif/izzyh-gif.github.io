"""
Hospital Finder — Flask Backend
================================
Serves the frontend (index.html) and proxies chat requests to the OpenAI API.
The CMS patient-reported outcomes CSV is loaded once at startup and used as
context for every OpenAI query.

Usage (local):
    python app.py
    Then open http://localhost:5000

Usage (Render):
    Deployed automatically via render.yaml.
    Set the OPENAI_API_KEY environment variable in the Render dashboard.
    The frontend (index.html on GitHub Pages) calls this server via RENDER_URL.
"""

import csv
import os
import pathlib

from flask import Flask, jsonify, request
from flask_cors import CORS
from openai import OpenAI

# ============================================================
# CONFIGURATION
# ============================================================
# All tuneable settings live here. Edit these to change the
# behaviour of the app without touching the logic below.

CONFIG = {
    # Path to the CMS CSV dataset, relative to this file
    "CSV_PATH": "Medicare_IP_Hospitals_by_Provider_and_Service_2024.csv",

    # Path to the file containing your OpenAI API key (one line).
    # Used for local development only. On Render, the key is read
    # from the OPENAI_API_KEY environment variable instead.
    "KEY_PATH": "private.txt",

    # OpenAI model to use for chat completions
    # e.g. "gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"
    "MODEL": "gpt-4o-mini",

    # Maximum number of CSV rows sent to OpenAI per query.
    # Rows are pre-filtered by the user's search terms before
    # this cap is applied. Lower = cheaper; higher = more context.
    "MAX_ROWS_IN_CONTEXT": 50,

    # Flask host and port (local only — Render overrides PORT via env var)
    "HOST": "0.0.0.0",
    "PORT": int(os.environ.get("PORT", 5000)),
    "DEBUG": os.environ.get("RENDER") is None,  # disable debug on Render
}

# ============================================================
# SYSTEM PROMPT
# ============================================================
# This is the overarching instruction sent to the OpenAI model
# on every request. Edit this to change how the assistant
# interprets questions and formats answers.

SYSTEM_PROMPT = """
You are a helpful hospital finder assistant. You have access to a dataset of
US hospitals with Medicare inpatient cost data for 2024, sourced from the
CMS Medicare Inpatient Hospitals by Provider and Service dataset.

Each record represents a specific DRG (Diagnosis Related Group) procedure at
a specific hospital and includes:
- Rndrng_Prvdr_CCN: Provider CMS Certification Number
- Rndrng_Prvdr_Org_Name: Hospital name
- Rndrng_Prvdr_City: City
- Rndrng_Prvdr_St: Street address
- Rndrng_Prvdr_State_Abrvtn: State abbreviation
- Rndrng_Prvdr_Zip5: ZIP code
- Rndrng_Prvdr_RUCA_Desc: Rural/urban classification
- DRG_Cd: DRG procedure code
- DRG_Desc: DRG procedure description
- Tot_Dschrgs: Total number of discharges for this procedure
- Avg_Submtd_Cvrd_Chrg: Average submitted covered charge (billed amount)
- Avg_Tot_Pymt_Amt: Average total payment amount
- Avg_Mdcr_Pymt_Amt: Average Medicare payment amount

When answering:
- Help users find hospitals by name, city, state, or ZIP code.
- Help users compare costs for specific procedures across hospitals.
- Format dollar amounts clearly (e.g. $12,345.67).
- Explain the difference between billed charges, total payment, and Medicare
  payment when relevant.
- Be concise but thorough. Format responses with clear structure.
- Assume users do not have prior medical experience. Make explanations easily understandable and digestible to all backgrounds.
- Only display information the user asks for in a clear readable format. Use bullets or lists when multiple items are in the result.
"""

# ============================================================
# STARTUP: Load API key and CSV data
# ============================================================

BASE_DIR = pathlib.Path(__file__).parent


def load_api_key() -> str:
    """
    Load the OpenAI API key.

    Priority order:
      1. OPENAI_API_KEY environment variable  — used on Render
      2. private.txt file                     — used locally

    This means you never need to change this function when
    switching between local development and Render deployment.
    """
    # 1. Environment variable (Render sets this from the dashboard)
    env_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if env_key:
        print("[startup] Using API key from environment variable.")
        return env_key

    # 2. Local private.txt fallback
    key_path = BASE_DIR / CONFIG["KEY_PATH"]
    if not key_path.exists():
        raise FileNotFoundError(
            f"API key not found. Either:\n"
            f"  - Set the OPENAI_API_KEY environment variable (Render), or\n"
            f"  - Create '{key_path}' with your key (local development)."
        )
    key = key_path.read_text().strip()
    if not key:
        raise ValueError("private.txt is empty. Add your OpenAI API key to it.")
    print("[startup] Using API key from private.txt.")
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

# Allow requests from GitHub Pages and localhost
CORS(app, origins=[
    "https://izzyh-gif.github.io",
    "http://localhost:5000",
    "http://127.0.0.1:5000",
])


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
        "Rndrng_Prvdr_Org_Name", "Rndrng_Prvdr_City", "Rndrng_Prvdr_State_Abrvtn",
        "Rndrng_Prvdr_Zip5", "DRG_Desc", "Rndrng_Prvdr_RUCA_Desc",
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
            f"- {row.get('Rndrng_Prvdr_Org_Name', 'N/A')} | "
            f"{row.get('Rndrng_Prvdr_City', 'N/A')}, {row.get('Rndrng_Prvdr_State_Abrvtn', 'N/A')} "
            f"{row.get('Rndrng_Prvdr_Zip5', '')} | "
            f"DRG {row.get('DRG_Cd', 'N/A')}: {row.get('DRG_Desc', 'N/A')} | "
            f"Discharges: {row.get('Tot_Dschrgs', 'N/A')} | "
            f"Avg Billed: ${row.get('Avg_Submtd_Cvrd_Chrg', 'N/A')} | "
            f"Avg Total Payment: ${row.get('Avg_Tot_Pymt_Amt', 'N/A')} | "
            f"Avg Medicare Payment: ${row.get('Avg_Mdcr_Pymt_Amt', 'N/A')}"
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
            max_tokens=2048,   # Increased — "See more" toggle handles long responses
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
    print(f"\n🏥 Hospital Finder running at http://localhost:{CONFIG['PORT']}\n")
    app.run(host=CONFIG["HOST"], port=CONFIG["PORT"], debug=CONFIG["DEBUG"])
