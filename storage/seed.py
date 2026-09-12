"""Explicit deterministic seed command: python -m storage.seed --customers 2000 --orders 10000."""
from __future__ import annotations
import argparse
from pathlib import Path
from storage.database import DEFAULT_DB, reset_database, connect

def seed(path: str | Path = DEFAULT_DB, customers: int = 4, orders: int = 4, scenario: str = "adaptation") -> None:
    """Seed golden cases, then add synthetic indexed records for explorer/load testing."""
    reset_database(path, scenario)
    if customers <= 4 and orders <= 4: return
    conn=connect(path)
    for index in range(5, customers + 1):
        cid=f"CUS-{index:04d}";conn.execute("INSERT INTO customers VALUES(?,?,?,?,?,?)",(cid,f"Demo Customer {index}",f"customer{index}@example.test","STANDARD","ACTIVE",f"{index} Synthetic Way"))
    for index in range(5, orders + 1):
        cid=f"CUS-{5 + ((index - 5) % max(customers - 4, 1)):04d}" if customers > 4 else "CUS-100"
        oid=f"ORD-{index:05d}"; pid="PROD-HEAD" if index % 3 == 0 else "PROD-SPEAK"
        product="Wireless Headphones" if pid=="PROD-HEAD" else "Portable Speaker"; amount=129.99 if pid=="PROD-HEAD" else 89.99
        conn.execute("INSERT INTO orders VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(oid,cid,pid,product,"DELIVERED","2026-08-01","2026-08-06","PAID",amount,1,1,0))
        conn.execute("INSERT INTO payments VALUES(?,?,?,?,?,?,?,?,?)",(f"PAY-{index:05d}",oid,amount,"INR","CARD","PAYMENT_CAPTURED",0,f"TXN-{index:05d}",f"AUTH-{index:05d}"))
        conn.execute("INSERT INTO shipments VALUES(?,?,?,?,?,?)",(f"SHP-{index:05d}",oid,"Resolve Express","DELIVERED",f"RX{index:05d}","2026-08-06"))
    conn.executescript("CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id); CREATE INDEX IF NOT EXISTS idx_orders_product ON orders(product_name); CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(status); CREATE INDEX IF NOT EXISTS idx_payments_order ON payments(order_id);")
    conn.commit();conn.close()

if __name__ == "__main__":
    parser=argparse.ArgumentParser(description="Seed ResolveAI's deterministic simulated enterprise database.")
    parser.add_argument("--customers",type=int,default=4);parser.add_argument("--orders",type=int,default=4);parser.add_argument("--scenario",choices=["adaptation","replacement"],default="adaptation");parser.add_argument("--db",default=str(DEFAULT_DB))
    args=parser.parse_args();seed(args.db,args.customers,args.orders,args.scenario);print(f"Seeded {args.db} with {args.customers} customers and {args.orders} orders.")
