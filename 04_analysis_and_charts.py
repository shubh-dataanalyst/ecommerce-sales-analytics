"""
Step 4: Analysis (KPIs, RFM, cohorts, leakage) + charts.

Input : data/ecommerce.db (SQLite views from step 3)
Output: outputs/charts/*.png, outputs/*.csv, outputs/key_metrics.json
"""
import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.colors import LinearSegmentedColormap

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
CH = OUT / "charts"
CH.mkdir(parents=True, exist_ok=True)

# ----------------------------------------------------------------- style (validated default palette)
SURF, INK, INK2, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
GRID, AXIS = "#e1e0d9", "#c3c2b7"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"          # categorical slots 1-3
SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
CMAP = LinearSegmentedColormap.from_list("blue_seq", SEQ)

plt.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
    "font.family": "DejaVu Sans", "font.size": 10, "text.color": INK,
    "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.edgecolor": AXIS, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": False, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
})


def lakh(x, _=None):
    return f"₹{x / 1e5:,.0f}L"


def crore(x, _=None):
    return f"₹{x / 1e7:,.1f}Cr"


def heading(fig, title, sub=None):
    fig.text(0.012, 0.975, title, fontsize=13.5, fontweight="bold", color=INK, va="top")
    if sub:
        fig.text(0.012, 0.925, sub, fontsize=9.5, color=INK2, va="top")


def save(fig, name):
    fig.savefig(CH / name, dpi=160)
    plt.close(fig)


# ----------------------------------------------------------------- data
con = sqlite3.connect(ROOT / "data/ecommerce.db")
lines = pd.read_sql("SELECT * FROM v_lines", con, parse_dates=["order_date"])
orders = pd.read_sql("SELECT * FROM orders", con, parse_dates=["order_date"])
customers = pd.read_sql("SELECT * FROM customers", con, parse_dates=["signup_date"])
valid = lines[lines["status"].isin(["Delivered", "Shipped"])].copy()
valid["gp"] = valid["revenue"] - valid["cogs"]
M = {}  # key metrics

# ================================================================= 1. KPIs
n_orders = valid["order_id"].nunique()
M["kpi"] = {
    "revenue": float(valid["revenue"].sum()),
    "gross_profit": float(valid["gp"].sum()),
    "margin_pct": float(100 * valid["gp"].sum() / valid["revenue"].sum()),
    "orders": int(n_orders),
    "buyers": int(valid["customer_id"].nunique()),
    "aov": float(valid["revenue"].sum() / n_orders),
    "units": int(valid["quantity"].sum()),
}
# like-for-like YoY (Jan-Sep both years)
v = valid.assign(y=valid["order_date"].dt.year, m=valid["order_date"].dt.month)
ytd = v[v["m"] <= 9].groupby("y")["revenue"].sum()
M["kpi"]["ytd_2025"] = float(ytd[2025])
M["kpi"]["ytd_2026"] = float(ytd[2026])
M["kpi"]["yoy_growth_pct"] = float(100 * (ytd[2026] / ytd[2025] - 1))

# ================================================================= 2. Monthly trend
mon = (valid.groupby("order_month")
       .agg(revenue=("revenue", "sum"), gp=("gp", "sum"), orders=("order_id", "nunique")).reset_index())
mon["margin_pct"] = 100 * mon["gp"] / mon["revenue"]
mon["date"] = pd.to_datetime(mon["order_month"] + "-01")
mon.to_csv(OUT / "monthly_trend.csv", index=False)

fest = mon[mon["order_month"].isin(["2025-10", "2025-11"])]
rest = mon[(~mon["order_month"].isin(["2025-10", "2025-11"])) & (mon["order_month"] >= "2025-03")]
fest_m = 100 * fest["gp"].sum() / fest["revenue"].sum()
rest_m = 100 * rest["gp"].sum() / rest["revenue"].sum()
fl = valid[valid["order_month"].isin(["2025-10", "2025-11"])]
nl = valid[(~valid["order_month"].isin(["2025-10", "2025-11"])) & (valid["order_month"] >= "2025-03")]
M["festive"] = {"margin_festive": float(fest_m), "margin_rest": float(rest_m),
                "margin_drop_pts": float(rest_m - fest_m),
                "avg_discount_festive": float(fl["discount_pct"].mean()),
                "avg_discount_rest": float(nl["discount_pct"].mean()),
                "revenue_festive_2m": float(fest["revenue"].sum()),
                "gp_festive_2m": float(fest["gp"].sum())}
