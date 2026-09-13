"""Authoritative SQLite store, deterministic golden cases, and safe first-run initialization."""
from __future__ import annotations
import sqlite3
from pathlib import Path

DEFAULT_DB=Path(__file__).resolve().parent.parent / "resolveai.db"
SCHEMA="""
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS customers(id TEXT PRIMARY KEY,name TEXT NOT NULL,email TEXT NOT NULL UNIQUE,tier TEXT NOT NULL,status TEXT NOT NULL,address TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS products(id TEXT PRIMARY KEY,sku TEXT UNIQUE,name TEXT NOT NULL,category TEXT,price REAL NOT NULL,return_window_days INTEGER NOT NULL DEFAULT 30);
CREATE TABLE IF NOT EXISTS warehouses(id TEXT PRIMARY KEY,name TEXT,location TEXT,is_operational INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS orders(id TEXT PRIMARY KEY,customer_id TEXT NOT NULL REFERENCES customers(id),product_id TEXT,product_name TEXT,status TEXT NOT NULL,created_at TEXT,delivered_at TEXT,payment_status TEXT,amount REAL NOT NULL,eligible_refund INTEGER,eligible_replacement INTEGER,cancellation_allowed INTEGER); -- deprecated: services/policy_rules.py computes eligibility
CREATE TABLE IF NOT EXISTS order_items(id TEXT PRIMARY KEY,order_id TEXT REFERENCES orders(id),product_id TEXT REFERENCES products(id),quantity INTEGER,unit_price REAL,delivered_sku TEXT);
CREATE TABLE IF NOT EXISTS inventory(product_id TEXT NOT NULL REFERENCES products(id),warehouse_id TEXT NOT NULL REFERENCES warehouses(id),available_units INTEGER NOT NULL,reserved_units INTEGER NOT NULL DEFAULT 0,incoming_units INTEGER NOT NULL DEFAULT 0,reorder_level INTEGER NOT NULL DEFAULT 2,status TEXT,PRIMARY KEY(product_id,warehouse_id));
CREATE TABLE IF NOT EXISTS cases(id TEXT PRIMARY KEY,customer_id TEXT REFERENCES customers(id),order_id TEXT REFERENCES orders(id),issue_type TEXT,description TEXT,status TEXT,current_resolution TEXT,priority TEXT,resolution_summary TEXT);
CREATE TABLE IF NOT EXISTS payments(id TEXT PRIMARY KEY,order_id TEXT REFERENCES orders(id),amount REAL,currency TEXT,method TEXT,status TEXT,refunded_amount REAL DEFAULT 0,transaction_reference TEXT,authorization_token TEXT);
CREATE TABLE IF NOT EXISTS refunds(id TEXT PRIMARY KEY,order_id TEXT REFERENCES orders(id),case_id TEXT REFERENCES cases(id),amount REAL,status TEXT,reason TEXT,payment_id TEXT,idempotency_key TEXT UNIQUE,item_id TEXT,quantity INTEGER,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS replacements(id TEXT PRIMARY KEY,order_id TEXT UNIQUE REFERENCES orders(id),case_id TEXT,product_id TEXT,warehouse_id TEXT,status TEXT,tracking_number TEXT);
CREATE TABLE IF NOT EXISTS shipments(id TEXT PRIMARY KEY,order_id TEXT REFERENCES orders(id),carrier TEXT,status TEXT,tracking_number TEXT,estimated_delivery TEXT);
CREATE TABLE IF NOT EXISTS carrier_logs(id INTEGER PRIMARY KEY AUTOINCREMENT,order_id TEXT,tracking_number TEXT,status TEXT,last_update TEXT,note TEXT);
CREATE TABLE IF NOT EXISTS return_labels(id TEXT PRIMARY KEY,order_id TEXT UNIQUE,sku TEXT,label_url TEXT,status TEXT);
CREATE TABLE IF NOT EXISTS approval_tasks(id TEXT PRIMARY KEY,case_id TEXT,reason TEXT,status TEXT,audit_package TEXT);
CREATE TABLE IF NOT EXISTS audit_events(id INTEGER PRIMARY KEY AUTOINCREMENT,case_id TEXT,action TEXT,tool TEXT,before_state TEXT,after_state TEXT,reason TEXT,verification_status TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS investigation_requests(id TEXT PRIMARY KEY,case_id TEXT,question TEXT,status TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);CREATE INDEX IF NOT EXISTS idx_orders_product ON orders(product_name);CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(status);CREATE INDEX IF NOT EXISTS idx_payments_order ON payments(order_id);CREATE INDEX IF NOT EXISTS idx_shipments_order ON shipments(order_id);
"""
def connect(path: str|Path=DEFAULT_DB)->sqlite3.Connection:
    conn=sqlite3.connect(path);conn.row_factory=sqlite3.Row;conn.execute("PRAGMA foreign_keys=ON");return conn
