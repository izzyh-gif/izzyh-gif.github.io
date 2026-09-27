# Gong cha Drink Match

A static GitHub Pages chat interface backed by a small Flask/OpenAI service on Render. The chat asks about flavor preferences and recommends a drink from the starter catalog based on the [official Gong cha product guide](https://www.gong-cha.com/our-products/).

## Local development

1. Keep your OpenAI key in `Gong chat/private.txt`. The repository `.gitignore` already excludes `private.txt` at every directory depth.
2. From `Gong chat`, create a virtual environment and install dependencies:

   ```text
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   python app.py
   ```

3. In a second terminal, serve the repository so the browser sends an allowed HTTP origin:

   ```text
   python3 -m http.server 8000
   ```

4. Open `http://localhost:8000/Gong%20chat/`.

The frontend currently points to `https://gong-cha-chat-api.onrender.com`. For local-only testing, change `BACKEND_URL` in `index.html` to `http://localhost:5000`. Render uses `Gong chat` as the service root, so `app.py` and `requirements.txt` are found directly without a nested backend directory.

## Deploy the backend to Render

1. Push the repository without `private.txt`.
2. In Render, create a new Blueprint or Web Service from the repository and use `Gong chat/render.yaml`.
3. Set the secret environment variable `OPENAI_API_KEY` to the key stored in your local `private.txt`.
4. Set `ALLOWED_ORIGINS` to the origin that will host the static page, for example `https://your-user.github.io`. Include `http://localhost:8000` if local browser testing is needed.
5. Deploy the service and confirm `https://<your-render-service>.onrender.com/health` returns a JSON status response.
6. Update `BACKEND_URL` in `Gong chat/index.html` with the actual Render service URL, then push that frontend change to GitHub.

The backend never sends the OpenAI key to the browser. CORS, message-size validation, a small in-memory rate limit, and generic production errors are included as baseline protections. The rate limit is per Render instance, so add a managed rate limiter before treating this as a high-traffic production service.

## GitHub Pages

The working app is `Gong chat/index.html`, so with the repository published as a project site it is available at a URL shaped like:

`https://your-user.github.io/your-repository/Gong%20chat/`

GitHub Pages does not run the Python backend; it only hosts the static HTML, CSS, and JavaScript.
