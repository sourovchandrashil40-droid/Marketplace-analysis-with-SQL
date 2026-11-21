"""Generate a reproducible, synthetic second-hand marketplace dataset (SQLite).

Everything here is simulated. There is no real company or customer data.
Tables: users, items, orders. Re-running with the same SEED gives identical data.

Patterns deliberately built in (so the analysis has something to find):
  - user/listing growth over time, plus a Nov-Dec seasonal peak
  - categories differ in price level and how fast they sell
  - cheaper items and budget brands sell faster
  - acquisition channels differ in how likely users are to buy
  - a small share of sellers produce most of the listings
  - buyers are active for a limited period after signup, so retention decays
"""
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
START, END = "2025-01-01", "2026-10-31"
N_USERS, N_ITEMS = 8_000, 40_000
DB_PATH = Path(__file__).parent / "marketplace.db"

COUNTRIES = ["LT", "DE", "FR", "PL", "NL"]
COUNTRY_P = [0.30, 0.25, 0.20, 0.15, 0.10]
CHANNELS = ["organic", "paid_social", "referral", "search"]
CHANNEL_P = [0.40, 0.25, 0.15, 0.20]
CHANNEL_BUY = {"organic": 1.0, "paid_social": 0.55, "referral": 1.6, "search": 0.9}

# category: (median list price EUR, base 30-day sell-through, share of listings)
CATEGORIES = {
    "Women's clothing": (14, 0.34, 0.34),
    "Men's clothing": (16, 0.26, 0.14),
    "Shoes": (24, 0.28, 0.14),
    "Kids": (9, 0.38, 0.14),
    "Home": (18, 0.21, 0.10),
    "Accessories": (20, 0.24, 0.09),
    "Electronics": (55, 0.15, 0.05),
}
TIERS = ["budget", "mid", "premium"]
TIER_P = [0.50, 0.35, 0.15]
TIER_PRICE = {"budget": 0.7, "mid": 1.0, "premium": 2.2}
TIER_SELL = {"budget": 1.10, "mid": 1.0, "premium": 0.80}
TIER_DISCOUNT = {"budget": 0.92, "mid": 0.88, "premium": 0.83}  # mean share of list price paid
SEASON = {1: 1.10, 2: 0.95, 3: 1.0, 4: 1.0, 5: 1.0, 6: 0.95,
          7: 0.90, 8: 0.90, 9: 1.05, 10: 1.10, 11: 1.25, 12: 1.30}

SCHEMA = """
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS items;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    user_id             INTEGER PRIMARY KEY,
    signup_date         TEXT NOT NULL,           -- YYYY-MM-DD
    country             TEXT NOT NULL,
    acquisition_channel TEXT NOT NULL
);
CREATE TABLE items (
    item_id    INTEGER PRIMARY KEY,
    seller_id  INTEGER NOT NULL REFERENCES users(user_id),
    category   TEXT NOT NULL,
    brand_tier TEXT NOT NULL,                    -- budget / mid / premium
    list_price REAL NOT NULL,                    -- EUR
    listed_at  TEXT NOT NULL                     -- YYYY-MM-DD
);
CREATE TABLE orders (
    order_id   INTEGER PRIMARY KEY,
    item_id    INTEGER NOT NULL UNIQUE REFERENCES items(item_id),
    buyer_id   INTEGER NOT NULL REFERENCES users(user_id),
    order_date TEXT NOT NULL,                    -- YYYY-MM-DD
    sale_price REAL NOT NULL,                    -- EUR actually paid
    status     TEXT NOT NULL CHECK (status IN ('completed', 'cancelled', 'refunded'))
);
CREATE INDEX idx_items_seller   ON items(seller_id);
CREATE INDEX idx_items_listed   ON items(listed_at);
CREATE INDEX idx_orders_buyer   ON orders(buyer_id);
CREATE INDEX idx_orders_date    ON orders(order_date);
"""


def day_weights(days):
    """Sampling weights per day: linear growth x monthly seasonality."""
    t = np.linspace(0, 1, len(days))
    months = pd.DatetimeIndex(days).month
    w = (1 + 1.5 * t) * np.array([SEASON[m] for m in months])
    return w / w.sum()


def make_users(rng, days):
    idx = rng.choice(len(days), size=N_USERS, p=day_weights(days))
    return pd.DataFrame({
        "user_id": np.arange(1, N_USERS + 1),
        "signup_date": np.sort(days[idx]),  # older users get lower ids
        "country": rng.choice(COUNTRIES, size=N_USERS, p=COUNTRY_P),
        "acquisition_channel": rng.choice(CHANNELS, size=N_USERS, p=CHANNEL_P),
    })


