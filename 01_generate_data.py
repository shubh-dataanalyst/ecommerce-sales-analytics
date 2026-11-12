"""
Step 1: Raw data generation.

Real projects me data company ke database / API se aata hai. Humare paas wo nahi hai,
isliye ek realistic e-commerce (India) dataset simulate kar rahe hain, jisme jaan-boojhkar
wahi problems daali hain jo real data me hoti hain:
  - duplicate rows
  - missing values
  - mixed date formats
  - inconsistent text (case, extra spaces, spelling variants)
  - invalid / outlier values

Output: data/raw/customers.csv, products.csv, orders.csv, order_items.csv
"""
import numpy as np
import pandas as pd
from pathlib import Path

RNG = np.random.default_rng(42)
OUT = Path(__file__).resolve().parents[1] / "data" / "raw"
OUT.mkdir(parents=True, exist_ok=True)

START, END = pd.Timestamp("2025-01-01"), pd.Timestamp("2026-09-30")
N_CUSTOMERS = 6000
N_PRODUCTS = 220

# ----------------------------------------------------------------- locations
CITIES = {  # city: (state, region, weight)
    "Mumbai": ("Maharashtra", "West", 12), "Pune": ("Maharashtra", "West", 7),
    "Ahmedabad": ("Gujarat", "West", 5), "Delhi": ("Delhi", "North", 13),
    "Gurgaon": ("Haryana", "North", 5), "Lucknow": ("Uttar Pradesh", "North", 4),
    "Jaipur": ("Rajasthan", "North", 4), "Bengaluru": ("Karnataka", "South", 13),
    "Hyderabad": ("Telangana", "South", 9), "Chennai": ("Tamil Nadu", "South", 8),
    "Kochi": ("Kerala", "South", 3), "Kolkata": ("West Bengal", "East", 7),
    "Patna": ("Bihar", "East", 3), "Bhubaneswar": ("Odisha", "East", 2),
}
city_names = list(CITIES)
city_w = np.array([CITIES[c][2] for c in city_names], dtype=float)
city_w /= city_w.sum()

# ----------------------------------------------------------------- customers
channels = ["Organic Search", "Paid Ads", "Social Media", "Referral", "Email", "Direct"]
channel_w = [0.28, 0.25, 0.20, 0.10, 0.07, 0.10]

signup_days = (END - START).days
signup = START + pd.to_timedelta(RNG.integers(0, signup_days, N_CUSTOMERS), unit="D")

customers = pd.DataFrame({
    "customer_id": [f"C{100000 + i}" for i in range(N_CUSTOMERS)],
    "signup_date": signup,
    "city": RNG.choice(city_names, N_CUSTOMERS, p=city_w),
    "gender": RNG.choice(["Male", "Female", "Other"], N_CUSTOMERS, p=[0.52, 0.46, 0.02]),
    "age": np.clip(RNG.normal(32, 9, N_CUSTOMERS), 18, 70).round().astype(int),
    "acquisition_channel": RNG.choice(channels, N_CUSTOMERS, p=channel_w),
})
customers["state"] = customers["city"].map(lambda c: CITIES[c][0])
customers["region"] = customers["city"].map(lambda c: CITIES[c][1])

# ----------------------------------------------------------------- products
CATALOG = {  # category: (subcats, price_low, price_high, margin_low, margin_high)
    "Electronics": (["Mobile Accessories", "Audio", "Wearables", "Laptop Accessories"], 400, 9000, 0.10, 0.22),
    "Fashion": (["Men Clothing", "Women Clothing", "Footwear", "Accessories"], 300, 4000, 0.30, 0.50),
    "Home & Kitchen": (["Cookware", "Decor", "Storage", "Appliances"], 250, 6000, 0.22, 0.40),
    "Beauty": (["Skincare", "Haircare", "Makeup", "Fragrance"], 150, 2500, 0.35, 0.55),
    "Grocery": (["Snacks", "Beverages", "Staples", "Organic"], 60, 900, 0.08, 0.18),
    "Sports": (["Fitness", "Outdoor", "Yoga", "Cycling"], 300, 7000, 0.20, 0.38),
}
cat_names = list(CATALOG)
rows = []
for i in range(N_PRODUCTS):
    cat = cat_names[i % len(cat_names)]
    subs, plo, phi, mlo, mhi = CATALOG[cat]
    mrp = round(float(np.exp(RNG.uniform(np.log(plo), np.log(phi)))) / 10) * 10
    mrp = max(mrp, 49)
    margin = RNG.uniform(mlo, mhi)
    rows.append({
        "product_id": f"P{2000 + i}",
        "product_name": f"{cat.split()[0]} Item {i + 1}",
        "category": cat,
        "sub_category": RNG.choice(subs),
        "mrp": mrp,
        "cost_price": round(mrp * (1 - margin - 0.12), 2),  # cost vs selling (~12% avg discount)
    })
