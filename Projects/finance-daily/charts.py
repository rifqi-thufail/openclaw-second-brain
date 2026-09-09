#!/usr/bin/env python3
"""Generate JPM/GS-style charts. Analogous palette, SPY + JCI highlighted. Output: output/charts/*.png"""
import json, os, datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE = os.path.dirname(os.path.abspath(__file__))
# Analogous palette: blue -> teal -> green (similar hues, distinct lightness)
ANALOGOUS = ["#0b3d91", "#1456a8", "#1f6fb2", "#2a8cbf", "#35a6b8", "#45bfa3", "#6ccfa8", "#8fdca9"]
SPY_COLOR = "#e8a020"   # amber, highlight S&P 500 (SPY)
JCI_COLOR = "#c1292e"   # red, highlight Jakarta Composite (JCI)
GRID = "#d9d9d9"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9,
    "axes.edgecolor": "#666666", "axes.linewidth": 0.6,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.5,
    "axes.spines.top": False, "axes.spines.right": False,
    "figure.facecolor": "white", "axes.facecolor": "white",
})

def load():
    date = datetime.date.today().isoformat()
    with open(os.path.join(BASE, "data", f"markets_{date}.json")) as f:
        return json.load(f)

def bar_color(sym, name):
    if sym in ("^GSPC", "SPY"):
        return SPY_COLOR
    if sym == "^JKSE":
        return JCI_COLOR
    return ANALOGOUS[0]

def chart_change(m, path):
    items = sorted(m["markets"].items(), key=lambda kv: kv[1]["chg_pct"])
    names = [v["name"] for _, v in items]
    vals = [v["chg_pct"] for _, v in items]
    colors = [bar_color(sym, v["name"]) for sym, v in items]
    fig, ax = plt.subplots(figsize=(8.4, 4.0))
    bars = ax.barh(names, vals, color=colors, height=0.62)
    for b, v in zip(bars, vals):
        ax.text(v + (0.08 if v >= 0 else -0.08), b.get_y() + b.get_height() / 2,
                f"{v:+.2f}%", va="center", ha="left" if v >= 0 else "right", fontsize=8)
    ax.axvline(0, color="#333333", linewidth=0.8)
    ax.set_xlabel("Daily change (%)")
    ax.set_title("Index performance, latest close (SPY and JCI highlighted)", fontsize=10, fontweight="bold", loc="left")
    fig.tight_layout(); fig.savefig(path, dpi=150); plt.close(fig)

def line_color(sym, i):
    if sym in ("^GSPC", "SPY"):
        return SPY_COLOR
    if sym == "^JKSE":
        return JCI_COLOR
    return ANALOGOUS[min(i % 4, 3)]


def chart_weekly_change(m, path):
    """Indonesia-focus weekly comparison: % change vs baseline ~1 week prior."""
    import os
    items = sorted(m["markets"].items(), key=lambda kv: kv[1].get("wk_chg_pct", kv[1]["chg_pct"]))
    names, vals, colors = [], [], []
    for sym, v in items:
        if "wk_chg_pct" not in v:
            continue
        names.append(v["name"])
        vals.append(v["wk_chg_pct"])
        colors.append(SPY_COLOR if sym in ("^GSPC", "SPY") else (JCI_COLOR if sym == "^JKSE" else ANALOGOUS[0]))
    if not names:
        return
    fig, ax = plt.subplots(figsize=(8.4, 4.0))
    bars = ax.barh(names, vals, color=colors, height=0.62)
    for b, v in zip(bars, vals):
        ax.text(v + (0.08 if v >= 0 else -0.08), b.get_y() + b.get_height() / 2,
                f"{v:+.2f}%", va="center", ha="left" if v >= 0 else "right", fontsize=8)
    ax.axvline(0, color="#333333", linewidth=0.8)
    ax.set_xlabel("Weekly change (%) ~5 sessions")
    ax.set_title("Weekly index performance (JCI highlighted)", fontsize=10, fontweight="bold", loc="left")
    fig.tight_layout(); fig.savefig(path, dpi=150); plt.close(fig)


