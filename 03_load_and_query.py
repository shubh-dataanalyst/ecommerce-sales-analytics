"""
Step 3: Clean CSVs -> SQLite warehouse -> run business SQL -> save result tables.
Real jobs me ye step Snowflake / BigQuery / Postgres pe hota hai; SQL logic same rehta hai.
"""
import re
import sqlite3
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data/clean"
DB = ROOT / "data/ecommerce.db"
OUT = ROOT / "outputs/sql_results"
OUT.mkdir(parents=True, exist_ok=True)

if DB.exists():
    DB.unlink()
con = sqlite3.connect(DB)

# ---- load tables with proper types
for name, dates in [("customers", ["signup_date"]), ("products", []), ("orders", ["order_date"]), ("order_items", [])]:
    df = pd.read_csv(CLEAN / f"{name}.csv", parse_dates=dates)
    for d in dates:
        df[d] = df[d].dt.strftime("%Y-%m-%d")
    df.to_sql(name, con, index=False)
    print(f"loaded {name:12s} {len(df):>7,} rows")

# ---- indexes (JOIN speed)
con.executescript("""
CREATE INDEX idx_orders_cust  ON orders(customer_id);
CREATE INDEX idx_orders_date  ON orders(order_date);
CREATE INDEX idx_items_order  ON order_items(order_id);
CREATE INDEX idx_items_prod   ON order_items(product_id);
""")

# ---- views
con.executescript((ROOT / "sql/00_views.sql").read_text())

# ---- run named queries
text = (ROOT / "sql/01_analysis_queries.sql").read_text()
blocks = re.split(r"^-- name:\s*(\w+)\s*$", text, flags=re.M)[1:]
for name, sql in zip(blocks[0::2], blocks[1::2]):
    df = pd.read_sql_query(sql.strip().rstrip(";"), con)
    df.to_csv(OUT / f"{name}.csv", index=False)
    print(f"\n=== {name} ({len(df)} rows) ===")
    print(df.head(12).to_string(index=False))

con.close()
