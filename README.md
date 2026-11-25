# World Gone Mad AI Editor

A research and editorial assistant for the public Telegram channel **World Gone Mad**.

## What it does

- Searches Google News RSS for English-language story leads across selected topics.
- Lets the editor open the original report and review publication details.
- Provides a checklist for checking dates, sources, evidence and uncertainty.
- Can generate an English Telegram draft using an optional OpenAI API key.
- Keeps source links separate from the post text.

## What it does not do

- Does not connect to Telegram or request a Telegram login.
- Does not publish, comment, message, subscribe, react or invite users.
- Does not connect to Reddit.
- Does not link to ua-stena.info.
- Does not guarantee that feed results are accurate. The editor must verify each story.

## Deploy the lightweight web version on Render

The Render version uses Flask and simple HTML pages rather than the Streamlit interface.

1. Sign in at https://render.com/ with GitHub.
2. Choose **New** → **Blueprint** (or **New** → **Web Service**).
3. Connect the repository `onlineplanetaa-commits/world-gone-mad-ai-editor`.
4. If using Blueprint, Render reads `render.yaml` and configures the free web service.
5. If creating a Web Service manually, use:
   - Runtime: Python
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn web_app:app`
   - Health check path: `/health`
   - Instance type: Free

Free Render services sleep after 15 minutes without traffic and may take about a minute to wake. Free services have other usage limits; see https://render.com/docs/free.

## Original Streamlit version

The original Streamlit app remains in `app.py`. It can still be run locally with:

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Enable AI draft generation

AI drafting requires an OpenAI API key and may incur API charges. It is optional.

For the Render version, add an environment variable named `OPENAI_API_KEY` in the service's Environment settings. Never commit API keys to GitHub. Without a key, RSS research and the editorial checklist still work.

## Editorial rule

Treat RSS results as story leads, not established facts. Open the original report, verify dates and claims, and seek independent confirmation before publishing. Clearly label uncertainty and never invent details.