sep = mon[mon["order_month"] == "2025-09"].iloc[0]
M["festive"]["orders_change_vs_sep_pct"] = float(100 * (fest["orders"].mean() / sep["orders"] - 1))
M["festive"]["revenue_change_vs_sep_pct"] = float(100 * (fest["revenue"].mean() / sep["revenue"] - 1))
M["festive"]["gp_change_vs_sep_pct"] = float(100 * (fest["gp"].mean() / sep["gp"] - 1))

fig, (a1, a2) = plt.subplots(2, 1, figsize=(10, 6.4), sharex=True, gridspec_kw={"height_ratios": [2.2, 1]})
fig.subplots_adjust(top=0.84, bottom=0.08, left=0.08, right=0.97, hspace=0.12)
heading(fig, f"Festive discounts cut gross margin by ~{M['festive']['margin_drop_pts']:.0f} points in Oct–Nov",
        "Monthly revenue (valid orders) and gross margin %, Jan 2025 – Sep 2026")
span = (pd.Timestamp("2025-09-22"), pd.Timestamp("2025-11-09"))
for a in (a1, a2):
    a.axvspan(*span, color=GRID, alpha=0.7, lw=0)
    a.grid(axis="y")
a1.plot(mon["date"], mon["revenue"], color=BLUE, lw=2)
a1.scatter(mon["date"].iloc[-1], mon["revenue"].iloc[-1], s=50, color=BLUE, zorder=3, edgecolor=SURF, linewidth=2)
a1.yaxis.set_major_formatter(lakh)
a1.set_ylabel("Revenue / month")
a1.text(mon["date"].iloc[-1], mon["revenue"].iloc[-1] * 1.08, f"₹{mon['revenue'].iloc[-1] / 1e5:.0f}L",
        ha="right", fontsize=9.5, color=INK2)
a1.set_ylim(0, mon["revenue"].max() * 1.2)
a2.plot(mon["date"], mon["margin_pct"], color=BLUE, lw=2)
a2.set_ylim(20, 42)
a2.set_ylabel("Gross margin %")
a2.yaxis.set_major_formatter(lambda x, _: f"{x:.0f}%")
a2.text(pd.Timestamp("2025-10-15"), 21.2, f"Oct–Nov sale\n~{fest_m:.0f}% margin", ha="center", va="bottom", fontsize=9, color=INK2)
a2.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
a2.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
save(fig, "01_monthly_revenue_margin.png")

# ================================================================= 3. Category
cat = (valid.groupby("category").agg(revenue=("revenue", "sum"), gp=("gp", "sum"), units=("quantity", "sum"))
       .assign(margin_pct=lambda d: 100 * d["gp"] / d["revenue"], share=lambda d: 100 * d["revenue"] / d["revenue"].sum())
       .sort_values("revenue", ascending=False))
cat.to_csv(OUT / "category_summary.csv")
M["category"] = {"top_revenue": cat.index[0], "top_revenue_share": float(cat["share"].iloc[0]),
                 "top_margin": cat["margin_pct"].idxmax(), "top_margin_val": float(cat["margin_pct"].max()),
                 "low_margin": cat["margin_pct"].idxmin(), "low_margin_val": float(cat["margin_pct"].min()),
                 "electronics_margin": float(cat.loc["Electronics", "margin_pct"]),
                 "electronics_share": float(cat.loc["Electronics", "share"])}

fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 4.6), sharey=True)
fig.subplots_adjust(top=0.78, bottom=0.1, left=0.17, right=0.96, wspace=0.08)
heading(fig, f"{cat.index[0]} brings the most revenue at a {cat['margin_pct'].iloc[0]:.0f}% margin; "
             f"{cat['margin_pct'].idxmax()} earns {cat['margin_pct'].max():.0f}%",
        "Revenue and gross margin % by category (valid orders)")
y = np.arange(len(cat))
a1.barh(y, cat["revenue"], color=BLUE, height=0.62)
a1.set_yticks(y, cat.index)
a1.invert_yaxis()
a1.set_title("Revenue", loc="left", fontsize=10, color=INK2)
for i, val in enumerate(cat["revenue"]):
    a1.text(val + cat["revenue"].max() * 0.015, i, lakh(val), va="center", fontsize=9, color=INK2)
