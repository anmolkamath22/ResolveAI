# ResolveAI V2 data model

The SQLite database is the authoritative simulated enterprise system. Golden demo records use `CUS-100` / `ORD-1042` / `CASE-100` for the blocked-replacement path and `CUS-200` / `ORD-2042` / `CASE-200` for the successful-replacement path.

| Table | Purpose | Important relationship |
|---|---|---|
| `customers` | Synthetic customer account and contact context | One customer has many orders/cases |
| `orders` | Item, lifecycle and eligibility facts | Links customer and payment |
| `inventory` | Numeric available/reserved quantity per product/warehouse | Checked before replacement |
| `payments` | Captured/refunded monetary state | One payment per order |
| `refunds` | Idempotent refund transaction | Unique `order_id` prevents duplicate refund |
| `replacements` | Replacement confirmation | Unique `order_id` prevents duplicate replacement |
| `shipments` | Delivery lifecycle and tracking facts | One shipment per seeded order |
| `cases` | Customer issue and final resolution | Links customer and order |
| `audit_events` | State-changing operational audit | Links case and before/after state |

Run `python -m storage.seed --customers 2000 --orders 10000` for a deterministic larger data set. Golden cases are always retained. The seed script adds indexes for customer/order, product, case status, payment, and shipment lookups.

Refund lifecycle: `PAYMENT_CAPTURED → REFUNDED`. A refund writes the refund record, updates `payments.refunded_amount`, updates payment/order state, writes an audit event, then verification rereads state before resolving the case.

## V3 extensions

`products`, `warehouses`, and multi-warehouse `inventory` hold fulfillment truth; inventory is numeric per warehouse, not a boolean. `order_items` records the expected/delivered SKU, `carrier_logs` holds delivery telemetry, `return_labels` records idempotent RMA labels, and `approval_tasks` holds human review packages for high-value financial actions. `CASE-100` through `CASE-800` cover the deterministic multi-case operations suite.
