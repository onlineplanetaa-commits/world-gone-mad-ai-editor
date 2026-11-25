# World Gone Mad AI Editor

A research and editorial assistant for the public Telegram channel **World Gone Mad**.

## What it does

- Searches Google News RSS for English-language story leads across selected topics.
- Lets the editor open the original report and review publication details.
- Provides a checklist for checking dates, sources, evidence and uncertainty.
- Can generate an English Telegram draft using an OpenAI API key.
- Keeps source links separate from the post text.

## What it does not do

- Does not connect to Telegram or request a Telegram login.
- Does not publish, comment, message, subscribe, react or invite users.
- Does not connect to Reddit.
- Does not link to ua-stena.info.
- Does not guarantee that feed results are accurate. The editor must verify each story.

## Run locally

Python 3.10 or newer is recommended.

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy free on Streamlit Community Cloud

1. Sign in at https://share.streamlit.io/ using GitHub.
2. Choose **Create app** and select this repository.
3. Select branch `main` and main file path `app.py`.
4. Deploy the app.

Free hosting availability and limits are controlled by Streamlit and may change.

## Enable AI draft generation

AI drafting requires an OpenAI API key and may incur API charges. It is optional.

In Streamlit Community Cloud:
1. Open the deployed app's **Settings**.
2. Open **Secrets**.
3. Add:

```toml
OPENAI_API_KEY = "your_api_key_here"
```

Never commit API keys to GitHub. Without a key, the RSS research and editorial checklist still work.

## Editorial rule

Treat RSS results as story leads, not established facts. Open the original report, verify dates and claims, and seek independent confirmation before publishing. Clearly label uncertainty and never invent details.
