# Hospital Finder

A conversational hospital finder powered by the OpenAI Chat API and CMS patient-reported outcomes data for hip and knee replacement surgeries (THA/TKA).

Ask natural-language questions like:
- *"Find hospitals in Boston, MA with hip replacement data"*
- *"Which hospitals in Texas have the best knee replacement scores?"*
- *"Show me hospitals near ZIP code 10001"*

---

## How it works

1. **Flask backend (`app.py`)** loads the CMS CSV dataset at startup and serves the frontend.
2. When you ask a question, the backend filters the CSV to the most relevant rows and sends them as context to OpenAI.
3. OpenAI returns a natural-language answer, which appears in the chat UI.
4. Your API key never leaves the server — it is never exposed in the browser.

---

## Setup

### 1. Prerequisites

- Python 3.10 or higher
- An [OpenAI API key](https://platform.openai.com/api-keys)

### 2. Clone the repo

```bash
git clone https://github.com/<your-username>/<your-repo>.git
cd "<repo>/Hospital Finder"
```

### 3. Add your API key

Create a file called `private.txt` in the `Hospital Finder` folder and paste your OpenAI API key into it (one line, nothing else):

```
sk-...your-key-here...
```

> `private.txt` is listed in `.gitignore` and will never be committed to the repo.

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

Or use a virtual environment (recommended):

```bash
python -m venv venv
source venv/bin/activate      # macOS/Linux
venv\Scripts\activate         # Windows
pip install -r requirements.txt
```

### 5. Run the app

```bash
python app.py
```

Open your browser to **http://localhost:5000**

---

## Project structure

```
Hospital Finder/
├── app.py                              # Flask backend + OpenAI proxy
├── index.html                          # Chat UI frontend
├── requirements.txt                    # Python dependencies
├── README.md                           # This file
├── PATIENT_REPORTED_OUTCOMES_FACILITY.csv  # CMS dataset
└── private.txt                         # Your API key (NOT committed)
```

---

## Customisation

### Change the AI's behaviour
Edit the `SYSTEM_PROMPT` string near the top of `app.py`. This controls how the assistant interprets questions and formats answers.

### Change model, result limits, etc.
Edit the `CONFIG` dictionary in `app.py`:

| Key | Default | Description |
|-----|---------|-------------|
| `MODEL` | `gpt-4o-mini` | OpenAI model to use |
| `MAX_ROWS_IN_CONTEXT` | `50` | Max CSV rows sent per query |
| `PORT` | `5000` | Local server port |

### Change UI text and suggested questions
Edit the `UI_CONFIG` object at the top of `index.html`.

---

## Data source

[CMS Provider Data Catalog — Patient-Reported Outcomes](https://data.cms.gov/provider-data/dataset/ynj2-r877)

Data reflects hospital-level performance on patient-reported outcome measures for total hip and knee arthroplasty. Updated periodically by CMS.

> **Disclaimer:** This tool is for informational purposes only and does not constitute medical advice.