a1.set_xlim(0, cat["revenue"].max() * 1.22)
a1.xaxis.set_visible(False)
a1.spines["bottom"].set_visible(False)
a2.barh(y, cat["margin_pct"], color=BLUE, height=0.62)
a2.set_title("Gross margin %", loc="left", fontsize=10, color=INK2)
for i, val in enumerate(cat["margin_pct"]):
    a2.text(val + 0.8, i, f"{val:.1f}%", va="center", fontsize=9, color=INK2)
a2.set_xlim(0, cat["margin_pct"].max() * 1.2)
a2.xaxis.set_visible(False)
a2.spines["bottom"].set_visible(False)
a2.spines["left"].set_visible(False)
a2.tick_params(left=False)
save(fig, "02_category_revenue_vs_margin.png")

# ================================================================= 4. Discount bands
def band(d):
    return ("0%" if d == 0 else "5–10%" if d <= 10 else "15–20%" if d <= 20 else "25–30%" if d <= 30 else "35%+")


valid["band"] = valid["discount_pct"].map(band)
order_b = ["0%", "5–10%", "15–20%", "25–30%", "35%+"]
db = (valid.groupby("band").agg(revenue=("revenue", "sum"), gp=("gp", "sum"), lines=("revenue", "size"),
                                loss_lines=("gp", lambda s: int((s < 0).sum())), loss_amt=("gp", lambda s: float(s[s < 0].sum())))
      .reindex(order_b))
db["margin_pct"] = 100 * db["gp"] / db["revenue"]
db.to_csv(OUT / "discount_band_summary.csv")
heavy = db.loc[["25–30%", "35%+"]]
M["discount"] = {"margin_by_band": {k: float(v_) for k, v_ in db["margin_pct"].items()},
                 "loss_lines": int(db["loss_lines"].sum()),
                 "loss_amount": float(db["loss_amt"].sum()),
                 "heavy_share_of_lines_pct": float(100 * heavy["lines"].sum() / db["lines"].sum()),
                 "heavy_share_of_revenue_pct": float(100 * heavy["revenue"].sum() / db["revenue"].sum()),
                 "heavy_loss_lines_pct": float(100 * heavy["loss_lines"].sum() / heavy["lines"].sum())}

fig, ax = plt.subplots(figsize=(8.6, 4.6))
fig.subplots_adjust(top=0.78, bottom=0.14, left=0.09, right=0.97)
heading(fig, f"Margin falls from {db['margin_pct'].iloc[0]:.0f}% to {db['margin_pct'].iloc[-1]:.0f}% as discounts deepen from 0 to 35%+",
        "Gross margin % by discount band (valid order lines)")
x = np.arange(len(db))
ax.bar(x, db["margin_pct"], color=BLUE, width=0.58)
ax.set_xticks(x, db.index)
ax.set_xlabel("Discount given")
for i, (m_, ll, tot) in enumerate(zip(db["margin_pct"], db["loss_lines"], db["lines"])):
    ax.text(i, m_ + 0.8, f"{m_:.1f}%", ha="center", fontsize=10.5, color=INK)
    if ll:
        ax.text(i, m_ + 4.6, f"{ll:,} of {tot:,} lines\nsold at a loss", ha="center", va="bottom", fontsize=8.5, color=INK2)
ax.set_ylim(0, 50)
ax.yaxis.set_visible(False)
ax.spines["left"].set_visible(False)
save(fig, "03_discount_vs_margin.png")

# ================================================================= 5. Pareto
cr = valid.groupby("customer_id")["revenue"].sum().sort_values(ascending=False)
dec = pd.qcut(cr.rank(method="first", ascending=False), 10, labels=range(1, 11))
par = cr.groupby(dec, observed=True).sum()
par_pct = 100 * par / par.sum()
M["pareto"] = {"top10_pct": float(par_pct.iloc[0]), "top20_pct": float(par_pct.iloc[:2].sum()),
               "bottom50_pct": float(par_pct.iloc[5:].sum())}
fig, ax = plt.subplots(figsize=(8.6, 4.4))
fig.subplots_adjust(top=0.78, bottom=0.14, left=0.06, right=0.97)
heading(fig, f"Top 10% of customers bring {par_pct.iloc[0]:.0f}% of revenue",
        "Share of revenue by customer decile (1 = highest-spending 10% of buyers)")
ax.bar(range(10), par_pct.values, color=BLUE, width=0.62)
ax.set_xticks(range(10), [str(i) for i in range(1, 11)])
ax.set_xlabel("Customer decile")
for i, p in enumerate(par_pct.values):
    ax.text(i, p + 0.7, f"{p:.0f}%", ha="center", fontsize=9.5, color=INK2)
