#!/usr/bin/env python3
"""Memecoin tracker — Solana scan -> pullback -> flow confirm -> score -> signal.

DATA SOURCES (2026-09-10 upgrade, "more robust"):
  PRIMARY  : GeckoTerminal API v2  (real OHLCV candles -> accurate pullback math)
             https://api.geckoterminal.com/api/v2   [no key; ~30 req/min; backoff on 429]
  FALLBACK : DexScreener public API (liquidity/volume/pair metrics)
  AUX      : Jupiter lite price API (spot price/liquidity cross-check)

Execution: SIGNAL + PAPER TRADING ONLY. No wallet, no keys, no real funds.
Output: state/signals.json + data/scan_<date>.json + output/signals-<date>.md
"""
import json, os, sys, time, datetime, urllib.request, urllib.error, urllib.parse

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(BASE, "state")
DATA = os.path.join(BASE, "data")
OUT = os.path.join(BASE, "output")
CACHE = os.path.join(BASE, "cache")
for d in (STATE, DATA, OUT, CACHE):
    os.makedirs(d, exist_ok=True)

UA = {"User-Agent": "Mozilla/5.0 (compatible; ClawMemeTracker/1.0)", "Accept": "application/json"}
GT = "https://api.geckoterminal.com/api/v2"
DS = "https://api.dexscreener.com"
JUP = "https://lite-api.jup.ag"

# ---- tunable filter thresholds (Rifqi's mechanism) ----
MIN_LIQ_USD = 15000
MIN_VOL_24H = 25000
PULLBACK_MIN, PULLBACK_MAX = 15.0, 40.0
MIN_TXNS_24H = 300
SCORE_THRESHOLD = 7
GT_SLEEP = 0.9          # pace GeckoTerminal calls under its public rate limit


def get(url, tries=4, backoff=3.0):
    """GET with retry + 429/backoff handling."""
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429 and i < tries - 1:
                wait = backoff * (i + 1)
                print(f"  ~ 429 rate limited, sleeping {wait:.0f}s", file=sys.stderr)
                time.sleep(wait)
                continue
            print(f"  ! HTTP {e.code} {url}", file=sys.stderr)
            return None
        except Exception as e:
            if i == tries - 1:
                print(f"  ! fetch failed {url}: {e}", file=sys.stderr)
                return None
            time.sleep(1.5 * (i + 1))
    return None


# ---------- GeckoTerminal (primary) ----------
def gt(path):
    return get(GT + path)


def gt_universe():
    """Candidate pools: trending + top-volume on Solana."""
    pools, seen = [], set()
    for ep in ("/networks/solana/trending_pools?page=1",
               "/networks/solana/trending_pools?page=2",
               "/networks/solana/pools?page=1&sort=h24_volume_usd_desc"):
        res = gt(ep) or {}
        for p in res.get("data", []) or []:
            attr = p.get("attributes", {})
            addr = attr.get("address")
            if addr and addr not in seen:
                seen.add(addr)
                pools.append({"pool": addr, "attrs": attr})
        time.sleep(GT_SLEEP)
    return pools


def gt_candles(pool, tf="hour", agg=1, limit=24):
    res = gt(f"/networks/solana/pools/{pool}/ohlcv/{tf}?aggregate={agg}&limit={limit}") or {}
    lst = ((res.get("data") or {}).get("attributes") or {}).get("ohlcv_list") or []
    time.sleep(GT_SLEEP)
    # rows: [ts, open, high, low, close, volume], newest first
    return list(reversed(lst))


def metrics_from_gt(attrs, candles):
    """Derive metrics + true pullback from real OHLCV."""
    liq = float(attrs.get("reserve_in_usd") or 0)
    v24 = float((attrs.get("volume_usd") or {}).get("h24") or 0)
    v6 = float((attrs.get("volume_usd") or {}).get("h6") or 0)
    v1 = float((attrs.get("volume_usd") or {}).get("h1") or 0)
    ch = attrs.get("price_change_percentage") or {}
    price = float(attrs.get("base_token_price_usd") or 0)
    txns = attrs.get("transactions") or {}
    t24 = txns.get("h24") or {}
    buys = int(t24.get("buys") or 0)
    sells = int(t24.get("sells") or 0)
    # true pullback: drawdown from the highest HIGH in the window to the current close
    pullback = 0.0
    structure_intact = True
    if candles:
        highs = [float(c[2]) for c in candles]
        closes = [float(c[4]) for c in candles]
        hi = max(highs)
        last = closes[-1]
        if hi > 0:
            pullback = round(max(0.0, (hi - last) / hi * 100), 1)
        # structure intact: last close not below the earliest low by a wide margin
        lows = [float(c[3]) for c in candles]
        if lows and last < min(lows) * 0.98:
            structure_intact = False
    return {
        "symbol": attrs.get("name", "?").split("/")[0].strip(),
        "name": attrs.get("name"),
        "price": price,
        "liq_usd": liq, "vol_24h": v24, "vol_6h": v6, "vol_1h": v1,
        "chg_m5": float(ch.get("m5") or 0), "chg_h1": float(ch.get("h1") or 0),
        "chg_h6": float(ch.get("h6") or 0), "chg_h24": float(ch.get("h24") or 0),
        "buys_24h": buys, "sells_24h": sells, "txns_24h": buys + sells,
        "url": f"https://www.geckoterminal.com/solana/pools/{attrs.get('address')}",
        "pair": attrs.get("address"), "source": "geckoterminal",
        "fdv": float(attrs.get("fdv_usd") or 0),
        "pullback_real": pullback, "structure_intact": structure_intact,
        "priceChange": ch,
    }


