# ResolveAI v5 — 3-minute demo script

## Before recording

Start the React live demo and API, then open `http://localhost:5173`. Keep the Streamlit operations console at `http://localhost:8501` ready for the audit view. Reset Streamlit to **Replacement blocked → refund fallback**. Confirm the provider badge shows Gemini; if it says `offline-demo`, describe it only as a visible resilience fallback—not as a live-model generalization claim.

## [0:00–0:22] The outcome thesis

**Spoken:** “Most support bots produce a reply. ResolveAI owns the outcome. It reads an authorized customer case, retrieves policy evidence, selects a controlled tool, adapts to what the enterprise system returns, and independently verifies the final state change.”

**Visual:** Open the React live demo. Keep the provider badge, case ID field, and Agent Trace, Policy Evidence, and Authoritative State panels visible.

## [0:22–0:45] The customer request and safe context

**Spoken:** “I’ll use CASE-100: ‘My headphones arrived damaged and I want a replacement.’ The model never receives permission to alter data directly. It receives the request, an authorized case snapshot, prior tool results, policy evidence, and explicit tool contracts.”

**Visual:** Select **Adaptive resolution** and press **Start live resolution**. Point to entity resolution and policy retrieval streaming into the trace.

## [0:45–1:15] Grounded policy—not a hardcoded flag

**Spoken:** “ResolveAI retrieves ranked policy text using local TF-IDF similarity. Separately, the service computes eligibility from delivery date, payment state, order state, and shipment state. Policy RAG informs the decision; deterministic rules authorize the mutation.”

**Visual:** Point to Policy Evidence and `SEARCH_POLICY`. Mention the matching policy reference and that legacy seed booleans are not used for authorization.

## [1:15–1:45] A real constraint triggers replanning

**Spoken:** “The agent investigates inventory before it promises fulfilment. There are zero available replacement headphones across the warehouse records. The replacement action is blocked by the enterprise tool—not by a scripted branch. The next decision uses that structured failure as evidence and evaluates the remaining safe remedy.”

**Visual:** Pause on `GET_INVENTORY`, its zero-unit result, and `ADAPT_PLAN`.

## [1:45–2:12] Controlled mutation and verification

**Spoken:** “The service creates the refund only after server-side policy and captured-payment checks pass. The request is idempotent, writes an audit event in the same transaction, and then ResolveAI calls VERIFY. It rereads the payment and refund records directly; the agent cannot report resolved merely because a tool said it succeeded.”

**Visual:** Pause on `CREATE_REFUND`, then `VERIFY`, then show the resolved status and payment snapshot. Switch briefly to Streamlit **Audit**.

## [2:12–2:35] Generalization and customer isolation

**Spoken:** “Natural language is not treated as a fixed issue template. A cached Bitext customer-support dataset provides an offline TF-IDF intent hint for paraphrased requests, while explicit case and order IDs always win. An unscoped ambiguous request never selects a customer, and the API rejects a case that does not belong to the supplied customer context.”

**Visual:** Show the policy/test evidence or a vague request ending in **NEEDS CLARIFICATION**. Do not claim the offline stub is live-model generalization.

## [2:35–3:00] Close and resilience

**Spoken:** “The trace, policy citations, authoritative state, and audit log make every claim inspectable. If a live provider is unavailable, the UI labels the fallback explicitly instead of pretending a keyword stub is model reasoning. ResolveAI is a bounded agentic workflow: observe, ground, act, adapt, verify—and prove the customer outcome.”

**Visual:** End on the resolved banner, provider badge, and audit evidence. Optional final screen: the ‘Why ResolveAI’ presentation slide.