products = pd.DataFrame(rows)
# popularity weights (few bestsellers, long tail)
pop = RNG.pareto(2.8, N_PRODUCTS) + 1
pop = pop / pop.sum()

# ----------------------------------------------------------------- orders
# month seasonality (festive season Oct-Nov, Dec, small bump Jan sale)
month_boost = {1: 1.05, 2: 0.9, 3: 0.95, 4: 0.9, 5: 0.95, 6: 0.9, 7: 1.0,
               8: 1.1, 9: 1.1, 10: 1.6, 11: 1.5, 12: 1.25}
# customers have "activity" level -> repeat behaviour
activity = RNG.gamma(1.2, 1.0, N_CUSTOMERS)
activity = activity / activity.mean()
BASE_GAP = 38.0   # avg days between orders for an average customer (before seasonal thinning)
MEAN_LIFETIME = 280.0  # avg days a customer stays active before churning

order_rows = []
oid = 500000
for idx, c in customers.iterrows():
    if RNG.random() > 0.74:          # ~26% of signups never buy
        continue
    # first order shortly after signup, then renewal process with churn.
    # Same behaviour for every cohort => cohort retention is comparable across cohorts.
    t = c["signup_date"] + pd.Timedelta(days=int(RNG.integers(0, 10)))
    stop = min(END, t + pd.Timedelta(days=float(RNG.exponential(MEAN_LIFETIME))))
    gap_mean = BASE_GAP / activity[idx]
    first = True
    while t <= stop:
        # seasonality: slow months drop some orders, festive months keep nearly all
        if first or RNG.random() < month_boost[t.month] / 1.6:
            order_rows.append((f"O{oid}", c["customer_id"], t.normalize()))
            oid += 1
        first = False
        t = t + pd.Timedelta(days=float(RNG.exponential(gap_mean)) + 1)

orders = pd.DataFrame(order_rows, columns=["order_id", "customer_id", "order_date"])
orders = orders.sort_values("order_date").reset_index(drop=True)
n_orders = len(orders)

orders["payment_method"] = RNG.choice(
    ["UPI", "Credit Card", "Debit Card", "Net Banking", "COD", "Wallet"], n_orders,
    p=[0.38, 0.20, 0.14, 0.07, 0.17, 0.04])
orders["status"] = RNG.choice(["Delivered", "Cancelled", "Returned", "Shipped"], n_orders,
                              p=[0.82, 0.07, 0.08, 0.03])
# COD has higher cancellations
cod_mask = (orders["payment_method"] == "COD") & (RNG.random(n_orders) < 0.08)
orders.loc[cod_mask, "status"] = "Cancelled"
orders["delivery_days"] = np.clip(RNG.normal(4.2, 1.8, n_orders), 1, 14).round().astype(int)
orders["coupon_used"] = RNG.choice(["Y", "N"], n_orders, p=[0.31, 0.69])

# ----------------------------------------------------------------- order items
item_rows = []
for oid_, od in zip(orders["order_id"], orders["order_date"]):
    k = RNG.choice([1, 2, 3, 4], p=[0.55, 0.28, 0.12, 0.05])
    picks = RNG.choice(N_PRODUCTS, k, replace=False, p=pop)
    for p in picks:
        prod = products.iloc[p]
        disc = float(RNG.choice([0, 5, 10, 15, 20, 30], p=[0.30, 0.15, 0.22, 0.15, 0.13, 0.05]))
        if od.month in (10, 11):
            disc = min(disc + 10, 40)
        qty = int(RNG.choice([1, 2, 3, 4, 5], p=[0.68, 0.18, 0.08, 0.04, 0.02]))
        unit_price = round(prod["mrp"] * (1 - disc / 100), 2)
        item_rows.append((oid_, prod["product_id"], qty, unit_price, disc))
