"""
Step 2: Data cleaning pipeline.

Rule of thumb in industry: raw data kabhi overwrite nahi karte. data/raw -> data/clean.
Har fix ka log rakhte hain taaki stakeholders ko bata sako "kitna data kharab tha aur humne kya kiya".
"""
import re
import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW, CLEAN, REPORTS = ROOT / "data/raw", ROOT / "data/clean", ROOT / "reports"
CLEAN.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)

log = []  # (table, issue, rows_affected, action)


def note(table, issue, n, action):
    log.append((table, issue, int(n), action))


def parse_mixed_dates(s: pd.Series) -> pd.Series:
    """Format detect karke parse karta hai (ambiguous dd/mm vs mm-dd avoid karne ke liye regex se)."""
    s = s.astype(str).str.strip()
    out = pd.Series(pd.NaT, index=s.index, dtype="datetime64[ns]")
    patterns = [
        (r"^\d{4}-\d{2}-\d{2}$", "%Y-%m-%d"),
        (r"^\d{2}/\d{2}/\d{4}$", "%d/%m/%Y"),
        (r"^\d{2}-\d{2}-\d{4}$", "%m-%d-%Y"),
        (r"^\d{2} [A-Za-z]{3} \d{4}$", "%d %b %Y"),
        (r"^\d{2}-[A-Za-z]{3}-\d{4}$", "%d-%b-%Y"),
    ]
    for rx, fmt in patterns:
        mask = s.str.match(rx)
        out.loc[mask] = pd.to_datetime(s[mask], format=fmt, errors="coerce")
    return out


# =============================================================== CUSTOMERS
cust = pd.read_csv(RAW / "customers.csv", dtype=str)
n0 = len(cust)

d = cust.duplicated().sum()
cust = cust.drop_duplicates()
note("customers", "Exact duplicate rows", d, "Dropped")
d = cust.duplicated("customer_id").sum()
cust = cust.drop_duplicates("customer_id", keep="first")
note("customers", "Duplicate customer_id", d, "Kept first")

# city standardisation
city_raw = cust["city"].copy()
cust["city"] = cust["city"].str.strip().str.title()
cust["city"] = cust["city"].replace({"Bangalore": "Bengaluru", "Gurugram": "Gurgaon", "Bombay": "Mumbai"})
note("customers", "City casing / spaces / alias (Bangalore, Gurugram, Bombay)", (city_raw != cust["city"]).sum(),
     "strip + title case + alias map")

CITY_MAP = {"Mumbai": ("Maharashtra", "West"), "Pune": ("Maharashtra", "West"), "Ahmedabad": ("Gujarat", "West"),
            "Delhi": ("Delhi", "North"), "Gurgaon": ("Haryana", "North"), "Lucknow": ("Uttar Pradesh", "North"),
            "Jaipur": ("Rajasthan", "North"), "Bengaluru": ("Karnataka", "South"), "Hyderabad": ("Telangana", "South"),
            "Chennai": ("Tamil Nadu", "South"), "Kochi": ("Kerala", "South"), "Kolkata": ("West Bengal", "East"),
            "Patna": ("Bihar", "East"), "Bhubaneswar": ("Odisha", "East")}
cust["state"] = cust["city"].map(lambda c: CITY_MAP.get(c, (None, None))[0])
cust["region"] = cust["city"].map(lambda c: CITY_MAP.get(c, (None, None))[1])
note("customers", "Unmapped city after cleaning", cust["region"].isna().sum(), "Should be 0")

# gender
g_raw = cust["gender"].copy()
cust["gender"] = (cust["gender"].str.strip().str.lower()
                  .map({"male": "Male", "m": "Male", "female": "Female", "f": "Female", "other": "Other"})
                  .fillna("Unknown"))
note("customers", "Gender variants / missing", (g_raw.fillna("") != cust["gender"]).sum(), "Standardised, missing -> 'Unknown'")

# channel
blank = cust["acquisition_channel"].fillna("").str.strip().eq("").sum()
cust["acquisition_channel"] = cust["acquisition_channel"].fillna("").str.strip().replace("", "Unknown")
note("customers", "Missing acquisition_channel", blank, "-> 'Unknown'")

# age
cust["age"] = pd.to_numeric(cust["age"], errors="coerce")
bad_age = ((cust["age"] < 18) | (cust["age"] > 80)).sum()
cust.loc[(cust["age"] < 18) | (cust["age"] > 80), "age"] = np.nan
note("customers", "Invalid age (<18 or >80)", bad_age, "Set to NaN")
miss_age = cust["age"].isna().sum()
cust["age_group"] = pd.cut(cust["age"], [17, 24, 34, 44, 54, 80],
                           labels=["18-24", "25-34", "35-44", "45-54", "55+"]).astype(object).fillna("Unknown")
note("customers", "Missing/invalid age total", miss_age, "Kept NaN (no imputation), age_group='Unknown'")

# dates
cust["signup_date"] = parse_mixed_dates(cust["signup_date"])
note("customers", "Unparseable signup_date", cust["signup_date"].isna().sum(), "Should be 0")
cust = cust[["customer_id", "signup_date", "city", "state", "region", "gender", "age", "age_group", "acquisition_channel"]]

# =============================================================== PRODUCTS
prod = pd.read_csv(RAW / "products.csv")
cat_raw = prod["category"].copy()
canon = {"electronics": "Electronics", "fashion": "Fashion", "home & kitchen": "Home & Kitchen",
         "beauty": "Beauty", "grocery": "Grocery", "sports": "Sports"}
