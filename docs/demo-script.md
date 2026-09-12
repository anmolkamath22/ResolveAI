# Three-minute demo

1. Select **Replacement blocked → Refund fallback** and press **Reset demo environment**.
2. Use `CASE-100` and: “My headphones arrived damaged. I want a replacement.”
3. Start resolution. In Agent Trace, show policy allowing replacement, inventory reporting zero units, and the recorded `ADAPT_PLAN` event.
4. Show the refund policy check, state-changing refund action, then Verification with `REFUNDED` payment state.
5. Open Audit to show the persistent before/after transition. State that this is a real simulated enterprise failure, not a scripted final answer.

Backup: select **Successful replacement**, reset, and run `CASE-200`. The same controller takes the replacement route because observed inventory differs.

Optional resilience moment: select `refund_api_temporarily_unavailable` in Failure injection before starting CASE-100. The trace records a real `RETRY` from the simulated service, then the idempotent refund is created and verified on the next bounded attempt.