ax.yaxis.set_visible(False)
ax.spines["left"].set_visible(False)
ax.set_ylim(0, par_pct.max() * 1.15)
save(fig, "04_customer_pareto.png")

# ================================================================= 6. RFM
snap = valid["order_date"].max() + pd.Timedelta(days=1)
rfm = valid.groupby("customer_id").agg(last_order=("order_date", "max"), frequency=("order_id", "nunique"),
                                       monetary=("revenue", "sum"))
rfm["recency"] = (snap - rfm["last_order"]).dt.days
rfm["R"] = pd.qcut(rfm["recency"].rank(method="first"), 5, labels=[5, 4, 3, 2, 1]).astype(int)
rfm["F"] = pd.cut(rfm["frequency"], [0, 1, 2, 3, 5, np.inf], labels=[1, 2, 3, 4, 5]).astype(int)
rfm["M"] = pd.qcut(rfm["monetary"].rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)


def segment(r):
    if r.R >= 4 and r.F >= 4:
        return "Champions"
    if r.R >= 3 and r.F >= 3:
        return "Loyal"
    if r.R >= 4 and r.F <= 2:
        return "New / Promising"
    if r.R <= 2 and r.F >= 3:
        return "At Risk"
    if r.R <= 2 and r.F <= 2:
        return "Hibernating"
    return "Needs Attention"


rfm["segment"] = rfm.apply(segment, axis=1)
rfm.reset_index().to_csv(OUT / "rfm_customers.csv", index=False)
seg_order = ["Champions", "Loyal", "New / Promising", "Needs Attention", "At Risk", "Hibernating"]
rs = (rfm.groupby("segment").agg(customers=("monetary", "size"), revenue=("monetary", "sum"),
                                 avg_orders=("frequency", "mean"), avg_recency_days=("recency", "mean"),
                                 avg_spend=("monetary", "mean")).reindex(seg_order))
rs["customer_pct"] = 100 * rs["customers"] / rs["customers"].sum()
rs["revenue_pct"] = 100 * rs["revenue"] / rs["revenue"].sum()
rs.to_csv(OUT / "rfm_summary.csv")
M["rfm"] = {s: {"customers": int(r.customers), "customer_pct": float(r.customer_pct),
                "revenue_pct": float(r.revenue_pct), "avg_spend": float(r.avg_spend),
                "avg_recency_days": float(r.avg_recency_days)} for s, r in rs.iterrows()}
at_risk_rev = float(rs.loc["At Risk", "revenue"])
M["rfm"]["at_risk_historic_revenue"] = at_risk_rev

fig, ax = plt.subplots(figsize=(9.6, 5))
fig.subplots_adjust(top=0.78, bottom=0.08, left=0.16, right=0.97)
heading(fig, f"Champions ({rs.loc['Champions', 'customer_pct']:.0f}% of customers) bring {rs.loc['Champions', 'revenue_pct']:.0f}% of revenue; "
             f"At Risk hold another {rs.loc['At Risk', 'revenue_pct']:.0f}%",
        "Share of customers vs. share of lifetime revenue, by RFM segment")
y = np.arange(len(rs))
h = 0.36
ax.barh(y - h / 2, rs["customer_pct"], height=h, color=BLUE, label="% of customers")
ax.barh(y + h / 2, rs["revenue_pct"], height=h, color=ORANGE, label="% of revenue")
ax.set_yticks(y, rs.index)
ax.invert_yaxis()
for i, (c_, r_) in enumerate(zip(rs["customer_pct"], rs["revenue_pct"])):
    ax.text(c_ + 0.5, i - h / 2, f"{c_:.0f}%", va="center", fontsize=9, color=INK2)
    ax.text(r_ + 0.5, i + h / 2, f"{r_:.0f}%", va="center", fontsize=9, color=INK2)
ax.xaxis.set_visible(False)
ax.spines["bottom"].set_visible(False)
ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, frameon=False, fontsize=9, labelcolor=INK2)
save(fig, "05_rfm_segments.png")

