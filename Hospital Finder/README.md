# Hospital Finder

A conversational hospital finder powered by the OpenAI Chat API and CMS patient-reported outcomes data for hip and knee replacement surgeries (THA/TKA).

Ask natural-language questions like:
- *"Find hospitals in Boston, MA with hip replacement data"*
- *"Which hospitals in Texas have the best knee replacement scores?"*
- *"Show me hospitals near ZIP code 10001"*

---

## Architecture

```
Browser (GitHub Pages)  →  Render (Flask + Python)  →  OpenAI API
       index.html               app.py                  gpt-4o-mini
```

The frontend lives on GitHub Pages. All OpenAI calls go through the Flask backend on Render, so your API key is never visible in the browser.

---

## How it works

1. **Flask backend (`app.py`)** loads the CMS CSV dataset at startup and serves the `/chat` endpoint.
2. When you ask a question, the backend filters the CSV to the most relevant rows and sends them as context to OpenAI.
3. OpenAI returns a natural-language answer, which appears in the chat UI.
4. Your API key never leaves the server — it is never exposed in the browser.

---

## Local setup

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

### 5. Run locally

```bash
python app.py
```

Open your browser to **http://localhost:5000**

---

## Render deployment (live public URL)

Follow these steps to host the Flask backend on Render's free tier so the GitHub Pages frontend works publicly.

### 1. Push to GitHub

Make sure `private.txt` is **not** committed (it's in `.gitignore`). Push everything else:

```bash
git add .
git commit -m "Add Hospital Finder app"
git push
```

### 2. Create a Render account

Go to [render.com](https://render.com) and sign up for free.

### 3. Create a new Web Service

1. Click **New** → **Web Service**
2. Connect your GitHub account and select your repo
3. Render will detect `render.yaml` automatically and pre-fill the settings
4. Click **Create Web Service**

### 4. Add your API key

In the Render dashboard for your service:
1. Go to **Environment** → **Environment Variables**
2. Add a new variable:
   - **Key:** `OPENAI_API_KEY`
   - **Value:** your OpenAI key (the contents of your `private.txt`)
3. Click **Save Changes** — Render will redeploy automatically

### 5. Get your Render URL

Once deployed, Render shows your service URL at the top of the dashboard, e.g.:
```
https://hospital-finder-xxxx.onrender.com
```

### 6. Update index.html

Open `Hospital Finder/index.html` and paste your Render URL into `BACKEND_URL`:

```js
const BACKEND_URL = "https://hospital-finder-xxxx.onrender.com";
```

Commit and push that change:

```bash
git add "Hospital Finder/index.html"
git commit -m "Set Render backend URL"
git push
```

### 7. Done!

Visit **`https://izzyh-gif.github.io/Hospital%20Finder/`** — the chat will now reach your live backend.

> **Note:** Render's free tier spins down after 15 minutes of inactivity. The first request after a sleep may take ~30 seconds to respond. Subsequent requests are fast.

---

## Project structure

```
Hospital Finder/
├── app.py                                   # Flask backend + OpenAI proxy
├── index.html                               # Chat UI (GitHub Pages frontend)
├── render.yaml                              # Render deployment config
├── requirements.txt                         # Python dependencies
├── README.md                                # This file
├── PATIENT_REPORTED_OUTCOMES_FACILITY.csv   # CMS dataset
└── private.txt                              # Your API key (NOT committed)
```

---

## Customisation

### Change the AI's behaviour
Edit the `SYSTEM_PROMPT` string near the top of `app.py`.

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
