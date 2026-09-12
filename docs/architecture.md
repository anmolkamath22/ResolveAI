# Architecture

```text
Streamlit UI → ResolutionAgent state machine → Enterprise service boundary → SQLite
                         ↑                         ↓
                  evaluation/adaptation ← tool results + verification
```

`ResolutionAgent` owns operational decisions, not policy truth. It accesses the enterprise only through an allow-listed `ToolRegistry`; invalid tool names and malformed arguments return structured errors. `Enterprise` enforces policy and authorization, performs idempotent writes, and records audit events. After each state-changing operation, the verification service re-reads enterprise state before a case becomes `RESOLVED`.

The graph is bounded by `MAX_AGENT_ACTIONS`, `MAX_REPLANS`, and `MAX_RETRIES`; exhausted or unsafe paths are escalated. Only `SERVICE_UNAVAILABLE` and `TIMEOUT` failures are retried. Inventory shortages and policy denials become evidence for adaptation, never retries. The trace is composed from actual state-machine events rather than a scripted UI timeline.

V3 adds archetype routing from persisted case truth: duplicate-payment reversal, pre/post-shipment cancellation paths, return-label generation, carrier-dispute escalation, and financial-threshold approval tasks. Graph rendering is guarded so an unavailable Graphviz/Streamlit renderer falls back to the DOT execution path instead of crashing the case workspace.
