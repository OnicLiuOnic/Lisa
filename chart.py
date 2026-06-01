#!/usr/bin/env python3
"""
TrendSpider-style stock chart generator.

Produces a dark-themed weekly candlestick chart that mimics the TrendSpider look:
  - green/red candlesticks
  - volume bars
  - an "Analyst Estimates History" step line
  - a Volume-by-Price (VbP) histogram on the right
  - a center watermark + branding + price/date axes
  - a "Wall Street Analyst High" annotation

Data:
  Pass --data path/to/file.csv (or .json) with columns/keys:
      Date, Open, High, Low, Close, Volume
  If no data file is given, realistic ONDS-shaped sample data is generated so you
  can see the result immediately. (Live data feeds such as Yahoo Finance are
  blocked in some sandboxes; feed your own file when that happens.)

Usage:
  python3 chart.py                          # sample ONDS chart -> chart.png
  python3 chart.py --ticker ONDS --out onds.png
  python3 chart.py --data my_prices.csv --ticker ONDS --analyst-high 22.5
"""

import argparse
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrow
import matplotlib.dates as mdates

# ----------------------------------------------------------------------------
# Theme (TrendSpider-like dark palette)
# ----------------------------------------------------------------------------
BG          = "#0b1018"   # page background (near-black navy)
PANEL       = "#0b1018"   # plot panel background
GRID        = "#1b2230"   # subtle grid lines
TEXT        = "#c7cdd6"   # default text
TEXT_DIM    = "#5c6675"   # dimmed text
UP          = "#3ad07a"   # bullish candle / volume green
DOWN        = "#ef4d56"   # bearish candle / volume red
UP_VOL      = "#26344a"   # volume bars (muted slate)
ANALYST     = "#2fbf4f"   # analyst estimate step line (green)
WICK        = "#9aa4b2"   # candle wick


def make_sample_data(n_weeks=53, seed=7):
    """Generate weekly OHLCV resembling the ONDS run-up shown in the reference."""
    rng = np.random.default_rng(seed)
    end = pd.Timestamp("2026-05-25")
    dates = pd.date_range(end=end, periods=n_weeks, freq="W-MON")

    # Target close path: ~2.4 -> spike ~15 (Jan) -> pullback ~9-10 -> spike 13.22
    x = np.linspace(0, 1, n_weeks)
    base = (
        2.4
        + 11.0 * np.clip((x - 0.10) / 0.50, 0, 1) ** 1.6 * np.exp(-3.5 * np.clip(x - 0.62, 0, 1))
        + 7.5 * np.clip((x - 0.58) / 0.10, 0, 1) * np.exp(-2.0 * np.clip(x - 0.62, 0, 1))
    )
    base = np.clip(base, 2.2, None)
    noise = rng.normal(0, 0.22, n_weeks).cumsum() * 0.0
    close = base + rng.normal(0, 0.35, n_weeks)
    close = np.clip(close, 1.5, None)
    close[-1] = 13.22  # match the highlighted last price

    opens = np.empty(n_weeks)
    opens[0] = close[0] * 0.97
    opens[1:] = close[:-1] * (1 + rng.normal(0, 0.015, n_weeks - 1))
    highs = np.maximum(opens, close) * (1 + np.abs(rng.normal(0.04, 0.03, n_weeks)))
    lows = np.minimum(opens, close) * (1 - np.abs(rng.normal(0.04, 0.03, n_weeks)))

    vol = np.abs(rng.normal(1.0, 0.4, n_weeks)) * 1e7
    vol[-1] *= 1.8  # big final-week volume

    return pd.DataFrame(
        {"Open": opens, "High": highs, "Low": lows, "Close": close, "Volume": vol},
        index=dates,
    )


def load_data(path):
    if path.lower().endswith(".json"):
        df = pd.read_json(path)
    else:
        df = pd.read_csv(path)
    cols = {c.lower(): c for c in df.columns}
    date_col = cols.get("date", df.columns[0])
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.set_index(date_col).sort_index()
    df = df.rename(columns={cols.get(k, k): k.capitalize()
                            for k in ["open", "high", "low", "close", "volume"]})
    return df[["Open", "High", "Low", "Close", "Volume"]]


