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

def main():
    m = load()
    os.makedirs(os.path.join(BASE, "output", "charts"), exist_ok=True)
    c1 = os.path.join(BASE, "output", "charts", "change.png")
    c2 = os.path.join(BASE, "output", "charts", "trend.png")
    chart_change(m, c1); chart_trend(m, c2)
    print(f"charts -> {c1}, {c2}")

if __name__ == "__main__":
    main()