# ================================================================= 7. Cohort retention
v2 = valid[["customer_id", "order_date"]].copy()
v2["om"] = v2["order_date"].dt.to_period("M")
first = v2.groupby("customer_id")["om"].min().rename("cohort")
act = v2[["customer_id", "om"]].drop_duplicates().join(first, on="customer_id")
act["n"] = [(a - b).n for a, b in zip(act["om"], act["cohort"])]
mat = act.groupby(["cohort", "n"])["customer_id"].nunique().unstack()
size = mat[0]
ret = mat.div(size, axis=0) * 100
last_m = v2["om"].max()
for c in ret.index:
    for n in ret.columns:
        if c + int(n) > last_m:
            ret.loc[c, n] = np.nan
ret.index = ret.index.astype(str)
ret.to_csv(OUT / "cohort_retention_matrix.csv")
sizes = size.copy()
sizes.index = sizes.index.astype(str)
big = sizes[sizes >= 40].index
cols = [c for c in range(0, 12) if c in ret.columns]
sub = ret.loc[big, cols]


def avg_ret(n):
    ok = sub[n].dropna()
    w = sizes.loc[ok.index]
    return float((ok * w).sum() / w.sum())


M["cohort"] = {"m1": avg_ret(1), "m3": avg_ret(3), "m6": avg_ret(6), "cohorts_used": int(len(big))}

fig, ax = plt.subplots(figsize=(10.5, 6.6))
fig.subplots_adjust(top=0.86, bottom=0.08, left=0.14, right=0.93)
heading(fig, f"About {M['cohort']['m1']:.0f}% of a cohort buys again in month 1; {M['cohort']['m6']:.0f}% are still buying in month 6",
        "Cohort retention: % of each first-purchase-month cohort that ordered in month N (cohorts with 40+ customers)")
im = ax.imshow(sub.values, cmap=CMAP, vmin=0, vmax=60, aspect="auto")
ax.set_xticks(range(len(cols)), [f"M{c}" for c in cols])
ax.set_yticks(range(len(sub)), [f"{i}  (n={int(sizes[i])})" for i in sub.index])
ax.xaxis.tick_top()
ax.tick_params(length=0)
for s in ax.spines.values():
    s.set_visible(False)
for i in range(sub.shape[0]):
    for j in range(sub.shape[1]):
        val = sub.values[i, j]
        if np.isnan(val):
            continue
        ax.text(j, i, f"{val:.0f}", ha="center", va="center", fontsize=8.5,
                color="#ffffff" if (val > 30 and j > 0) or j == 0 else INK)
cb = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
cb.outline.set_visible(False)
cb.ax.tick_params(labelsize=8, length=0)
cb.set_label("Retention %", fontsize=9, color=INK2)
save(fig, "06_cohort_retention.png")

# ================================================================= 8. Payment risk / leakage
pm = orders.groupby("payment_method").agg(orders=("order_id", "size"),
                                          cancel_pct=("status", lambda s: 100 * (s == "Cancelled").mean()),
                                          return_pct=("status", lambda s: 100 * (s == "Returned").mean()))
pm = pm.sort_values("cancel_pct", ascending=False)
pm.to_csv(OUT / "payment_risk.csv")
cod = orders[orders["payment_method"] == "COD"]
non = orders[~orders["payment_method"].isin(["COD", "Unknown"])]
cod_rate, non_rate = (cod["status"] == "Cancelled").mean(), (non["status"] == "Cancelled").mean()
excess_orders = (cod_rate - non_rate) * len(cod)
canc_cod_ids = cod.loc[cod["status"] == "Cancelled", "order_id"]
canc_cod_val = lines[lines["order_id"].isin(canc_cod_ids)].groupby("order_id")["revenue"].sum().mean()
all_lines_rev = lines["revenue"].sum()
leak = lines[lines["status"].isin(["Cancelled", "Returned"])].groupby("status")["revenue"].sum()
M["leakage"] = {"cancelled_rev": float(leak["Cancelled"]), "returned_rev": float(leak["Returned"]),
                "leak_pct_of_booked": float(100 * leak.sum() / all_lines_rev),
                "cod_cancel_pct": float(100 * cod_rate), "other_cancel_pct": float(100 * non_rate),
                "cod_excess_orders": float(excess_orders), "cod_excess_rev": float(excess_orders * canc_cod_val),
                "cod_share_of_orders_pct": float(100 * len(cod) / len(orders)),
                "return_rate_pct": float(100 * (orders["status"] == "Returned").mean()),
                "cancel_rate_pct": float(100 * (orders["status"] == "Cancelled").mean())}

fig, ax = plt.subplots(figsize=(8.8, 4.6))
fig.subplots_adjust(top=0.78, bottom=0.08, left=0.17, right=0.96)
heading(fig, f"Cash-on-delivery orders get cancelled {cod_rate / non_rate:.1f}x as often",
        "Cancellation rate % by payment method (all orders)")