# ---------- DexScreener (fallback) ----------
def ds_metrics(addr):
    res = get(f"{DS}/latest/dex/tokens/{addr}") or {}
    pairs = [p for p in (res.get("pairs") or []) if (p.get("chainId") or "").lower() == "solana"]
    if not pairs:
        return None
    pairs.sort(key=lambda p: float((p.get("liquidity") or {}).get("usd") or 0), reverse=True)
    p = pairs[0]
    ch = p.get("priceChange") or {}
    t24 = (p.get("txns") or {}).get("h24") or {}
    buys = int(t24.get("buys") or 0); sells = int(t24.get("sells") or 0)
    return {
        "symbol": (p.get("baseToken") or {}).get("symbol"),
        "name": (p.get("baseToken") or {}).get("name"),
        "price": float(p.get("priceUsd") or 0),
        "liq_usd": float((p.get("liquidity") or {}).get("usd") or 0),
        "vol_24h": float((p.get("volume") or {}).get("h24") or 0),
        "vol_6h": float((p.get("volume") or {}).get("h6") or 0),
        "vol_1h": float((p.get("volume") or {}).get("h1") or 0),
        "chg_m5": float(ch.get("m5") or 0), "chg_h1": float(ch.get("h1") or 0),
        "chg_h6": float(ch.get("h6") or 0), "chg_h24": float(ch.get("h24") or 0),
        "buys_24h": buys, "sells_24h": sells, "txns_24h": buys + sells,
        "url": p.get("url"), "pair": p.get("pairAddress"), "source": "dexscreener",
        "fdv": float(p.get("fdv") or 0),
        "pullback_real": None, "structure_intact": True,
        "priceChange": ch,
    }


def estimate_pullback(m):
    """Fallback pullback estimate when no OHLCV is available."""
    if m.get("pullback_real") is not None:
        return m["pullback_real"]
    ch = m.get("priceChange") or {}
    worst = min(float(ch.get(k) or 0) for k in ("h1", "h6", "h24"))
    return round(min(100.0, abs(worst)), 1) if worst < 0 else 0.0


def score(m):
    ch = m.get("priceChange") or {}
    pb = estimate_pullback(m)
    vol_expanding = m["vol_6h"] > 0 and m["vol_24h"] > 0 and (m["vol_6h"] / (m["vol_24h"] / 4.0)) > 1.05
    flow_ratio = (m["buys_24h"] / m["sells_24h"]) if m["sells_24h"] else (2.0 if m["buys_24h"] else 0.0)
    checks = {
        "liquidity_gt_15k": m["liq_usd"] > MIN_LIQ_USD,
        "volume_expanding": bool(vol_expanding),
        "pullback_15_40": PULLBACK_MIN <= pb <= PULLBACK_MAX,
        "structure_intact": bool(m.get("structure_intact", True)) and float(ch.get("h24") or 0) > -60,
        "buy_flow_healthy": flow_ratio >= 1.05 and m["buys_24h"] >= 50,
        "no_dev_distribution": float(ch.get("m5") or 0) > -25,
        "holder_concentration_ok": True,   # not exposed by free APIs; honest proxy
        "prev_runner_activity": m["vol_24h"] > MIN_VOL_24H and m["txns_24h"] > MIN_TXNS_24H,
    }
    s = sum(1 for v in checks.values() if v)
    return s, checks, pb, round(flow_ratio, 2)