def chart_weekly_trend(m, path):
    """Indonesia-focus: indexed 5-session trend, JCI + present peers."""
    picks = ["^JKSE", "^GSPC", "^STI", "^KLSE", "^N225", "^HSI"]
    fig, ax = plt.subplots(figsize=(8.4, 3.6))
    for i, sym in enumerate(picks):
        if sym not in m["series"]:
            continue
        s = m["series"][sym]
        ax.plot(range(len(s["norm"])), s["norm"], label=s["name"],
                color=line_color(sym, i), linewidth=1.8 if sym in ("^JKSE", "^GSPC") else 1.3)
    days = m["series"].get("^JKSE", {}).get("days") or next(iter(m["series"].values()))["days"]
    ax.set_xticks(range(len(days)))
    ax.set_xticklabels([d[5:] for d in days])
    ax.set_ylabel("Indexed to 100")
    ax.set_title("Indonesia Focus: 5-session trend, JCI vs peers", fontsize=10, fontweight="bold", loc="left")
    ax.legend(fontsize=7.5, frameon=False, ncol=3, loc="upper left")
    fig.tight_layout(); fig.savefig(path, dpi=150); plt.close(fig)

def chart_trend(m, path):
    fig, ax = plt.subplots(figsize=(8.4, 3.6))
    picks = ["^GSPC", "^N225", "^HSI", "^STI", "^KLSE", "^JKSE"]
    for i, sym in enumerate(picks):
        if sym not in m["series"]:
            continue
        s = m["series"][sym]
        ax.plot(range(len(s["norm"])), s["norm"], label=s["name"],
                color=line_color(sym, i), linewidth=1.6 if sym in ("^GSPC", "^JKSE") else 1.2)
    days = m["series"].get("^GSPC", {}).get("days") or list(m["series"].values())[0]["days"]
    ax.set_xticks(range(len(days)))
    ax.set_xticklabels([d[5:] for d in days])
    ax.set_ylabel("Indexed to 100")
    ax.set_title("5-day relative performance (SPY and JCI highlighted)", fontsize=10, fontweight="bold", loc="left")
    ax.legend(fontsize=7.5, frameon=False, ncol=3, loc="upper left")
    fig.tight_layout(); fig.savefig(path, dpi=150); plt.close(fig)

def chart_rupiah(m, path):
    """Indonesia-focus rupiah panel: USD/IDR level (down = stronger IDR)."""
    fx = m.get("fx")
    if not fx or "days" not in fx:
        return False
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(8.4, 4.2), sharex=True,
                                 gridspec_kw={"height_ratios": [3, 1], "hspace": 0.15})
    # level + weekly indexed strength
    a1.plot(range(len(fx["days"])), fx["norm"], color=JCI_COLOR, linewidth=2.0)
    a1.axhline(100, color=GRID, linewidth=0.8, linestyle="--")
    a1.set_ylabel("USD/IDR (indexed)")
    a1.set_title("Indonesia Focus: Rupiah (USD/IDR) weekly move", fontsize=10,
                 fontweight="bold", loc="left")
    labs = [f"{v:+,.1f}%" if abs(v)>0.01 else "0" for v in fx["norm"] ]
    for i, v in enumerate(fx["norm"]):
        a1.annotate(f"{v-100:+.2f}%", (i, v), textcoords="offset points",
                    xytext=(0, 7), ha="center", fontsize=7.5, color="#333333")
    wk = fx["wk_chg_pct"]; dy = fx["chg_pct"]; close = fx["close"]
    a2.text(0.01, 0.5, f"{close:,.0f} IDR/USD  |  day {dy:+.2f}%  |  week {wk:+.2f}%"
            + ("  (stronger IDR)" if wk < 0 else "  (weaker IDR)"),
            va="center", fontsize=9, transform=a2.transAxes)
    a2.axis("off")
    days = fx["days"]
    a1.set_xticks(range(len(days)))
    a1.set_xticklabels([d[5:] for d in days])
    fig.tight_layout(); fig.savefig(path, dpi=150); plt.close(fig)
    return True


def main():
    m = load()
    os.makedirs(os.path.join(BASE, "output", "charts"), exist_ok=True)
    base = os.path.join(BASE, "output", "charts")
    chart_change(m, os.path.join(base, "change.png"))
    chart_trend(m, os.path.join(base, "trend.png"))
    chart_weekly_change(m, os.path.join(base, "weekly_change.png"))
    chart_weekly_trend(m, os.path.join(base, "weekly_trend.png"))
    if not chart_rupiah(m, os.path.join(base, "rupiah.png")):
        print("rupiah chart skipped: no USD/IDR fx data")
    print(f"charts -> {base} (daily: change, trend; indonesia focus: weekly_change, weekly_trend, rupiah)")

if __name__ == "__main__":
    main()
