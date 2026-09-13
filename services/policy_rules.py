"""Deterministic policy rules: the sole source of authorization eligibility."""
from __future__ import annotations
from datetime import date, datetime

REFUND_WINDOW_DAYS=30
HIGH_VALUE_THRESHOLD=20_000.0
NON_REFUNDABLE_STATUSES={"REFUNDED","REPLACED","CANCELLED"}
NON_CANCELLABLE_STATUSES={"SHIPPED","DELIVERED","REFUNDED","REPLACED","CANCELLED"}

def _days_since(iso_date: str|None)->int|None:
    if not iso_date:return None
    return (date.today()-datetime.fromisoformat(iso_date).date()).days

def refund_eligible(order: dict)->tuple[bool,str]:
    if order["payment_status"]!="PAID":return False,"Order payment is not in a paid state"
    if order["status"] in NON_REFUNDABLE_STATUSES:return False,f"Order status {order['status']} is not refund-eligible"
    delivered_days=_days_since(order.get("delivered_at"))
    if delivered_days is None:return True,"Order not yet delivered; refund evaluated on payment and order state"
    if delivered_days>REFUND_WINDOW_DAYS:return False,f"Delivered {delivered_days} days ago, exceeding the {REFUND_WINDOW_DAYS}-day refund window"
    return True,f"Within the {REFUND_WINDOW_DAYS}-day refund window ({delivered_days} days since delivery)"

def replacement_eligible(order: dict)->tuple[bool,str]:return refund_eligible(order)

def cancellation_eligible(order: dict)->tuple[bool,str]:
    if order["status"] in NON_CANCELLABLE_STATUSES:return False,f"Order status {order['status']} can no longer be cancelled in place"
    return True,"Order has not shipped; cancellation permitted"

def requires_human_approval(amount: float)->bool:return amount>HIGH_VALUE_THRESHOLD