y = np.arange(len(pm))
ax.barh(y, pm["cancel_pct"], color=BLUE, height=0.6)
ax.set_yticks(y, pm.index)
ax.invert_yaxis()
for i, (c_, n_) in enumerate(zip(pm["cancel_pct"], pm["orders"])):
    ax.text(c_ + 0.25, i, f"{c_:.1f}%   ({n_:,} orders)", va="center", fontsize=9, color=INK2)
ax.set_xlim(0, pm["cancel_pct"].max() * 1.5)
ax.xaxis.set_visible(False)
ax.spines["bottom"].set_visible(False)
save(fig, "07_payment_cancellations.png")

# ================================================================= 9. Cities + channel
city = (valid.groupby(["city", "region"]).agg(revenue=("revenue", "sum"), customers=("customer_id", "nunique"))
        .reset_index().sort_values("revenue", ascending=False))
city.to_csv(OUT / "city_summary.csv", index=False)
chan = pd.read_csv(OUT / "sql_results/channel_performance.csv")
chan_k = chan[chan["acquisition_channel"] != "Unknown"].sort_values("revenue_per_acquired_customer", ascending=False)
M["channel"] = {"best": chan_k.iloc[0]["acquisition_channel"], "worst": chan_k.iloc[-1]["acquisition_channel"],
                "spread_pct": float(100 * (chan_k["revenue_per_acquired_customer"].max()
                                           / chan_k["revenue_per_acquired_customer"].min() - 1)),
                "table": chan_k[["acquisition_channel", "customers_acquired", "conversion_pct",
                                 "revenue_per_acquired_customer"]].to_dict("records")}
M["top_cities"] = city.head(3)[["city", "revenue"]].to_dict("records")
M["top3_city_share_pct"] = float(100 * city.head(3)["revenue"].sum() / city["revenue"].sum())

fig, ax = plt.subplots(figsize=(8.8, 5.2))
fig.subplots_adjust(top=0.82, bottom=0.05, left=0.16, right=0.96)
heading(fig, f"Top 3 cities ({', '.join(city['city'].head(3))}) make up {M['top3_city_share_pct']:.0f}% of revenue",
        "Revenue by city (valid orders)")
y = np.arange(len(city))
ax.barh(y, city["revenue"], color=BLUE, height=0.62)
ax.set_yticks(y, city["city"])
ax.invert_yaxis()
for i, val in enumerate(city["revenue"]):
    ax.text(val + city["revenue"].max() * 0.01, i, lakh(val), va="center", fontsize=9, color=INK2)
ax.set_xlim(0, city["revenue"].max() * 1.14)
ax.xaxis.set_visible(False)
ax.spines["bottom"].set_visible(False)
save(fig, "08_city_revenue.png")

# ================================================================= 10. Misc metrics
oc = valid.groupby("customer_id")["order_id"].nunique()
M["repeat"] = {"repeat_rate_pct": float(100 * (oc > 1).mean()), "avg_orders": float(oc.mean()),
               "buyers": int(len(oc)), "signups": int(len(customers)),
               "signup_to_buyer_pct": float(100 * len(oc) / len(customers))}
dv = orders[orders["status"].isin(["Delivered", "Returned"]) & orders["delivery_days"].notna()]
dv_b = pd.cut(dv["delivery_days"], [0, 3, 5, 7, 30], labels=["1-3", "4-5", "6-7", "8+"])
M["delivery"] = {"avg_days": float(orders["delivery_days"].mean()),
                 "return_pct_by_bucket": {str(k): float(100 * (g["status"] == "Returned").mean())
                                          for k, g in dv.groupby(dv_b, observed=True)}}
top_prod = (valid.groupby(["product_name", "category"]).agg(revenue=("revenue", "sum"), gp=("gp", "sum")).reset_index()
            .sort_values("revenue", ascending=False))
M["top_product_share_pct"] = float(100 * top_prod["revenue"].iloc[0] / valid["revenue"].sum())
M["top10_products_share_pct"] = float(100 * top_prod["revenue"].head(10).sum() / valid["revenue"].sum())

with open(OUT / "key_metrics.json", "w") as f:
    json.dump(M, f, indent=2, default=str)
print(json.dumps(M, indent=2, default=str))
print("\ncharts:", sorted(p.name for p in CH.iterdir()))
