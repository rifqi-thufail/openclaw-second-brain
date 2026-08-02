#!/usr/bin/env python3
"""Generate JPM/GS-style minimal charts. Output: output/charts/*.png"""
import json, os, datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE = os.path.dirname(os.path.abspath(__file__))
GRAY, NAVY, RED, GRID = "#4d4d4d", "#1f4e79", "#a6192e", "#d9d9d9"

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

def chart_change(m, path):
    items = sorted(m["markets"].items(), key=lambda kv: kv[1]["chg_pct"])
    names = [v["name"] for _, v in items]
    vals = [v["chg_pct"] for _, v in items]
    colors = [RED if v < 0 else (NAVY if "(" in n or n in ("Nikkei 225", "Hang Seng") else GRAY)
              for v, (_, n) in zip(vals, [(None, i) for i in names])]
    fig, ax = plt.subplots(figsize=(8.4, 4.0))
    bars = ax.barh(names, vals, color=colors, height=0.62)
    for b, v in zip(bars, vals):
        ax.text(v + (0.08 if v >= 0 else -0.08), b.get_y() + b.get_height() / 2,
                f"{v:+.2f}%", va="center", ha="left" if v >= 0 else "right", fontsize=8)
    ax.axvline(0, color="#333333", linewidth=0.8)
    ax.set_xlabel("Daily change (%)")
    ax.set_title("Index performance, latest close", fontsize=10, fontweight="bold", loc="left")
    fig.tight_layout(); fig.savefig(path, dpi=150); plt.close(fig)

def chart_trend(m, path):
    fig, ax = plt.subplots(figsize=(8.4, 3.6))
    picks = ["^GSPC", "^N225", "^HSI", "^STI", "^KLSE", "^JKSE"]
    for i, sym in enumerate(picks):
        if sym not in m["series"]:
            continue
        s = m["series"][sym]
        asean = "(" in s["name"]
        ax.plot(range(len(s["norm"])), s["norm"], label=s["name"],
                color=NAVY if asean else GRAY,
                linestyle="-" if i % 2 == 0 else "--", linewidth=1.4)
    ax.set_xticks(range(5))
    ax.set_xticklabels([d[5:] for d in m["series"]["^GSPC"]["days"]])
    ax.set_ylabel("Indexed to 100")
    ax.set_title("5-day relative performance", fontsize=10, fontweight="bold", loc="left")
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
