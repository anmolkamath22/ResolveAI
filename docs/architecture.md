# Architecture

```text
Streamlit UI → ResolutionAgent state machine → Enterprise service boundary → SQLite
                         ↑                         ↓
                  evaluation/adaptation ← tool results + verification
```

`ResolutionAgent` owns operational decisions, not policy truth. It accesses the enterprise only through an allow-listed `ToolRegistry`; invalid tool names and malformed arguments return structured errors. `Enterprise` enforces policy and authorization, performs idempotent writes, and records audit events. After each state-changing operation, the verification service re-reads enterprise state before a case becomes `RESOLVED`.

The graph is bounded by `MAX_AGENT_ACTIONS`, `MAX_REPLANS`, and `MAX_RETRIES`; exhausted or unsafe paths are escalated. Only `SERVICE_UNAVAILABLE` and `TIMEOUT` failures are retried. Inventory shortages and policy denials become evidence for adaptation, never retries. The trace is composed from actual state-machine events rather than a scripted UI timeline.

V3 adds archetype routing from persisted case truth: duplicate-payment reversal, pre/post-shipment cancellation paths, return-label generation, carrier-dispute escalation, and financial-threshold approval tasks. Graph rendering is guarded so an unavailable Graphviz/Streamlit renderer falls back to the DOT execution path instead of crashing the case workspace.
# ResolveAI v4 architecture

ResolveAI runs a bounded **observe → reason → tool call → observe** investigation loop. Each turn provides the provider with the verbatim request, authorized case snapshot, full tool transcript, retrieved policy citations, and tool schemas. The provider proposes one action or terminal outcome; it cannot write the database itself.

`SEARCH_POLICY` uses local TF-IDF similarity over a broad policy corpus. Policy RAG informs the model's interpretation; deterministic order/payment/inventory flags gate every mutation server-side. Tool calls are allow-listed, validated, idempotent, mutation-capped, retried only once for transient errors, and independently verified before a resolved result is emitted.

Eligibility is computed in `services/policy_rules.py`: delivery-window date math, payment/order status, shipment state, and the high-value threshold are the only authorization source. Legacy seed eligibility columns remain schema-compatible but are not read. Each policy gate exposes a `policy_ref` that corresponds to a PolicyRAG document ID. Bitext's cached support utterances power a separate TF-IDF intent hint for non-ID entity resolution; it narrows scoped candidates but can never resolve an unscoped ambiguous customer match.

Entity resolution never falls back to a fixed customer or system-wide case. An ambiguous or missing match creates a resumable investigation with a specific clarification question. Audit events retain decisions, tool inputs/results, policy citations, and verification evidence.

## Independently testable sandbox contracts

| Sandbox capability | Named tools | Invariant |
| --- | --- | --- |
| Customer DB | `GET_CUSTOMER`, `SEARCH_CUSTOMER` | Read-only; ambiguous matches are never silently selected. |
| Order API | `GET_ORDER`, `GET_CASE_HISTORY` | The order row and its deterministic eligibility flags are authoritative. |
| Inventory API | `GET_INVENTORY` | `CREATE_REPLACEMENT` rechecks and reserves stock at execution time. |
| Resolution endpoints | `CREATE_REFUND`, `CREATE_REPLACEMENT`, `CANCEL_ORDER`, `REVERSE_DUPLICATE_CHARGE`, `GENERATE_RETURN_LABEL`, `CREATE_APPROVAL_TASK` | Policy-gated, idempotent mutations write their audit state transactionally. |
| Policy RAG | `SEARCH_POLICY` | TF-IDF retrieval informs reasoning only; it never returns authorization. |
| Verification | `VERIFY` | Each action has an explicit independent DB check; resolved status follows only a passing check. |

Provider fallback is an explicit `PROVIDER_FALLBACK` trace event and state field. The deterministic `OfflineTestStubProvider` is CI-only and visibly labelled `offline-demo`; it is never evidence of live-model generalization. The React demo consumes the FastAPI SSE endpoint and exposes provider identity, policy citations, trace events, and authoritative snapshots turn by turn.
