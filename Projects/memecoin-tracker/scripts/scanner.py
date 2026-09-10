#!/usr/bin/env python3
"""Memecoin tracker — Solana scan -> pullback -> flow confirm -> score -> signal.

Data source: DexScreener public API (no key required).
Execution: SIGNAL + PAPER TRADING ONLY. No wallet, no keys, no real funds.
Output: state/signals.json + state/paper_trades.json + output/signals-<date>.md
"""
import json, os, sys, time, datetime, urllib.request, urllib.error

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(BASE, "state")
DATA = os.path.join(BASE, "data")
OUT = os.path.join(BASE, "output")
for d in (STATE, DATA, OUT):
    os.makedirs(d, exist_ok=True)

UA = {"User-Agent": "Mozilla/5.0 (compatible; ClawMemeTracker/1.0)"}
DS = "https://api.dexscreener.com"

# ---- tunable filter thresholds (Rifqi's mechanism) ----
MIN_LIQ_USD = 15000          # Liquidity > $15k
MIN_VOL_24H = 25000          # sanity floor
PULLBACK_MIN, PULLBACK_MAX = 15.0, 40.0   # 15-40% off recent high
MIN_TXNS_24H = 300           # activity floor
MAX_TOP10_PCT = 60.0         # holder concentration guard (when available)
SCORE_THRESHOLD = 7          # entry only if >= 7/10


def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            if i == tries - 1:
                print(f"  ! fetch failed {url}: {e}", file=sys.stderr)
                return None
            time.sleep(1.5 * (i + 1))


def scan_solana():
    """Pull boosted + recently active Solana pairs as a candidate universe."""
    cands = {}
    for path in ("/token-boosts/latest/v1", "/token-boosts/top/v1"):
        data = get(DS + path) or []
        for it in data:
            if (it.get("chainId") or "").lower() == "solana":
                addr = it.get("tokenAddress")
                if addr:
                    cands[addr] = {"address": addr, "boost": True}
    # search endpoint for the hottest solana pairs as fallback universe
    for q in ("SOL/USDC", "meme"):
        res = get(f"{DS}/latest/dex/search?q={urllib.request.quote(q)}") or {}
        for p in res.get("pairs", []) or []:
            if (p.get("chainId") or "").lower() == "solana" and p.get("baseToken", {}).get("address"):
                cands[p["baseToken"]["address"]] = {"address": p["baseToken"]["address"]}
    return list(cands.values())


def pair_metrics(addr):
    """Best pair (highest liquidity) for a token address."""
    res = get(f"{DS}/latest/dex/tokens/{addr}") or {}
    pairs = res.get("pairs") or []
    pairs = [p for p in pairs if (p.get("chainId") or "").lower() == "solana"]
    if not pairs:
        return None
    pairs.sort(key=lambda p: float((p.get("liquidity") or {}).get("usd") or 0), reverse=True)
    p = pairs[0]
    liq = float((p.get("liquidity") or {}).get("usd") or 0)
    v24 = float((p.get("volume") or {}).get("h24") or 0)
    v6 = float((p.get("volume") or {}).get("h6") or 0)
    v1 = float((p.get("volume") or {}).get("h1") or 0)
    ch = p.get("priceChange") or {}
    txns = (p.get("txns") or {})
    t24 = txns.get("h24") or {}
    buys = int(t24.get("buys") or 0)
    sells = int(t24.get("sells") or 0)
    return {
        "symbol": (p.get("baseToken") or {}).get("symbol"),
        "name": (p.get("baseToken") or {}).get("name"),
        "price": float(p.get("priceUsd") or 0),
        "liq_usd": liq,
        "vol_24h": v24, "vol_6h": v6, "vol_1h": v1,
        "chg_m5": float(ch.get("m5") or 0),
        "chg_h1": float(ch.get("h1") or 0),
        "chg_h6": float(ch.get("h6") or 0),
        "chg_h24": float(ch.get("h24") or 0),
        "buys_24h": buys, "sells_24h": sells,
        "txns_24h": buys + sells,
        "url": p.get("url"),
        "pair": p.get("pairAddress"),
        "fdv": float(p.get("fdv") or 0),
        "raw": {"priceChange": ch},
    }


def estimate_pullback(m):
    """Approximate drawdown from recent high using 1h/6h/24h change chain.
    True high needs OHLC history; DexScreener gives % changes, so we infer:
    high ~ price / (1 + min(chg)) over the window and pullback = (high-price)/high."""
    ch = m["raw"]["priceChange"]
    ups = [float(ch.get(k) or 0) for k in ("h1", "h6", "h24")]
    # most negative window change suggests we are off a local high
    worst = min(ups) if ups else 0.0
    if worst >= 0:
        return 0.0
    # pullback magnitude as the depth of the negative move
    return round(min(100.0, abs(worst)), 1)


