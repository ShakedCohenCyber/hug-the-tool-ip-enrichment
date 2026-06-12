# Hug-The-Tool IP Enrichment

Single-page Streamlit application for public IP enrichment and OSINT triage.

## Run

1. Install dependencies: `pip install -r requirements.txt`
2. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and add API keys.
3. Start the app: `streamlit run app.py`

## Deploy

Deploy `app.py` from this repository with Streamlit Community Cloud, then add the
same four keys through the app's **Settings > Secrets** panel.

The app does not log, cache, or persist queried IP addresses. Internal and non-routable
addresses are rejected locally before external API calls are made.
