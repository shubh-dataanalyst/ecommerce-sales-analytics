"""
Step 5 (project add-on): A/B test data.

Experiment: ShopKart ne checkout page par ek naya banner lagaya: "Free delivery above Rs 999".
  Group A (control)  = purana page
  Group B (variant)  = naya banner wala page
Visitors ko random 50/50 baanta gaya, 14 din (1-14 Sep 2026) tak chala.
Output: data/raw/ab_test.csv
"""
import numpy as np
import pandas as pd
from pathlib import Path

RNG = np.random.default_rng(7)
N = 12000
OUT = Path(__file__).resolve().parents[1] / "data" / "raw"

group = RNG.choice(["A", "B"], N)
device = RNG.choice(["Mobile", "Desktop", "Tablet"], N, p=[0.68, 0.28, 0.04])
visit_date = pd.Timestamp("2026-09-01") + pd.to_timedelta(RNG.integers(0, 14, N), unit="D")

base = np.select([device == "Mobile", device == "Desktop"], [0.036, 0.048], default=0.040)
p_conv = base * np.where(group == "B", 1.18, 1.0)
converted = (RNG.random(N) < p_conv).astype(int)

order_value = RNG.lognormal(np.log(2300), 0.55, N) * np.where(group == "B", 1.04, 1.0)
revenue = np.where(converted == 1, order_value.round(0), 0)

df = pd.DataFrame({
    "visitor_id": [f"V{300000 + i}" for i in range(N)],
    "visit_date": visit_date.strftime("%Y-%m-%d"),
    "group": group,
    "device": device,
    "converted": converted,
    "revenue": revenue.astype(int),
})

# thodi gandagi (real data jaisa)
df.loc[RNG.choice(N, 90, replace=False), "device"] = None
idx = RNG.choice(N, 120, replace=False)
df.loc[idx, "group"] = df.loc[idx, "group"].str.lower()
df = pd.concat([df, df.sample(40, random_state=1)], ignore_index=True).sample(frac=1, random_state=2)

df.to_csv(OUT / "ab_test.csv", index=False)
print(df.shape)
g = df.assign(g=df["group"].str.upper()).drop_duplicates("visitor_id")
print(g.groupby("g")["converted"].agg(["size", "mean"]))