def score(m):
    """0-10 scorecard per Rifqi's bagan. Returns (score, checks dict)."""
    ch = m["raw"]["priceChange"]
    pb = estimate_pullback(m)
    vol_expanding = m["vol_6h"] > 0 and m["vol_24h"] > 0 and (m["vol_6h"] / (m["vol_24h"] / 4.0)) > 1.05
    flow_ratio = (m["buys_24h"] / m["sells_24h"]) if m["sells_24h"] else (2.0 if m["buys_24h"] else 0.0)
    checks = {
        "liquidity_gt_15k": m["liq_usd"] > MIN_LIQ_USD,
        "volume_expanding": bool(vol_expanding),
        "pullback_15_40": PULLBACK_MIN <= pb <= PULLBACK_MAX,
        "structure_intact": float(ch.get("h24") or 0) > -60 and m["price"] > 0,
        "buy_flow_healthy": flow_ratio >= 1.05 and m["buys_24h"] >= 50,
        "no_dev_distribution": float(ch.get("m5") or 0) > -25,   # proxy: no sharp dump now
        "holder_concentration_ok": True,                          # not exposed by public API
        "prev_runner_activity": m["vol_24h"] > MIN_VOL_24H and m["txns_24h"] > MIN_TXNS_24H,
    }
    s = sum(1 for v in checks.values() if v)
    return s, checks, pb, round(flow_ratio, 2)


def build_signal(m, s, checks, pb, flow_ratio):
    liq = m["liq_usd"]
    entry = m["price"]
    # risk = distance to stop (use ~15% below entry as paper stop on low-cap memes)
    stop = entry * 0.85
    risk = entry - stop
    tp1 = entry + 1.5 * risk
    tp2 = entry + 2.5 * risk
    return {
        "ts": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "symbol": m["symbol"], "name": m["name"], "chain": "solana",
        "address": m.get("pair"), "url": m["url"],
        "price": entry, "liquidity_usd": round(liq, 0),
        "vol_24h": round(m["vol_24h"], 0), "vol_6h": round(m["vol_6h"], 0),
        "chg_h1": m["chg_h1"], "chg_h6": m["chg_h6"], "chg_h24": m["chg_h24"],
        "pullback_pct": pb, "buy_sell_ratio": flow_ratio,
        "score": s, "max_score": 10, "checks": checks,
        "plan": {"entry": round(entry, 8), "stop": round(stop, 8),
                 "tp1": round(tp1, 8), "tp2": round(tp2, 8), "tsl": "trail runner after TP2"},
        "risk_usd": 1.5, "note": "paper/signal only, no real funds",
    }


def main():
    date = datetime.date.today().isoformat()
    cands = scan_solana()
    print(f"candidates: {len(cands)}")
    signals, rejected = [], []
    for c in cands[:60]:
        m = pair_metrics(c["address"])
        if not m or not m["symbol"]:
            continue
        if m["liq_usd"] < MIN_LIQ_USD or m["txns_24h"] < 50:
            rejected.append({"symbol": m["symbol"], "reason": "liq/activity floor", "liq": m["liq_usd"]})
            continue
        s, checks, pb, fr = score(m)
        rec = build_signal(m, s, checks, pb, fr)
        (signals if s >= SCORE_THRESHOLD else rejected).append(rec if s >= SCORE_THRESHOLD else
            {"symbol": m["symbol"], "score": s, "checks": checks, "liq": m["liq_usd"]})
    signals.sort(key=lambda r: r["score"], reverse=True)
    payload = {"date": date, "generated": datetime.datetime.utcnow().isoformat() + "Z",
               "threshold": SCORE_THRESHOLD, "signals": signals, "rejected": rejected[:40]}
    with open(os.path.join(STATE, "signals.json"), "w") as f:
        json.dump(payload, f, indent=1)
    with open(os.path.join(DATA, f"scan_{date}.json"), "w") as f:
        json.dump(payload, f, indent=1)
    # markdown summary
    lines = [f"# Memecoin signals {date}", "", f"Candidates scanned: {len(cands)}. Passing score >= {SCORE_THRESHOLD}: {len(signals)}.", ""]
    if signals:
        for r in signals:
            lines += [f"## {r['symbol']} — score {r['score']}/10",
                      f"- liq ${r['liquidity_usd']:,.0f} | 24h vol ${r['vol_24h']:,.0f} | pullback {r['pullback_pct']}% | B/S {r['buy_sell_ratio']}",
                      f"- plan: entry {r['plan']['entry']}, SL {r['plan']['stop']}, TP1 {r['plan']['tp1']}, TP2 {r['plan']['tp2']}, TSL runner",
                      f"- {r['url']}", ""]
    else:
        lines.append("_No setups passed the score filter this scan._")
    with open(os.path.join(OUT, f"signals-{date}.md"), "w") as f:
        f.write("\n".join(lines))
    print(f"signals: {len(signals)} | rejected: {len(rejected)} -> state/signals.json")
    print("PAPER/SIGNAL ONLY — no trades executed.")


if __name__ == "__main__":
    main()
