"""Run every SQL file in queries/ against marketplace.db, save CSVs and draw charts.

Usage:
    python generate_data.py     # builds marketplace.db (once)
    python run_analysis.py      # writes results/*.csv and results/*.png
"""
import sqlite3
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import pandas as pd

ROOT = Path(__file__).parent
DB_PATH = ROOT / "marketplace.db"
QUERY_DIR = ROOT / "queries"
RESULTS = ROOT / "results"

# Chart palette: one blue hue (sequential), neutral ink for all text.
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
SURFACE, GRID, BASELINE = "#fcfcfb", "#e1e0d9", "#c3c2b7"
BLUE = "#2a78d6"
SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "text.color": INK, "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED,
    "font.family": "sans-serif", "font.size": 10, "axes.titleweight": "bold",
    "axes.titlesize": 12, "axes.titlelocation": "left",
})


def tidy(ax, grid_axis="y"):
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(BASELINE)
    ax.tick_params(length=0)
    ax.grid(axis=grid_axis, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def run_queries():
    out = {}
    with sqlite3.connect(DB_PATH) as con:
        for path in sorted(QUERY_DIR.glob("*.sql")):
            df = pd.read_sql_query(path.read_text(), con)
            df.to_csv(RESULTS / f"{path.stem}.csv", index=False)
            out[path.stem] = df
            print(f"\n=== {path.stem} ===")
            print(df.to_string(index=False))
    return out


def chart_gmv(df):
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.plot(df.month, df.gmv, color=BLUE, linewidth=2, marker="o", markersize=6,
            markerfacecolor=BLUE, markeredgecolor=SURFACE, markeredgewidth=1.5)
    for i in {int(df.gmv.idxmax()), len(df) - 1}:
        ax.annotate(f"€{df.gmv[i]:,.0f}", (df.month[i], df.gmv[i]), textcoords="offset points",
                    xytext=(0, 10), ha="center", color=INK, fontsize=9, fontweight="bold")
    ax.set_title("Monthly GMV (completed orders)")
    ax.set_xticks(range(0, len(df), 3))
    ax.set_xticklabels(df.month[::3])
    ax.yaxis.set_major_formatter(lambda v, _: f"€{v / 1000:.0f}k")
    ax.set_ylim(0, df.gmv.max() * 1.18)
    tidy(ax)
    fig.tight_layout()
    fig.savefig(RESULTS / "gmv_trend.png", dpi=150)
    plt.close(fig)


def chart_cohorts(df):
    d = df[df.months_since >= 1]
    pivot = d.pivot(index="cohort_month", columns="months_since", values="retention_pct")
    sizes = df[df.months_since == 0].set_index("cohort_month").cohort_buyers
    labels = [f"{m}  (n={sizes[m]:,})" for m in pivot.index]
    cmap = LinearSegmentedColormap.from_list("blue_seq", SEQ)
    fig, ax = plt.subplots(figsize=(8, 0.42 * len(pivot) + 1.6))
    vmax = float(pivot.max().max())
    ax.imshow(pivot.values, cmap=cmap, vmin=0, vmax=vmax, aspect="auto")
    ax.set_xticks(range(pivot.shape[1]))
    ax.set_xticklabels([f"+{c}" for c in pivot.columns])
    ax.set_yticks(range(len(pivot)))
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlabel("Months after first purchase")
    ax.set_title("Repeat-purchase rate by first-purchase cohort (%)")
    for (r, c), v in pd.DataFrame(pivot.values).stack().items():
        ax.text(c, r, f"{v:.1f}", ha="center", va="center", fontsize=8,
                color="#ffffff" if v > 0.6 * vmax else INK)
    for side in ax.spines.values():
        side.set_visible(False)
    ax.tick_params(length=0)
    fig.tight_layout()
    fig.savefig(RESULTS / "cohort_retention.png", dpi=150)
    plt.close(fig)


def bar_chart(df, label_col, value_col, title, fname, horizontal=False, unit="%"):
    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    if horizontal:
        df = df.iloc[::-1]
        ax.barh(df[label_col], df[value_col], color=BLUE, height=0.55)
        for y, v in enumerate(df[value_col]):
            ax.text(v + df[value_col].max() * 0.015, y, f"{v:.1f}{unit}", va="center",
                    color=INK, fontsize=9, fontweight="bold")
        ax.set_xlim(0, df[value_col].max() * 1.15)
        ax.xaxis.set_visible(False)
        tidy(ax, grid_axis="x")
        ax.grid(False)
    else:
        ax.bar(df[label_col], df[value_col], color=BLUE, width=0.55)
        for x, v in enumerate(df[value_col]):
            ax.text(x, v + df[value_col].max() * 0.02, f"{v:.1f}{unit}", ha="center",
                    color=INK, fontsize=9, fontweight="bold")
        ax.set_ylim(0, df[value_col].max() * 1.15)
        ax.yaxis.set_visible(False)
        tidy(ax)
        ax.grid(False)
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(RESULTS / fname, dpi=150)
    plt.close(fig)


def main():
    if not DB_PATH.exists():
        sys.exit("marketplace.db not found - run `python generate_data.py` first.")
    RESULTS.mkdir(exist_ok=True)
    r = run_queries()
    chart_gmv(r["01_monthly_gmv"])
    chart_cohorts(r["05_buyer_cohort_retention"])
    bar_chart(r["06_channel_conversion"], "acquisition_channel", "conversion_30d_pct",
              "Signup-to-first-purchase conversion within 30 days, by channel",
              "channel_conversion.png", horizontal=True)
    sell = r["07_sell_through_by_price_band"].copy()
    sell["price_band"] = sell.price_band.str.replace(r"^\d\) ", "", regex=True)
    sell["price_band"] = sell.price_band.str.replace("under 10", "under €10").map(
        lambda s: f"€{s}" if s[0].isdigit() else s)
    bar_chart(sell, "price_band", "sell_through_30d_pct",
              "30-day sell-through rate by list-price band", "sell_through_by_price.png")
    print("\nSaved CSVs and charts to results/")


if __name__ == "__main__":
    main()
