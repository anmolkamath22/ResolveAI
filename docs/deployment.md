# Deployment

For the full live-trace demo, run `docker compose --env-file .env up --build`. This starts the FastAPI agent API on port 8000, the Streamlit operations view on port 8501, and the React SSE demo on port 5173. Keep credentials in `.env` locally or in the platform secret manager; never commit or export the file.

Set `GEMINI_API_KEY` or `OPENROUTER_API_KEY` in the deployment secret manager. `RESOLVEAI_API_KEY` protects write endpoints when the API is public. The deployed SQLite file is seeded locally by the app and reset through the Demo Environment control. This is deliberately suitable for demos, not durable multi-user production storage.

## LLM routing

ResolveAI reads keys from local `.env`, environment variables, or Streamlit Secrets. Gemini is used first for real function-calling decisions; OpenRouter is retried as a fallback if Gemini fails. Each provider receives the retrieved case state, policy evidence, transcript, and explicit tool contracts. A transient provider error gets one retry before the next provider is tried. If no live provider responds, the UI emits a distinct `PROVIDER_FALLBACK` event and labels the execution `offline-demo`; that deterministic test stub is not evidence of model generalization. Policy, payment, and state-changing actions never leave the local simulated enterprise system.

Before sharing an archive, rotate any key previously included in a project export. Export tracked source with `git archive HEAD -o submission.zip`; never archive the working directory wholesale.
