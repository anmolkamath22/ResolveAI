"""Local TF-IDF policy retrieval.  Retrieval informs the model; services remain the gate."""
from __future__ import annotations

from collections import Counter
from math import log, sqrt
import re


POLICIES = [
    ("refund-window", "Refund window", "Customers may request a refund within 30 days of delivery. The order record is the final source for whether a refund is eligible. Refunds return only captured payments."),
    ("damaged-items", "Damage and defects", "For a damaged or defective delivered item, support may offer a replacement when stock is available or a refund when the deterministic eligibility check permits it. Photos can be requested when the claim is unclear."),
    ("partial-items", "Partial order remedies", "A multi-item order can be resolved per line item. Refunds and replacements must identify the affected line item and quantity; unaffected items remain active."),
    ("replacement-stock", "Replacement inventory", "Replacement shipments require available inventory at an operational warehouse. When stock is unavailable, do not promise a replacement; consider another permitted remedy or human review."),
    ("cancel-before-ship", "Cancellation before dispatch", "An order may be cancelled only while its fulfillment status permits cancellation. Once dispatched, support must not cancel it in place."),
    ("cancel-after-ship", "Cancellation after dispatch", "For an order already in transit or delivered, create a return label when appropriate instead of cancelling the shipment. A refund is evaluated after the return under the applicable order gate."),
    ("duplicate-charge", "Duplicate payment", "A duplicate authorization or capture may be reversed after the payment ledger confirms more than one charge for the same order. Never reverse the original valid payment."),
    ("payment-state", "Payment safety", "Refunds are permitted only against captured, refundable payments. Void, pending, reversed, and already-refunded payments require a different workflow or review."),
    ("high-value", "Financial authorization", "Refunds above the delegated authorization threshold require a human approval task with order value and evidence. Automation must not bypass this threshold."),
    ("wrong-item", "Incorrect merchandise", "When delivery does not match the ordered SKU, issue a prepaid return label and arrange the correct item only after the necessary fulfillment checks."),
    ("lost-parcel", "Delivery disputes", "For a parcel marked delivered but reported missing, inspect shipment and carrier records. A carrier claim or human review may be needed when the delivery scan is disputed."),
    ("gift-orders", "Gift orders", "Gift recipients may report a mis-shipped or damaged gift, but account ownership and the affected order must be identified before any financial action. Non-financial return support can proceed when identity is clear."),
    ("subscriptions", "Recurring and subscription orders", "Subscription billing questions require the subscription period, renewal date, and payment record. Proration or exceptions require deterministic billing eligibility or approval; do not infer an amount."),
    ("address-change", "Address changes", "Shipping addresses may be changed before dispatch subject to verification. After dispatch, the carrier route cannot be changed by order cancellation; provide carrier or return options instead."),
    ("international", "International returns", "International orders may have different return routing and evidence requirements. Confirm destination and return method before issuing a label or refund."),
    ("evidence", "Evidence collection", "Request only specific missing evidence needed to decide a claim, such as photos of damage, a transaction reference, delivery address confirmation, or the affected quantity."),
    ("missing-parts", "Missing components", "For a missing accessory or component, identify the item and quantity. A partial refund, component replacement, or human approval can be appropriate depending on inventory and order eligibility."),
    ("price-adjustment", "Price adjustments", "Price-match and price-adjustment requests need the qualifying offer and purchase date. They are not automatic refunds without a matching policy rule."),
    ("fraud", "Fraud and account security", "Potential account takeover, unauthorized high-value purchases, or conflicting identity evidence must be escalated with a concise evidence package. Do not disclose another customer's information."),
    ("returns", "Return labels", "A return label starts a return workflow; it does not itself create a refund. Labels are idempotent and should specify the returned SKU when known."),
    ("policy-unknown", "Uncovered requests", "When policy retrieval does not address a requested exception, gather the missing facts or create a bounded human approval task. Do not invent policy authority."),
    ("multi-request", "Multiple concerns", "A customer may raise more than one concern in the same message. Resolve each independently in a safe sequence and retain the full investigation transcript."),
    ("identity", "Identity and case matching", "Never select an order from a vague request across customers. If zero or multiple eligible cases match, request an order or case identifier and retain the investigation for resumption."),
    ("service-failure", "Service availability", "A transient service failure can be retried once. Repeating the same non-transient failure should lead to a different permitted action, information request, or escalation."),
    ("verification", "Completion verification", "A customer-facing resolved status requires an independent post-action check of the authoritative order, payment, inventory, or task record. A failed verification is not a resolved case."),
]


def _terms(text: str) -> list[str]:
    aliases={"charged":"charge","charges":"charge","charging":"charge","cancelled":"cancel","cancellation":"cancel","damaged":"damage","damages":"damage","replaced":"replace","replacement":"replace","refunded":"refund","refunds":"refund","shipped":"ship","shipping":"ship"}
    return [aliases.get(term,term) for term in re.findall(r"[a-z0-9]{2,}", text.lower())]


class PolicyRAG:
    def __init__(self, corpus: list[tuple[str, str, str]] = POLICIES):
        self.corpus = corpus
        docs = [set(_terms(f"{title} {body}")) for _, title, body in corpus]
        self.idf = {term: log((1 + len(docs)) / (1 + sum(term in d for d in docs))) + 1 for d in docs for term in d}

    def search(self, query: str, limit: int = 4) -> list[dict[str, object]]:
        q = Counter(_terms(query))
        if not q:
            return []
        q_norm = sqrt(sum((count * self.idf.get(term, 0)) ** 2 for term, count in q.items())) or 1
        scored = []
        for policy_id, title, body in self.corpus:
            d = Counter(_terms(f"{title} {body}")); d_norm = sqrt(sum((count * self.idf.get(term, 0)) ** 2 for term, count in d.items())) or 1
            dot = sum(q[term] * d[term] * self.idf.get(term, 0) ** 2 for term in q)
            score = dot / (q_norm * d_norm)
            if score:
                scored.append({"id": policy_id, "title": title, "text": body, "score": round(score, 4)})
        return sorted(scored, key=lambda item: item["score"], reverse=True)[:limit]