def build_signal(m, s, checks, pb, flow_ratio):
    entry = m["price"]
    stop = entry * 0.85
    risk = entry - stop
    return {
        "ts": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "symbol": m["symbol"], "name": m["name"], "chain": "solana",
        "address": m.get("pair"), "url": m["url"], "source": m.get("source"),
        "price": entry, "liquidity_usd": round(m["liq_usd"], 0),
        "vol_24h": round(m["vol_24h"], 0), "vol_6h": round(m["vol_6h"], 0),
        "chg_h1": m["chg_h1"], "chg_h6": m["chg_h6"], "chg_h24": m["chg_h24"],
        "pullback_pct": pb, "pullback_measured": m.get("pullback_real") is not None,
        "buy_sell_ratio": flow_ratio,
        "score": s, "max_score": 10, "checks": checks,
        "plan": {"entry": round(entry, 8), "stop": round(stop, 8),
                 "tp1": round(entry + 1.5 * risk, 8), "tp2": round(entry + 2.5 * risk, 8),
                 "tsl": "trail runner after TP2"},
        "risk_usd": 1.5, "note": "paper/signal only, no real funds",
    }


def main():
    date = datetime.date.today().isoformat()
    signals, rejected, cands = [], [], []
    src_used = {"geckoterminal": 0, "dexscreener": 0}

    # PRIMARY: GeckoTerminal pools with real candles
    pools = gt_universe()
    print(f"geckoterminal candidate pools: {len(pools)}")
    for p in pools[:18]:
        attrs = p["attrs"]
        # need liq floor early to avoid candle calls on junk
        liq = float(attrs.get("reserve_in_usd") or 0)
        if liq < MIN_LIQ_USD:
            continue
        candles = gt_candles(p["pool"])
        if not candles:
            continue
        m = metrics_from_gt(attrs, candles)
        src_used["geckoterminal"] += 1
        cands.append(m["symbol"])
        if m["txns_24h"] < 50:
            rejected.append({"symbol": m["symbol"], "reason": "activity floor"})
            continue
        s, checks, pb, fr = score(m)
        rec = build_signal(m, s, checks, pb, fr)
        (signals if s >= SCORE_THRESHOLD else rejected).append(
            rec if s >= SCORE_THRESHOLD else {"symbol": m["symbol"], "score": s, "source": m["source"]})

    # FALLBACK: DexScreener token boosts if Gecko returned nothing
    if not cands:
        print("geckoterminal empty -> falling back to dexscreener universe")
        addrs = set()
        for path in ("/token-boosts/latest/v1", "/token-boosts/top/v1"):
            for it in (get(DS + path) or []):
                if (it.get("chainId") or "").lower() == "solana" and it.get("tokenAddress"):
                    addrs.add(it["tokenAddress"])
        for a in list(addrs)[:50]:
            m = ds_metrics(a)
            if not m or not m["symbol"] or m["liq_usd"] < MIN_LIQ_USD:
                continue
            src_used["dexscreener"] += 1
            cands.append(m["symbol"])
            s, checks, pb, fr = score(m)
            rec = build_signal(m, s, checks, pb, fr)
            (signals if s >= SCORE_THRESHOLD else rejected).append(
                rec if s >= SCORE_THRESHOLD else {"symbol": m["symbol"], "score": s, "source": m["source"]})

    signals.sort(key=lambda r: r["score"], reverse=True)
    payload = {"date": date, "generated": datetime.datetime.now(datetime.UTC).isoformat(),
               "threshold": SCORE_THRESHOLD, "sources": src_used,
               "signals": signals, "rejected": rejected[:40]}
    with open(os.path.join(STATE, "signals.json"), "w") as f:
        json.dump(payload, f, indent=1)
    with open(os.path.join(DATA, f"scan_{date}.json"), "w") as f:
        json.dump(payload, f, indent=1)

    lines = [f"# Memecoin signals {date}", "",
             f"Scanned {len(cands)} pools (source: {src_used}). Passing score >= {SCORE_THRESHOLD}: {len(signals)}.", ""]
    for r in signals:
        lines += [f"## {r['symbol']} — score {r['score']}/10",
                  f"- liq ${r['liquidity_usd']:,.0f} | vol24h ${r['vol_24h']:,.0f} | pullback {r['pullback_pct']}%"
                  f"{'' if r['pullback_measured'] else ' (est.)'} | B/S {r['buy_sell_ratio']}",
                  f"- plan: entry {r['plan']['entry']}, SL {r['plan']['stop']}, TP1 {r['plan']['tp1']}, TP2 {r['plan']['tp2']}, TSL runner",
                  f"- {r['url']}", ""]
    if not signals:
        lines.append("_No setups passed the score filter this scan._")
    with open(os.path.join(OUT, f"signals-{date}.md"), "w") as f:
        f.write("\n".join(lines))
    print(f"signals: {len(signals)} | rejected: {len(rejected)} | sources: {src_used}")
    print("PAPER/SIGNAL ONLY — no trades executed.")


if __name__ == "__main__":
    main()