def build_chart(df, ticker="ONDS", subtitle="ONDAS", analyst_high=None, out="chart.png"):
    n = len(df)
    idx = np.arange(n)
    o, h, l, c = df["Open"].values, df["High"].values, df["Low"].values, df["Close"].values
    vol = df["Volume"].values
    up = c >= o

    pmax = max(h.max(), analyst_high or 0) * 1.06
    pmin = 0.0

    fig = plt.figure(figsize=(12.3, 9.0), dpi=100, facecolor=BG)
    gs = fig.add_gridspec(2, 1, height_ratios=[3.05, 1.0], hspace=0.06,
                          left=0.012, right=0.915, top=0.985, bottom=0.065)
    axp = fig.add_subplot(gs[0]); axv = fig.add_subplot(gs[1], sharex=axp)

    for ax in (axp, axv):
        ax.set_facecolor(PANEL)
        for s in ax.spines.values():
            s.set_visible(False)
        ax.grid(True, color=GRID, linewidth=0.6, alpha=0.6)
        ax.tick_params(colors=TEXT_DIM, length=0, labelsize=9)
        ax.yaxis.tick_right(); ax.yaxis.set_label_position("right")

    # ---- candlesticks ----
    cw = 0.62
    for i in range(n):
        col = UP if up[i] else DOWN
        axp.plot([i, i], [l[i], h[i]], color=col, linewidth=0.9, zorder=3)
        lo, hi = (o[i], c[i]) if up[i] else (c[i], o[i])
        axp.add_patch(Rectangle((i - cw / 2, lo), cw, max(hi - lo, pmax * 0.0008),
                                facecolor=col, edgecolor=col, linewidth=0.5, zorder=4))

    # ---- analyst estimate step line ----
    est = build_analyst_line(c, analyst_high)
    axp.step(idx, est, where="post", color=ANALYST, linewidth=1.8, zorder=5)

    # ---- Volume-by-Price histogram (right side) ----
    draw_vbp(axp, h, l, c, vol, up, n, pmin, pmax)

    # ---- Wall Street Analyst High annotation ----
    if analyst_high:
        axp.annotate("Wall Street Analyst High",
                     xy=(n - 1, analyst_high), xytext=(n * 0.80, analyst_high * 0.96),
                     color=ANALYST, fontsize=10, fontweight="bold", ha="left", va="center")

    # ---- last price tag ----
    axp.annotate(f"{c[-1]:.2f}", xy=(n - 1, c[-1]), xytext=(6, 0),
                 textcoords="offset points", va="center", ha="left", fontsize=9.5,
                 fontweight="bold", color="#0b1018",
                 bbox=dict(boxstyle="round,pad=0.25", fc=UP, ec="none"), zorder=10,
                 annotation_clip=False)

    axp.set_xlim(-1, n + n * 0.18)
    axp.set_ylim(pmin, pmax)
    axp.set_yticks(np.arange(0, pmax + 2.5, 2.5))
    axp.set_yticklabels([f"{v:.2f}" for v in np.arange(0, pmax + 2.5, 2.5)])

    # ---- volume panel ----
    axv.bar(idx, vol, width=cw, color=np.where(up, UP_VOL, "#3a2330"), zorder=3)
    axv.set_ylim(0, vol.max() * 1.25)
    axv.set_yticks([])

    # ---- x axis: month labels ----
    set_month_ticks(axv, df.index, n)

    # ---- text overlays / branding ----
    add_overlays(fig, axp, ticker, subtitle)

    fig.savefig(out, facecolor=BG)
    plt.close(fig)
    return out