order_items = pd.DataFrame(item_rows, columns=["order_id", "product_id", "quantity", "unit_price", "discount_pct"])

# =================================================================== DIRTY IT UP
dirty_log = {}

# --- customers
c = customers.copy()
# 1. city text issues
m = RNG.random(len(c)) < 0.12
c.loc[m, "city"] = c.loc[m, "city"].str.upper()
m = RNG.random(len(c)) < 0.08
c.loc[m, "city"] = " " + c.loc[m, "city"].str.lower() + "  "
m = RNG.random(len(c)) < 0.04
c.loc[m, "city"] = c.loc[m, "city"].replace({"Bengaluru": "Bangalore", "Gurgaon": "Gurugram", "Mumbai": "Bombay"})
# 2. missing values
c.loc[RNG.random(len(c)) < 0.07, "age"] = np.nan
c.loc[RNG.random(len(c)) < 0.03, "gender"] = None
c.loc[RNG.random(len(c)) < 0.02, "acquisition_channel"] = ""
# 3. invalid ages
bad = RNG.choice(len(c), 25, replace=False)
c.loc[bad, "age"] = RNG.choice([0, 5, 150, 999, -1], 25)
# 4. gender spelling variants
m = RNG.random(len(c)) < 0.05
c.loc[m & (c["gender"] == "Male"), "gender"] = "M"
c.loc[m & (c["gender"] == "Female"), "gender"] = "female"
# 5. mixed signup date formats
fmt = RNG.choice(["%Y-%m-%d", "%d/%m/%Y", "%d-%b-%Y"], len(c), p=[0.7, 0.2, 0.1])
c["signup_date"] = [d.strftime(f) for d, f in zip(c["signup_date"], fmt)]
# 6. duplicate customer rows
dups = c.sample(60, random_state=1)
c = pd.concat([c, dups], ignore_index=True).sample(frac=1, random_state=2).reset_index(drop=True)

# --- products
p = products.copy()
p.loc[RNG.choice(len(p), 6, replace=False), "cost_price"] = np.nan
p.loc[RNG.choice(len(p), 4, replace=False), "category"] = ["electronics", "FASHION", "home & kitchen", "Beauty "]

# --- orders
o = orders.copy()
fmt = RNG.choice(["%Y-%m-%d", "%d/%m/%Y", "%m-%d-%Y", "%d %b %Y"], len(o), p=[0.65, 0.2, 0.05, 0.10])
o["order_date"] = [d.strftime(f) for d, f in zip(o["order_date"], fmt)]
o["status"] = o["status"].where(RNG.random(len(o)) > 0.10, o["status"].str.upper())
o["status"] = o["status"].where(RNG.random(len(o)) > 0.04, o["status"].str.lower() + " ")
o.loc[RNG.random(len(o)) < 0.04, "payment_method"] = None
o.loc[RNG.random(len(o)) < 0.015, "delivery_days"] = -1  # bad entries
o.loc[RNG.random(len(o)) < 0.005, "delivery_days"] = 90  # outliers
# orders for unknown customers (orphans)
orph = RNG.choice(len(o), 40, replace=False)
o.loc[orph, "customer_id"] = [f"C{900000 + i}" for i in range(40)]
# duplicates
o = pd.concat([o, o.sample(180, random_state=3)], ignore_index=True).sample(frac=1, random_state=4).reset_index(drop=True)

# --- order items
oi = order_items.copy()
oi.loc[RNG.choice(len(oi), 30, replace=False), "quantity"] = -1
oi.loc[RNG.choice(len(oi), 12, replace=False), "quantity"] = 500  # fat-finger outliers
oi.loc[RNG.choice(len(oi), 80, replace=False), "unit_price"] = np.nan
oi = pd.concat([oi, oi.sample(150, random_state=5)], ignore_index=True)

c.to_csv(OUT / "customers.csv", index=False)
p.to_csv(OUT / "products.csv", index=False)
o.to_csv(OUT / "orders.csv", index=False)
oi.to_csv(OUT / "order_items.csv", index=False)

print("customers :", c.shape)
print("products  :", p.shape)
print("orders    :", o.shape)
print("order_items:", oi.shape)
print("Saved to", OUT)