def make_items(rng, users, days):
    sellers = users[rng.random(len(users)) < 0.35]
    w = rng.lognormal(0, 1.2, len(sellers))  # heavy tail: few power sellers
    pos = rng.choice(len(sellers), size=N_ITEMS, p=w / w.sum())
    seller_signup = sellers.signup_date.values[pos]
    listed = days[rng.choice(len(days), size=N_ITEMS, p=day_weights(days))]
    cats = list(CATEGORIES)
    category = rng.choice(cats, size=N_ITEMS, p=[CATEGORIES[c][2] for c in cats])
    tier = rng.choice(TIERS, size=N_ITEMS, p=TIER_P)
    price = (np.array([CATEGORIES[c][0] for c in category])
             * np.array([TIER_PRICE[t] for t in tier])
             * rng.lognormal(0, 0.55, N_ITEMS))
    return pd.DataFrame({
        "item_id": np.arange(1, N_ITEMS + 1),
        "seller_id": sellers.user_id.values[pos],
        "category": category,
        "brand_tier": tier,
        "list_price": np.maximum(2.0, np.round(price * 2) / 2),
        "listed_at": np.maximum(listed, seller_signup),  # can't list before signing up
    })


def simulate_sales(rng, items):
    """Decide which items sell and when. Unsold-by-END items simply have no order."""
    base = np.array([CATEGORIES[c][1] for c in items.category])
    price_eff = (20 / items.list_price.values) ** 0.15           # cheaper sells faster
    tier_eff = items.brand_tier.map(TIER_SELL).values
    season = np.array([SEASON[m] for m in pd.DatetimeIndex(items.listed_at).month])
    p30 = np.clip(base * price_eff * tier_eff * season, 0.02, 0.85)
    p_ever = np.clip(p30 / 0.70, 0, 0.92)  # ~70% of eventual sales happen within 30 days
    sells = rng.random(len(items)) < p_ever
    delay = np.maximum(1, np.ceil(rng.exponential(30 / -np.log(0.30), len(items)))).astype(int)
    order_date = items.listed_at.values + delay.astype("timedelta64[D]")
    sold = items[sells & (order_date <= np.datetime64(END))].copy()
    sold["order_date"] = order_date[sells & (order_date <= np.datetime64(END))]
    return sold


def assign_buyers(rng, users, sold):
    """Pick a buyer per order: weighted by channel propensity.

    A buyer must have signed up already and still be 'active': most users buy only for
    a limited, random period after signup (mean ~75 days), while ~12% stay active
    long-term. This is what makes retention decay in the cohort analysis.
    """
    act = users.acquisition_channel.map(CHANNEL_BUY).values * rng.lognormal(0, 0.9, len(users))
    cum = np.cumsum(act / act.sum())
    signup, uid = users.signup_date.values, users.user_id.values  # signup sorted ascending
    lifetime = np.where(rng.random(len(users)) < 0.12, 5000.0,
                        rng.exponential(75, len(users)))
    churn = signup + np.ceil(lifetime).astype(int).astype("timedelta64[D]")
    n_elig = np.searchsorted(signup, sold.order_date.values, side="right")
    buyer = np.full(len(sold), -1)
    pending = np.arange(len(sold))
    for _ in range(60):  # redraw when the buyer is the seller or already churned
        hi = cum[n_elig[pending] - 1]
        pos = np.searchsorted(cum, rng.random(len(pending)) * hi, side="right")
        pos = np.minimum(pos, n_elig[pending] - 1)
        ok = (uid[pos] != sold.seller_id.values[pending]) & (churn[pos] >= sold.order_date.values[pending])
        buyer[pending[ok]] = uid[pos[ok]]
        pending = pending[~ok]
        if len(pending) == 0:
            break
    sold = sold.assign(buyer_id=buyer)
    return sold[sold.buyer_id > 0].copy()


def make_orders(rng, sold):
    disc = np.clip(rng.normal(sold.brand_tier.map(TIER_DISCOUNT).values, 0.06), 0.5, 1.0)
    return pd.DataFrame({
        "item_id": sold.item_id.values,
        "buyer_id": sold.buyer_id.values,
        "order_date": sold.order_date.values,
        "sale_price": np.round(sold.list_price.values * disc, 2),
        "status": rng.choice(["completed", "cancelled", "refunded"], size=len(sold),
                             p=[0.93, 0.04, 0.03]),
    }).sort_values(["order_date", "item_id"]).reset_index(drop=True)


def iso(df, cols):
    out = df.copy()
    for c in cols:
        out[c] = pd.to_datetime(out[c]).dt.strftime("%Y-%m-%d")
    return out


def main():
    rng = np.random.default_rng(SEED)
    days = pd.date_range(START, END).values.astype("datetime64[ns]")
    users = make_users(rng, days)
    items = make_items(rng, users, days)
    sold = assign_buyers(rng, users, simulate_sales(rng, items))
    orders = make_orders(rng, sold)
    orders.insert(0, "order_id", np.arange(1, len(orders) + 1))

    with sqlite3.connect(DB_PATH) as con:
        con.executescript(SCHEMA)
        iso(users, ["signup_date"]).to_sql("users", con, if_exists="append", index=False)
        iso(items, ["listed_at"]).to_sql("items", con, if_exists="append", index=False)
        iso(orders, ["order_date"]).to_sql("orders", con, if_exists="append", index=False)

    print(f"Wrote {DB_PATH.name}: {len(users):,} users, {len(items):,} items, {len(orders):,} orders")
    print(orders.status.value_counts().to_string())


if __name__ == "__main__":
    main()