def build_analyst_line(close, analyst_high):
    """A coarse step line that tracks price then projects to the analyst high."""
    n = len(close)
    est = close.copy().astype(float)
    step = max(n // 12, 1)
    for i in range(0, n, step):
        est[i:i + step] = close[i:i + step].max()
    if analyst_high:
        tail = max(int(n * 0.30), 1)
        est[-tail:] = analyst_high
        est[-1] = analyst_high * 0.99
    return est


def draw_vbp(ax, h, l, c, vol, up, n, pmin, pmax):
    bins = 48
    edges = np.linspace(pmin, pmax, bins + 1)
    centers = (edges[:-1] + edges[1:]) / 2
    up_v = np.zeros(bins); dn_v = np.zeros(bins)
    for i in range(n):
        b = np.clip(np.searchsorted(edges, c[i]) - 1, 0, bins - 1)
        (up_v if up[i] else dn_v)[b] += vol[i]
    tot = up_v + dn_v
    if tot.max() == 0:
        return
    maxw = n * 0.165
    scale = maxw / tot.max()
    x0 = n + n * 0.012
    bh = (edges[1] - edges[0]) * 0.92
    for k in range(bins):
        if tot[k] <= 0:
            continue
        uw, dw = up_v[k] * scale, dn_v[k] * scale
        ax.add_patch(Rectangle((x0, centers[k] - bh / 2), uw, bh,
                               facecolor=UP, alpha=0.55, edgecolor="none", zorder=2))
        ax.add_patch(Rectangle((x0 + uw, centers[k] - bh / 2), dw, bh,
                               facecolor=DOWN, alpha=0.55, edgecolor="none", zorder=2))


def set_month_ticks(ax, dates, n):
    months, labels = [], []
    last = None
    for i, d in enumerate(dates):
        key = (d.year, d.month)
        if key != last:
            months.append(i)
            labels.append(d.strftime("%b '%y"))
            last = key
    # drop the leading partial month if it crowds the next label
    if len(months) > 1 and months[1] - months[0] < 3:
        months, labels = months[1:], labels[1:]
    ax.set_xticks(months)
    ax.set_xticklabels(labels, fontsize=8.5)


def add_overlays(fig, axp, ticker, subtitle):
    # TrendSpider logo (text stand-in)
    fig.text(0.022, 0.965, "TrendSpider", color="#ffffff", fontsize=15,
             fontweight="bold")
    # legend block top-left
    fig.text(0.022, 0.935, f"{ticker}, Weekly, Candles chart", color=TEXT,
             fontsize=9.5, fontweight="bold")
    fig.text(0.022, 0.915, "Volume", color=TEXT, fontsize=9)
    fig.text(0.022, 0.898, "VbP", color="#3a4658", fontsize=9)
    fig.text(0.022, 0.881, "Analyst Estimates History (120)", color=ANALYST, fontsize=9)

    # center watermark
    axp.text(0.5, 0.78, subtitle, transform=axp.transAxes, ha="center", va="center",
             color="#ffffff", fontsize=40, fontweight="bold", alpha=0.92)
    axp.text(0.5, 0.70, f"{ticker} WEEKLY", transform=axp.transAxes, ha="center",
             va="center", color="#ffffff", fontsize=18, fontweight="light",
             alpha=0.9, family="monospace")

    # footer
    fig.text(0.022, 0.02, "©2026 TrendSpider", color=TEXT_DIM, fontsize=8.5)
    fig.text(0.905, 0.075, "Your local time zone", color=TEXT_DIM, fontsize=8,
             ha="right")


def main():
    ap = argparse.ArgumentParser(description="TrendSpider-style chart generator")
    ap.add_argument("--data", help="CSV/JSON file with Date,Open,High,Low,Close,Volume")
    ap.add_argument("--ticker", default="ONDS")
    ap.add_argument("--subtitle", default="ONDAS", help="center watermark label")
    ap.add_argument("--analyst-high", type=float, default=22.5,
                    help="Wall Street analyst high price target")
    ap.add_argument("--out", default="chart.png")
    args = ap.parse_args()

    df = load_data(args.data) if args.data else make_sample_data()
    out = build_chart(df, ticker=args.ticker, subtitle=args.subtitle,
                      analyst_high=args.analyst_high, out=args.out)
    print(f"Wrote {out}  ({len(df)} bars)")


if __name__ == "__main__":
    main()