prod["category"] = prod["category"].str.strip().str.lower().map(canon)
note("products", "Category casing / trailing spaces", (cat_raw != prod["category"]).sum(), "Mapped to canonical names")
miss_cost = prod["cost_price"].isna().sum()
ratio = (prod["cost_price"] / prod["mrp"]).groupby(prod["category"]).median()
prod["cost_price"] = prod["cost_price"].fillna(prod["mrp"] * prod["category"].map(ratio)).round(2)
note("products", "Missing cost_price", miss_cost, "Imputed = mrp x category median cost/mrp ratio")

# =============================================================== ORDERS
ords = pd.read_csv(RAW / "orders.csv", dtype=str)
d = ords.duplicated().sum()
ords = ords.drop_duplicates()
note("orders", "Exact duplicate rows", d, "Dropped")
d = ords.duplicated("order_id").sum()
ords = ords.drop_duplicates("order_id", keep="first")
note("orders", "Duplicate order_id", d, "Kept first")

ords["order_date"] = parse_mixed_dates(ords["order_date"])
note("orders", "Mixed date formats parsed (4 formats)", ords["order_date"].notna().sum(), "Parsed via regex-detected formats")
note("orders", "Unparseable order_date", ords["order_date"].isna().sum(), "Should be 0")

st_raw = ords["status"].copy()
ords["status"] = ords["status"].str.strip().str.title()
note("orders", "Status casing / trailing spaces", (st_raw != ords["status"]).sum(), "strip + title case")

pm = ords["payment_method"].isna().sum()
ords["payment_method"] = ords["payment_method"].fillna("Unknown")
note("orders", "Missing payment_method", pm, "-> 'Unknown'")

ords["delivery_days"] = pd.to_numeric(ords["delivery_days"], errors="coerce")
bad_dd = ((ords["delivery_days"] <= 0) | (ords["delivery_days"] > 30)).sum()
ords.loc[(ords["delivery_days"] <= 0) | (ords["delivery_days"] > 30), "delivery_days"] = np.nan
note("orders", "Invalid delivery_days (<=0 or >30)", bad_dd, "Set to NaN (excluded from delivery KPIs)")

orph_mask = ~ords["customer_id"].isin(cust["customer_id"])
ords[orph_mask].to_csv(CLEAN / "rejected_orders_orphan_customers.csv", index=False)
note("orders", "Orphan orders (customer_id not in customers)", orph_mask.sum(), "Removed, saved to rejected_*.csv")
ords = ords[~orph_mask]

# =============================================================== ORDER ITEMS
items = pd.read_csv(RAW / "order_items.csv")
d = items.duplicated().sum()
items = items.drop_duplicates()
note("order_items", "Exact duplicate rows", d, "Dropped")
d = items.duplicated(["order_id", "product_id"]).sum()
items = items.drop_duplicates(["order_id", "product_id"], keep="first")
note("order_items", "Duplicate (order_id, product_id)", d, "Kept first")

neg = (items["quantity"] <= 0).sum()
items = items[items["quantity"] > 0]
note("order_items", "Quantity <= 0", neg, "Removed")
big = (items["quantity"] > 50).sum()
items = items[items["quantity"] <= 50]
note("order_items", "Quantity outliers (>50, fat-finger)", big, "Removed")

miss_price = items["unit_price"].isna().sum()
items = items.merge(prod[["product_id", "mrp"]], on="product_id", how="left")
items["unit_price"] = items["unit_price"].fillna((items["mrp"] * (1 - items["discount_pct"] / 100)).round(2))
items = items.drop(columns="mrp")
note("order_items", "Missing unit_price", miss_price, "Recomputed = mrp x (1 - discount%)")

orph_i = ~items["order_id"].isin(ords["order_id"])
note("order_items", "Items whose order was removed/missing", orph_i.sum(), "Removed (referential integrity)")
items = items[~orph_i]
unk_p = ~items["product_id"].isin(prod["product_id"])
note("order_items", "Unknown product_id", unk_p.sum(), "Should be 0")
items = items[~unk_p]

# orders with no items -> drop
no_items = ~ords["order_id"].isin(items["order_id"])
note("orders", "Orders with no line items", no_items.sum(), "Removed")
ords = ords[~no_items]

# =============================================================== SAVE
cust.to_csv(CLEAN / "customers.csv", index=False)
prod.to_csv(CLEAN / "products.csv", index=False)
ords.to_csv(CLEAN / "orders.csv", index=False)
items.to_csv(CLEAN / "order_items.csv", index=False)

# =============================================================== QUALITY REPORT
rep = pd.DataFrame(log, columns=["Table", "Issue", "Rows affected", "Action"])
rep.to_csv(CLEAN / "data_quality_log.csv", index=False)
lines = ["# Data Quality Report", "",
         "| Table | Issue found | Rows affected | Action taken |", "|---|---|---:|---|"]
for t, i, n, a in log:
    lines.append(f"| {t} | {i} | {n:,} | {a} |")
lines += ["", "## Row counts: raw vs clean", "", "| Table | Raw | Clean |", "|---|---:|---:|"]
for name, df in [("customers", cust), ("products", prod), ("orders", ords), ("order_items", items)]:
    raw_n = len(pd.read_csv(RAW / f"{name}.csv"))
    lines.append(f"| {name} | {raw_n:,} | {len(df):,} |")
(REPORTS / "data_quality_report.md").write_text("\n".join(lines))

print(rep.to_string(index=False))
print()
for name, df in [("customers", cust), ("products", prod), ("orders", ords), ("order_items", items)]:
    print(f"{name:12s} clean rows: {len(df):,}")
