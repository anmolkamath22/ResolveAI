# Deployment

Deploy on Streamlit Community Cloud by selecting this repository and setting the main file to `app/streamlit_app.py`. The only required dependencies are in `requirements.txt`; no secret is required for the deterministic demo.

If a hosted model adapter is added later, set `GEMINI_API_KEY` or `OPENROUTER_API_KEY` in Streamlit secrets—never commit `.env`. The deployed SQLite file is seeded locally by the app and reset through the Demo Environment control. This is deliberately suitable for demos, not durable multi-user production storage.

## LLM routing

ResolveAI reads keys from local `.env`, environment variables, or Streamlit Secrets. Gemini is used first for schema-constrained goal classification; OpenRouter is tried only if Gemini is unavailable or its request fails. If neither provider succeeds, the UI labels the execution `offline-demo` and uses deterministic intent parsing. Policy, payment, and state-changing actions never leave the local simulated enterprise system.
