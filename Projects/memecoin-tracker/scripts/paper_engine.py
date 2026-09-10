#!/usr/bin/env python3
"""Paper-trade engine — risk rules from Rifqi's mechanism.

Rules:
- risk $1-2 per trade (default 1.5)
- TP1 = 1.5R, TP2 = 2.5R, then trailing stop for the runner
- daily max loss -$5, daily target +$5-10; hitting EITHER stops trading for the day
- no overtrading: max N trades/day (default 5)
- logs every trade to state/paper_trades.json for expectancy review after 30-50 trades
"""
import json, os, sys, datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(BASE, "state")
os.makedirs(STATE, exist_ok=True)

RISK_USD = 1.5
TP1_R = 1.5
TP2_R = 2.5
DAILY_TARGET = 10.0
DAILY_MAX_LOSS = 5.0
MAX_TRADES_DAY = 5


def _path(date):
    return os.path.join(STATE, f"paper_{date}.json")


def load_day(date):
    p = _path(date)
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    return {"date": date, "trades": [], "realized_usd": 0.0, "stopped": False, "stop_reason": None}


def save_day(d):
    with open(_path(d["date"]), "w") as f:
        json.dump(d, f, indent=1)


def can_trade(d):
    if d["stopped"]:
        return False, d["stop_reason"]
    if d["realized_usd"] >= DAILY_TARGET:
        return False, f"daily target +${DAILY_TARGET:.0f} reached"
    if d["realized_usd"] <= -DAILY_MAX_LOSS:
        return False, f"daily max loss -${DAILY_MAX_LOSS:.0f} reached"
    if len(d["trades"]) >= MAX_TRADES_DAY:
        return False, f"max {MAX_TRADES_DAY} trades/day (anti-overtrade)"
    return True, "ok"


def open_paper(day, signal):
    ok, why = can_trade(day)
    if not ok:
        return {"skipped": True, "reason": why}
    t = {"id": len(day["trades"]) + 1, "symbol": signal["symbol"], "entry": signal["plan"]["entry"],
         "stop": signal["plan"]["stop"], "tp1": signal["plan"]["tp1"], "tp2": signal["plan"]["tp2"],
         "risk_usd": RISK_USD, "status": "open", "opened": datetime.datetime.utcnow().isoformat() + "Z",
         "score": signal["score"], "result_usd": 0.0, "events": ["opened"]}
    day["trades"].append(t)
    save_day(day)
    return t


def close_paper(day, trade_id, price, reason):
    for t in day["trades"]:
        if t["id"] == trade_id and t["status"] == "open":
            entry, stop = t["entry"], t["stop"]
            r_dist = entry - stop
            mult = (price - entry) / r_dist if r_dist else 0.0
            pnl = mult * t["risk_usd"]
            t["status"] = "closed"
            t["exit"] = price
            t["exit_reason"] = reason
            t["R"] = round(mult, 2)
            t["result_usd"] = round(pnl, 2)
            t["closed"] = datetime.datetime.utcnow().isoformat() + "Z"
            t["events"].append(reason)
            day["realized_usd"] = round(day["realized_usd"] + pnl, 2)
            ok, why = can_trade(day)
            if not ok:
                day["stopped"] = True
                day["stop_reason"] = why
            save_day(day)
            return t
    return None


def summary(date=None):
    date = date or datetime.date.today().isoformat()
    d = load_day(date)
    closed = [t for t in d["trades"] if t["status"] == "closed"]
    wins = [t for t in closed if t["result_usd"] > 0]
    wr = len(wins) / len(closed) if closed else 0.0
    exp_R = sum(t.get("R", 0) for t in closed) / len(closed) if closed else 0.0
    return {"date": date, "trades": len(d["trades"]), "closed": len(closed),
            "win_rate": round(wr, 2), "expectancy_R": round(exp_R, 2),
            "realized_usd": d["realized_usd"], "stopped": d["stopped"],
            "stop_reason": d["stop_reason"]}


if __name__ == "__main__":
    print(json.dumps(summary(), indent=1))