def ensure_database(path: str|Path=DEFAULT_DB)->None:
    path=Path(path)
    if not path.exists():reset_database(path);return
    c=connect(path)
    has_v3=c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='products'").fetchone()
    c.close()
    # Earlier prototype schemas are simulation-only and cannot safely satisfy V3 foreign-key contracts.
    if not has_v3:reset_database(path);return
    c=connect(path);c.executescript(SCHEMA)
    # Lightweight forward-compatible upgrades for a local prototype database.
    columns={row[1] for row in c.execute("PRAGMA table_info(refunds)")}
    if "item_id" not in columns: c.execute("ALTER TABLE refunds ADD COLUMN item_id TEXT")
    if "quantity" not in columns: c.execute("ALTER TABLE refunds ADD COLUMN quantity INTEGER")
    c.commit();c.close()
def reset_database(path: str|Path=DEFAULT_DB,scenario: str="adaptation")->None:
    path=Path(path)
    if path.exists():path.unlink()
    c=connect(path);c.executescript(SCHEMA)
    customers=[("CUS-100","Alex Morgan","alex@example.test","GOLD","ACTIVE","12 Demo Lane"),("CUS-200","Jordan Lee","jordan@example.test","STANDARD","ACTIVE","45 Sample Road"),("CUS-300","Sam Patel","sam@example.test","STANDARD","ACTIVE","3 Test Street"),("CUS-400","Taylor Quinn","taylor@example.test","VIP","ACTIVE","7 Example Ave"),("CUS-500","Morgan Chen","morgan@example.test","STANDARD","ACTIVE","2 Market Street"),("CUS-600","Casey Rao","casey@example.test","STANDARD","ACTIVE","44 Hill Road"),("CUS-700","Robin Das","robin@example.test","GOLD","ACTIVE","15 Lake Road"),("CUS-800","Avery Shah","avery@example.test","STANDARD","ACTIVE","9 Centre Road")]
    products=[("PROD-HEAD","WH-100","Wireless Headphones","Audio",129.99,30),("PROD-SPEAK","SP-200","Portable Speaker","Audio",89.99,30),("PROD-CABLE","CB-300","USB-C Cable","Accessories",15,30),("PROD-LAP","LP-900","Creator Laptop","Computing",24999,30)]
    c.executemany("INSERT INTO customers VALUES(?,?,?,?,?,?)",customers);c.executemany("INSERT INTO products VALUES(?,?,?,?,?,?)",products);c.executemany("INSERT INTO warehouses VALUES(?,?,?,?)",[("WH-PRIMARY","Primary Warehouse","Mumbai",1),("WH-SECONDARY","Secondary Warehouse","Pune",1)])
    zero=0 if scenario=="adaptation" else 8
    c.executemany("INSERT INTO inventory VALUES(?,?,?,?,?,?,?)",[("PROD-HEAD","WH-PRIMARY",zero,0,0,2,"OUT_OF_STOCK" if zero==0 else "AVAILABLE"),("PROD-HEAD","WH-SECONDARY",0,0,0,2,"OUT_OF_STOCK"),("PROD-SPEAK","WH-PRIMARY",6,0,4,2,"AVAILABLE"),("PROD-SPEAK","WH-SECONDARY",4,0,0,2,"AVAILABLE"),("PROD-CABLE","WH-PRIMARY",40,0,20,5,"AVAILABLE"),("PROD-LAP","WH-PRIMARY",1,0,0,1,"AVAILABLE")])
    orders=[("ORD-1042","CUS-100","PROD-HEAD","Wireless Headphones","DELIVERED","2026-09-01","2026-09-08","PAID",129.99,1,1,0),("ORD-2042","CUS-200","PROD-SPEAK","Portable Speaker","DELIVERED","2026-09-01","2026-09-09","PAID",89.99,1,1,0),("ORD-3042","CUS-300","PROD-HEAD","Wireless Headphones","DELIVERED","2025-01-01","2025-01-10","PAID",129.99,0,0,0),("ORD-4042","CUS-400","PROD-CABLE","USB-C Cable","PROCESSING","2026-09-10",None,"PAID",15,1,1,1),("ORD-5042","CUS-500","PROD-SPEAK","Portable Speaker","SHIPPED","2026-09-05",None,"PAID",89.99,1,1,0),("ORD-6042","CUS-600","PROD-HEAD","Wireless Headphones","DELIVERED","2026-09-01","2026-09-08","PAID",129.99,1,1,0),("ORD-7042","CUS-700","PROD-CABLE","USB-C Cable","DELIVERED","2025-01-01","2025-01-10","PAID",15,0,0,0),("ORD-8042","CUS-800","PROD-LAP","Creator Laptop","DELIVERED","2026-09-01","2026-09-08","PAID",24999,1,1,0)]
    c.executemany("INSERT INTO orders VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",orders)
    for oid,cid,pid,_,_,_,_,_,amount,*_ in orders:
        suffix=oid[4:];c.execute("INSERT INTO order_items VALUES(?,?,?,?,?,?)",(f"ITEM-{suffix}",oid,pid,1,amount,"SP-200" if oid=="ORD-6042" else None));c.execute("INSERT INTO payments VALUES(?,?,?,?,?,?,?,?,?)",(f"PAY-{suffix}",oid,amount,"INR","CARD","PAYMENT_CAPTURED",0,f"TXN-{suffix}",f"AUTH-{suffix}"));c.execute("INSERT INTO shipments VALUES(?,?,?,?,?,?)",(f"SHP-{suffix}",oid,"Resolve Express","DELIVERED" if oid not in ("ORD-4042","ORD-5042") else ("PICKING" if oid=="ORD-4042" else "IN_TRANSIT"),f"RX{suffix}","2026-09-14"))
    cases=[("CASE-100","CUS-100","ORD-1042","DAMAGED_ITEM","Headphones arrived damaged; customer requested replacement","OPEN",None,"NORMAL",None),("CASE-200","CUS-200","ORD-2042","DUPLICATE_CHARGE","Customer reports duplicate card charge","OPEN",None,"NORMAL",None),("CASE-300","CUS-300","ORD-3042","EXPIRED_RETURN","Return requested after policy window","OPEN",None,"NORMAL",None),("CASE-400","CUS-400","ORD-4042","PRE_SHIPMENT_CANCELLATION","Cancel unfulfilled cable order","OPEN",None,"NORMAL",None),("CASE-500","CUS-500","ORD-5042","POST_SHIPMENT_CANCELLATION","Cancel order already in transit","OPEN",None,"NORMAL",None),("CASE-600","CUS-600","ORD-6042","WRONG_ITEM","Delivered item differs from packing manifest","OPEN",None,"HIGH",None),("CASE-700","CUS-700","ORD-7042","LOST_PARCEL","Package marked delivered but customer did not receive it","OPEN",None,"HIGH",None),("CASE-800","CUS-800","ORD-8042","HIGH_VALUE_FRAUD","High-value refund requires authorization review","OPEN",None,"HIGH",None)]
    c.executemany("INSERT INTO cases VALUES(?,?,?,?,?,?,?,?,?)",cases);c.execute("INSERT INTO payments VALUES(?,?,?,?,?,?,?,?,?)",("PAY-DUPE","ORD-2042",89.99,"INR","CARD","PAYMENT_CAPTURED",0,"TXN-DUPE","AUTH-2042"));c.executemany("INSERT INTO carrier_logs(order_id,tracking_number,status,last_update,note) VALUES(?,?,?,?,?)",[("ORD-5042","RX5042","IN_TRANSIT","2026-09-11","Customer cancellation after dispatch"),("ORD-7042","RX7042","DELIVERED","2026-09-09","Delivery scan older than 48 hours")]);c.commit();c.close()
