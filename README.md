# ResolveAI

ResolveAI is a customer-operations prototype for Tech Zephyr 4.0, Track 3 — Smart Automation. It addresses Problem Statement 5: **Autonomous Customer Resolution Agent**.

Instead of producing a support reply and stopping there, ResolveAI investigates a simulated enterprise case, uses controlled tools to take a permitted action, and checks the database afterwards before it reports an outcome.

## What happens in a case

The flagship example is a customer asking for a replacement for damaged headphones. ResolveAI looks up the related case and order, checks the replacement policy, and queries inventory across two warehouses. When no stock is available, it records that the replacement plan is blocked, checks whether a refund is allowed, creates the refund, and verifies the updated payment and case records.

The next step comes from the state returned by the services. A model cannot directly update the database or override a policy decision.

## Included scenarios

| Case | Situation | Outcome handled by the system |
|---|---|---|
| `CASE-100` | Damaged item with no replacement stock | Refund fallback with verification |
| `CASE-200` | Duplicate charge | Duplicate authorization reversal |
| `CASE-300` | Expired return request | Escalation for review |
| `CASE-400` | Cancellation before shipment | Order cancellation |
| `CASE-500` | Cancellation after shipment | Prepaid return label |
| `CASE-600` | Wrong item delivered | Return workflow |
| `CASE-700` | Delivered parcel dispute | Carrier-claim escalation |
| `CASE-800` | High-value request | Human approval task |

## Architecture

```text
Customer request
  → intent parsing
  → case and entity resolution
  → deterministic policy and service checks
  → authorized state mutation
  → independent verification
  → customer-safe result and audit trail
```

The application uses SQLite as the simulated system of record. The tool registry is allow-listed, and financial and fulfilment actions are implemented in deterministic Python services. Gemini can classify a request when configured; OpenRouter is an optional fallback. The offline parser keeps the local demo usable without an API key.

## Run locally

Python 3.11+ is recommended.

```bash
git clone <your-repository-url>
cd ResolveAI
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

The first launch initializes `resolveai.db`. Open the URL printed by Streamlit, usually `http://localhost:8501`, and use **New case** to start a resolution.

## Optional LLM configuration

The prototype works without an API key. To use Gemini and, optionally, OpenRouter for intent parsing, copy `.env.example` to `.env` and add your own values:

```env
GEMINI_API_KEY=
OPENROUTER_API_KEY=
GEMINI_MODEL=gemini-3.6-flash
OPENROUTER_MODEL=google/gemini-3.6-flash
```

`.env` is excluded from version control. Policy decisions, payments, inventory, and verification remain local deterministic operations even when a live model is enabled.

## Seed data and tests

Reset the deterministic dataset:

```bash
python -m storage.seed
```

Add background records for search/performance checks:

```bash
python -m storage.seed --customers 1000 --orders 1200
```

Run the test suite:

```bash
python -m pytest
```

## Project structure

```text
app/        Streamlit operations console
agent/      Agent controller and case routing
demo/       Controlled failure injection
models/     Typed state and tool contracts
providers/  Gemini, OpenRouter, and offline providers
services/   Policy enforcement and enterprise actions
storage/    SQLite schema and deterministic seed data
tools/      Allow-listed tool registry
tests/      Automated regression tests
```

## Scope

ResolveAI is a hackathon prototype. Its customer, payment, carrier, and inventory data are synthetic. It is not connected to real payment processors or commerce platforms. A production version would need authentication, role controls, managed storage, monitoring, and real integration contracts.
